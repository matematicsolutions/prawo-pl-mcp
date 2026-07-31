"""Audit log JSONL dla rozliczalnosci operatora agregatora.

Lokalizacja: ~/.matematic/audit/pl-legal-mcp.jsonl (override: PL_LEGAL_MCP_AUDIT_DIR).

Co logujemy: ts, tool, source, params_hash, result_summary, latency_ms.
Czego NIE logujemy: pelna tresc dokumentow/orzeczen (przechodzi przez proxy verbatim).
Wzorzec 1:1 z floty (kio-orzeczenia-mcp/audit.py), zmieniony tylko prefiks env i plik.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _audit_dir() -> Path:
    override = os.environ.get("PL_LEGAL_MCP_AUDIT_DIR")
    if override:
        return Path(override)
    return Path.home() / ".matematic" / "audit"


def _audit_file() -> Path:
    return _audit_dir() / "pl-legal-mcp.jsonl"


def params_hash(params: Any) -> str:
    """SHA-256 z params (deterministyczny dump JSON)."""
    try:
        s = json.dumps(params, sort_keys=True, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        s = repr(params)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def log_event(
    tool: str,
    source: str | None,
    params: Any,
    result_summary: dict[str, Any],
    latency_ms: float,
    error: str | None = None,
) -> None:
    """Zapisz wpis do audit log JSONL. Best-effort - bledy nie blokuja flow."""
    try:
        d = _audit_dir()
        d.mkdir(parents=True, exist_ok=True)

        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "tool": tool,
            "source": source,
            "params_hash": params_hash(params),
            "result_summary": result_summary,
            "latency_ms": round(latency_ms, 2),
        }
        if error is not None:
            entry["error"] = error

        with _audit_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Audit log to best-effort - nie blokujemy uzytkownika jezeli sie nie da pisac.
        pass
