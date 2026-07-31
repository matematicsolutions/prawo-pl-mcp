"""FastMCP server - 4 unified tools nad flota polskich konektorow prawnych.

Uruchamianie:
    python -m prawo_pl_mcp

Lub jako entry point po pip install / uvx:
    prawo-pl-mcp
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import __version__, audit
from .instructions import INSTRUCTIONS
from .pagination import paginate
from .pool import POOL, SourceUnavailable
from .registry import SOURCES, Source, catalog, get_source


# Strukturalne kody bledow - drift test: kazdy kod w INSTRUCTIONS.
class PLLegalError(Exception):
    """Strukturalny blad agregatora - widoczny dla LLM z prefixem [code]."""

    VALID_CODES = frozenset({
        "unknown_source",
        "unknown_tool",
        "invalid_arg",
        "source_unavailable",
        "upstream_error",
    })

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown PLLegalError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,  # zrodla to zywe API/scraping (poza eu-compliance offline)
)

mcp = FastMCP(name="prawo-pl-mcp", instructions=INSTRUCTIONS)


# ---------- helpers ----------


def _resolve(source: str) -> Source:
    s = get_source(source)
    if s is None:
        raise PLLegalError(
            "unknown_source",
            f"Source '{source}' not in registry. Available: {', '.join(sorted(SOURCES))}. "
            f"Call pl_list_sources for details.",
        )
    return s


def _otel_tag(source_id: str | None) -> None:
    """OTel atrybuty per-call (kanon floty). No-op bez opentelemetry."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("mcp.server", "prawo-pl-mcp")
            if source_id:
                span.set_attribute("mcp.source", source_id)
    except Exception:
        pass


async def _proxy_call(s: Source, tool: str, arguments: dict) -> str:
    """Wywolanie natywnego toola z mapowaniem bledow na kody agregatora."""
    try:
        return await POOL.call(s, tool, arguments)
    except PLLegalError:
        raise
    except SourceUnavailable as exc:
        raise PLLegalError("source_unavailable", str(exc)) from exc
    except Exception as exc:
        msg = str(exc)
        if "unknown tool" in msg.lower() or "tool not found" in msg.lower():
            raise PLLegalError(
                "unknown_tool",
                f"Source '{s.id}' does not expose tool '{tool}'. Native tools: "
                f"{', '.join(s.native_tools)}. Verify via pl_list_sources(source_id='{s.id}').",
            ) from exc
        # Kod bledu konektora (np. [invalid_signature], [not_found]) zostaje w message.
        raise PLLegalError("upstream_error", f"{s.id}/{tool}: {msg}") from exc


def _audited(tool: str, source_id: str | None, params: Any, started: float,
             summary: dict, error: str | None = None) -> None:
    audit.log_event(
        tool=tool,
        source=source_id,
        params=params,
        result_summary=summary,
        latency_ms=(time.monotonic() - started) * 1000,
        error=error,
    )


# ---------- unified tools ----------


async def pl_list_sources(source_id: str | None = None, group: str | None = None) -> str:
    """List available Polish/EU legal data sources, or inspect one source's live tool schemas.

    Without arguments: full catalog (id, coverage, capabilities, native tool names) -
    reads a local registry, spawns nothing. With `source_id`: connects to that
    connector (lazy spawn on first use) and returns its live tools/list with input
    schemas - use before pl_call or before passing source-specific `extra` params.
    Optional `group` filter: 'pl' (Polish sources) or 'eu' (EU extras).

    Errors: `unknown_source` (bad source_id), `source_unavailable` (connector
    could not start).
    """
    started = time.monotonic()
    _otel_tag(source_id)
    if source_id is None:
        if group is not None and group not in ("pl", "eu"):
            raise PLLegalError("invalid_arg", "group must be 'pl' or 'eu'")
        result = {
            "server": f"prawo-pl-mcp {__version__}",
            "sources": catalog(group),
            "hint": "pl_search / pl_get_document for the common path; "
            "pl_call for source-specific tools; "
            "pl_list_sources(source_id=...) for live schemas.",
        }
        _audited("pl_list_sources", None, {"group": group}, started, {"sources": len(result["sources"])})
        return json.dumps(result, ensure_ascii=False, indent=1)

    s = _resolve(source_id)
    try:
        tools = await POOL.list_tools(s)
    except SourceUnavailable as exc:
        _audited("pl_list_sources", s.id, {"source_id": source_id}, started, {}, error=str(exc))
        raise PLLegalError("source_unavailable", str(exc)) from exc
    _audited("pl_list_sources", s.id, {"source_id": source_id}, started, {"tools": len(tools)})
    return json.dumps({"source": s.id, "tools": tools}, ensure_ascii=False, indent=1)


