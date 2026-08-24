# prawo-pl-mcp

<!-- mcp-name: io.github.matematicsolutions/prawo-pl-mcp -->

One MCP server for Polish legal data.

Ten independent connectors - case law, legislation, the company register, tax
rulings, public procurement, data-protection decisions, plus EU extras - behind
four tools. Each connector stays a separate package with its own repository;
this server spawns them on demand and translates between their conventions.

"Prawo" is Polish for "law"; the name follows yargi-mcp's move of naming a
country server in its own language.

## Why an aggregator

The connectors cover Polish legal data well, but as separate MCP servers, one
per database - ten installs and ten config entries before the first question.
[yargi-mcp](https://github.com/saidsurucu/yargi-mcp) showed the fix for
Turkish law: 16 institutions, one server. prawo-pl-mcp does the same for Poland:

- Four tools instead of 42. `pl_list_sources`, `pl_search`, `pl_get_document`,
  `pl_call` - fewer tool schemas means less context spent before the LLM starts
  working.
- One convention. The connectors grew organically: `dateFrom` here, `date_from`
  there, pages counted from 0 or from 1 depending on the repo. Here `page` is
  always 1-based and dates are always `date_from`/`date_to` (YYYY-MM-DD); the
  translation happens inside. One name per concept applies to the aggregator's
  own tools too: `page` is the page parameter of both `pl_search` and
  `pl_get_document` (`page_number` still works as a deprecated alias), and
  `pl_call` takes `arguments` or its alias `args`.
- Native names on the table. Every catalog entry carries `native_params` - the
  native parameter name each unified one maps to for that source, so
  `article_number` (eu-compliance) is visible without spawning the connector or
  reading an upstream error. `pl_call` checks the names it was given against
  the connector's own schema and says which one it meant.
- Nothing preinstalled. Connectors run as subprocesses via `npx -y` / `uvx`,
  downloaded on the first call to a given source and kept alive afterwards.
  A source that cannot start reports a readable error while the rest keep
  working.
- Paginated documents. Full judgment and act texts are chunked at ~5000
  characters per page (yargi-mcp's pattern), so a 200-page ruling does not
  flood the context window. Sources that paginate server-side (`isap`) get the
  `page` forwarded natively and are reported as `pagination: "native"` - the
  aggregator does not re-cut an already-cut page and does not invent a
  `total_pages` it cannot know.

## Coverage

| Source id | What | Institution / database | Connector | Runtime |
|---|---|---|---|---|
| `saos` | Case law: common courts, Supreme Court, Constitutional Tribunal + citator | [SAOS](https://www.saos.org.pl) | [mcp-saos](https://github.com/matematicsolutions/mcp-saos) | npx |
| `nsa` | Case law: administrative courts (NSA + 16 WSA) | [CBOSA](https://orzeczenia.nsa.gov.pl) | [mcp-nsa](https://github.com/matematicsolutions/mcp-nsa) | npx |
| `isap` | Legislation: Dziennik Ustaw + Monitor Polski, 96k+ acts | [Sejm ELI API](https://api.sejm.gov.pl) | [mcp-isap](https://github.com/matematicsolutions/mcp-isap) | npx |
| `krs` | Company register: extracts, history, board composition | [KRS API (Ministry of Justice)](https://api-krs.ms.gov.pl) | [mcp-krs](https://github.com/matematicsolutions/mcp-krs) | npx |
| `eureka` | Tax rulings: 550k+ individual interpretations | [EUREKA (Ministry of Finance)](https://eureka.mf.gov.pl) | [mcp-eureka](https://github.com/matematicsolutions/mcp-eureka) | npx |
| `kio` | Public procurement: National Appeal Chamber rulings | [orzeczenia.uzp.gov.pl](https://orzeczenia.uzp.gov.pl) | [kio-orzeczenia-mcp](https://github.com/matematicsolutions/kio-orzeczenia-mcp) | uvx |
| `uodo` | GDPR enforcement: Polish DPA decisions, fines, stats | [orzeczenia.uodo.gov.pl](https://orzeczenia.uodo.gov.pl) | [uodo-orzeczenia-mcp](https://github.com/matematicsolutions/uodo-orzeczenia-mcp) | uvx |
| `eu-sparql` | EU law: EUR-Lex by CELEX, CJEU by ECLI, GDPRhub | [Cellar SPARQL](https://op.europa.eu/en/web/cellar) | [mcp-eu-sparql](https://github.com/matematicsolutions/mcp-eu-sparql) | npx |
| `eu-compliance` | 14 EU regulations offline (GDPR, AI Act, DORA, NIS2...) | Local SQLite corpus | [mcp-eu-compliance](https://github.com/matematicsolutions/mcp-eu-compliance) | npx |
| `legalize` | Law-as-git: 32 jurisdictions, versioned by commit | [legalize-dev](https://github.com/legalize-dev) | [legalize-mcp](https://github.com/matematicsolutions/legalize-mcp) | uvx |

Polish sources are tagged `group: pl`, EU extras `group: eu` - filter with
`pl_list_sources(group="pl")`.

## Tools

| Tool | What it does |
|---|---|
| `pl_list_sources` | Catalog of sources (no subprocess spawned). With `source_id`: live tool schemas of one connector. |
| `pl_search` | Search any source with normalized parameters; source-specific filters via `extra`. |
| `pl_get_document` | Full document by identifier (judgment id, ELI, KRS number, signature...), paginated. |
| `pl_call` | Any native tool of any connector: citator, DPA statistics, board composition, regulation comparison... |
| `pl_coverage` | Declare what this connector covers, when each family was captured, and - explicitly - what it does NOT cover. Every gap carries a fallback. |

The typical flow an LLM follows (spelled out in the server's `instructions`):
`pl_list_sources` → `pl_search` → `pl_get_document`, with `pl_call` for the
specialized tools each connector brings.

## Install

Requires Python ≥ 3.11 plus the runtimes of the sources you use: Node.js ≥ 18
for `npx` sources, [uv](https://docs.astral.sh/uv/) for `uvx` sources. If a
runtime is missing, its sources report `source_unavailable` and the rest work.

### Claude Code

```bash
claude mcp add pl-legal -- uvx prawo-pl-mcp
```

### Claude Desktop / any MCP client (stdio)

```json
{
  "mcpServers": {
    "pl-legal": {
      "command": "uvx",
      "args": ["prawo-pl-mcp"]
    }
  }
}
```

### Remote (Streamable HTTP)

```bash
uvicorn prawo_pl_mcp.asgi:app --host 0.0.0.0 --port 8000
```

Open by default (public, read-only data). Set `PRAWO_PL_MCP_API_KEY` to require
`X-API-Key: <key>` or `Authorization: Bearer <key>` on every request.

## Configuration

| Env | Default | Meaning |
|---|---|---|
| `PRAWO_PL_MCP_CMD_<ID>` | - | Override the spawn command for a source, e.g. `PRAWO_PL_MCP_CMD_SAOS="node C:/dev/mcp-saos/dist/index.js"` for a local checkout. `<ID>` = source id, uppercase, `-` → `_`. |
| `PRAWO_PL_MCP_INIT_TIMEOUT` | `180` | Seconds allowed for a connector's first start (includes package download). |
| `PRAWO_PL_MCP_TIMEOUT` | `90` | Seconds per tool call after startup. |
| `PRAWO_PL_MCP_AUDIT_DIR` | `~/.matematic/audit` | Where the JSONL audit log goes. |
| `PRAWO_PL_MCP_API_KEY` | - | ASGI mode only: require this API key (dual-channel). |

## Architecture

The aggregator is a thin proxy
([ADR 0001](docs/adr/0001-proxy-nie-monorepo.md)). Connectors are not imported,
vendored or forked; the aggregator speaks MCP to them over stdio the same way
any client would. The whole layer is a source registry (one dataclass entry
per connector), a lazy subprocess pool, a parameter translator and a paginator.
Adding a source means adding a registry entry.

```
LLM client ──MCP──▶ prawo-pl-mcp ──MCP/stdio──▶ npx @matematicsolutions/mcp-saos
                        │         ──MCP/stdio──▶ uvx kio-orzeczenia-mcp
                        │         ──MCP/stdio──▶ ... (spawned on first use)
                        └─ registry + param mapping + 5000-char pagination
```

Every call lands in a JSONL audit log (timestamp, tool, source, parameter hash,
latency - never document content).

## Development

```bash
git clone https://github.com/matematicsolutions/prawo-pl-mcp && cd prawo-pl-mcp
uv sync --extra dev
uv run pytest          # offline tests: registry, dispatch mapping, pagination, drift
uv run prawo-pl-mcp    # stdio server
```

## License

Apache-2.0. Individual connectors carry their own licenses (MIT or Apache-2.0),
their own rate limits and their own terms toward upstream databases - the
aggregator adds no caching and no transformation beyond pagination, so each
connector's constraints apply unchanged.
