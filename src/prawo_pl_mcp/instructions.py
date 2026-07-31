"""Procedural orchestration - wstrzykiwane do system promptu klienta MCP.

LLM widzi to PRZED pierwszym tool call. Pattern z dograh v1.31.0 via flota
matematicsolutions. Drift test (tests/test_instructions_drift.py) failuje jesli
tool wymieniony tutaj nie jest zarejestrowany lub kod bledu nieudokumentowany.

Zasady: call order, twarde ograniczenia, iteracja po bledach, styl. NIE
re-enumerujemy sygnatur tooli (sa w tools/list) ani szczegolow zrodel
(sa w pl_list_sources - zero driftu przy dodaniu zrodla do registry).
"""

INSTRUCTIONS = """\
One MCP server for Polish legal data. Aggregates independent MCP connectors
(case law, legislation, company register, tax rulings, public procurement,
data-protection decisions + optional EU corpus) behind 4 unified tools.
Connectors run as on-demand subprocesses; the first call to a source may take
several seconds (package download + spawn), subsequent calls are fast.

## Call order

1. `pl_list_sources` - start here. Without arguments: catalog of sources
   (id, coverage, capabilities, native tools). With `source_id`: live tool
   schemas of that connector - check before using `pl_call` or source-specific
   `extra` parameters.
2. `pl_search` - unified search across any source. Common parameters
   (`query`, `date_from`, `date_to`, `page`, `limit`) are translated to the
   source's native names; pass source-specific filters via `extra` (native
   names, see `pl_list_sources(source_id=...)`).
3. `pl_get_document` - full document by source + identifier (judgment ID or
   case signature, ELI, KRS number, interpretation ID...). Long documents are
   paginated at ~5000 characters per page; iterate `page_number` while
   `has_more` is true.
4. `pl_call` - escape hatch: any native tool of any source (citator checks,
   statistics, board composition, dictionaries...). Use when unified tools do
   not cover the operation. Verify the schema first via
   `pl_list_sources(source_id=...)`.

## Hard constraints

- Legal answers require documents, not search snippets: after `pl_search`,
  fetch the actual text with `pl_get_document` before quoting or reasoning.
- NEVER invent case signatures, ELI identifiers, KRS numbers or dates - use
  only values returned by tools. Quote verbatim from document content.
- Always cite: source name + identifier + date + source URL when returned.
- Each source enforces its own rate limits - do not send bursts of parallel
  queries to one source.
- All tools are read-only; no tool mutates any upstream system.
- Audit log JSONL: every call is logged to ~/.matematic/audit/prawo-pl-mcp.jsonl
  (no document content).

## Iterating on errors

Errors carry a `[code]` prefix:
- `unknown_source` - source id not in registry. Call `pl_list_sources` and retry.
- `unknown_tool` - native tool name not exposed by that source (pl_call).
  Check `pl_list_sources(source_id=...)`.
- `invalid_arg` - parameter out of range or missing. Fix per message and retry.
- `source_unavailable` - connector could not start (missing Node/uv runtime or
  package unreachable). Report to the user with the message hint; other sources
  keep working - consider an alternative source.
- `upstream_error` - the connector itself errored (its own [code] is preserved
  in the message, e.g. invalid_signature, not_found). Follow the inner message;
  retry once if it looks transient.

## Style

- Present results with full citations (signature + date + court/body).
- When comparing case law across sources (e.g. SAOS vs NSA), state which
  database each ruling comes from.
- Administrative-court matters: prefer the NSA source; general courts and
  Supreme Court: SAOS. Statutes: ISAP. If unsure, check coverage in
  `pl_list_sources`.
- Disclaimer where relevant: court rulings are not a source of law in Poland
  (art. 87 of the Constitution) - reference material, not binding precedent.
"""