async def pl_search(
    source: str,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    limit: int | None = None,
    extra: dict | None = None,
) -> str:
    """Unified search across any registered source (SAOS, NSA, ISAP, EUREKA, KIO, UODO...).

    Common parameters are translated to the source's native names (dateFrom vs
    date_from, 0- vs 1-based pages - handled here; `page` is ALWAYS 1-based).
    `date_from`/`date_to`: YYYY-MM-DD. `limit`: results per page (clamped to the
    source maximum). `extra`: source-specific native filters merged verbatim
    (e.g. {"courtType": "SUPREME"} for saos, {"country": "es"} for legalize -
    see pl_list_sources).

    Errors: `unknown_source`, `invalid_arg` (source has no search tool, e.g. krs;
    missing required extra; page < 1), `source_unavailable`, `upstream_error`
    (connector's own error code preserved in message).
    """
    started = time.monotonic()
    s = _resolve(source)
    _otel_tag(s.id)
    spec = s.search
    if spec is None:
        raise PLLegalError(
            "invalid_arg",
            f"Source '{s.id}' has no search tool ({s.notes or 'lookup by identifier only'}). "
            f"Use pl_get_document or pl_call.",
        )
    if page < 1:
        raise PLLegalError("invalid_arg", f"page is 1-based; got {page}")

    args: dict[str, Any] = dict(extra or {})
    missing = [p for p in spec.required_extra if p not in args]
    if missing:
        raise PLLegalError(
            "invalid_arg",
            f"Source '{s.id}' search requires extra={{{', '.join(repr(m) for m in missing)}: ...}}. "
            f"See pl_list_sources(source_id='{s.id}').",
        )
    if query is not None and spec.query_param:
        args.setdefault(spec.query_param, query)
    if date_from is not None:
        if not spec.date_from_param:
            raise PLLegalError(
                "invalid_arg",
                f"Source '{s.id}' does not support date filtering ({s.notes or 'no date params'}).",
            )
        args.setdefault(spec.date_from_param, date_from)
    if date_to is not None and spec.date_to_param:
        args.setdefault(spec.date_to_param, date_to)
    if spec.page_param:
        args.setdefault(spec.page_param, page - 1 if spec.page_base == 0 else page)
    if limit is not None and spec.size_param:
        clamped = min(limit, spec.size_max) if spec.size_max else limit
        args.setdefault(spec.size_param, clamped)

    try:
        text = await _proxy_call(s, spec.tool, args)
    except PLLegalError as exc:
        _audited("pl_search", s.id, args, started, {}, error=exc.code)
        raise
    _audited("pl_search", s.id, args, started, {"chars": len(text)})
    return text


async def pl_get_document(
    source: str,
    document_id: str,
    page_number: int = 1,
    extra: dict | None = None,
) -> str:
    """Fetch the full document (judgment, act text, register extract...) from a source.

    `document_id` format depends on the source - numeric id (saos), hex doc_id
    (nsa), ELI (isap), KRS number (krs), signature (kio, uodo)... - see the
    `document_id` field in pl_list_sources. Long documents are paginated at
    ~5000 characters per page: response is JSON with `content`, `page_number`,
    `total_pages`, `has_more` - iterate `page_number` while `has_more`.
    Some sources need `extra` (e.g. eu-compliance: {"regulation": "GDPR"}).

    Errors: `unknown_source`, `invalid_arg` (missing required extra),
    `source_unavailable`, `upstream_error` (e.g. connector's not_found -
    check the identifier or search first).
    """
    started = time.monotonic()
    s = _resolve(source)
    _otel_tag(s.id)
    spec = s.get

    args: dict[str, Any] = dict(extra or {})
    missing = [p for p in spec.required_extra if p not in args]
    if missing:
        raise PLLegalError(
            "invalid_arg",
            f"Source '{s.id}' document fetch requires extra={{{', '.join(repr(m) for m in missing)}: ...}}. "
            f"Hint: {spec.id_hint}",
        )
    args.setdefault(spec.id_param, document_id)

    try:
        text = await _proxy_call(s, spec.tool, args)
    except PLLegalError as exc:
        _audited("pl_get_document", s.id, args, started, {}, error=exc.code)
        raise
    page = paginate(text, page_number)
    page["source"] = s.id
    page["document_id"] = document_id
    _audited(
        "pl_get_document", s.id, args, started,
        {"total_chars": page["total_chars"], "page": page["page_number"]},
    )
    return json.dumps(page, ensure_ascii=False)


async def pl_call(source: str, tool: str, arguments: dict | None = None) -> str:
    """Escape hatch: call any native tool of any registered source.

    For operations the unified tools do not cover: citator (saos_cite_check),
    DPA statistics (uodo_stats), procurement-article search (kio_by_pzp_article),
    board composition (get_board), regulation comparison (eu_compare), tax
    category dictionary (list_categories)... Check the exact input schema first
    via pl_list_sources(source_id=...) - `arguments` are passed verbatim.

    Errors: `unknown_source`, `unknown_tool` (not exposed by that source),
    `source_unavailable`, `upstream_error` (connector's own error code in message).
    """
    started = time.monotonic()
    s = _resolve(source)
    _otel_tag(s.id)
    args = arguments or {}
    try:
        text = await _proxy_call(s, tool, args)
    except PLLegalError as exc:
        _audited("pl_call", s.id, {"tool": tool, **args}, started, {}, error=exc.code)
        raise
    _audited("pl_call", s.id, {"tool": tool, **args}, started, {"chars": len(text)})
    return text


for _tool in (pl_list_sources, pl_search, pl_get_document, pl_call):
    mcp.tool(_tool, annotations=READ_ONLY)


def main() -> None:
    """Entry point stdio."""
    try:
        mcp.run()
    finally:
        try:
            asyncio.run(POOL.close_all())
        except Exception:
            pass


if __name__ == "__main__":
    main()
