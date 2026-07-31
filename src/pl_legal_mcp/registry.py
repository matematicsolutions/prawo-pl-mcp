"""Registry zrodel - jedyne miejsce, ktore trzeba edytowac przy dodaniu konektora.

Kazde zrodlo = osobny konektor MCP (osobne repo/pakiet), spawnowany lazy przez
npx/uvx. Mapowania parametrow unified -> natywne odzwierciedlaja FAKTYCZNE
schematy z kodu konektorow (ekstrakcja 2026-07-31), nie dokumentacje.

Niespojnosci floty normalizowane tutaj:
- daty: dateFrom/dateTo (saos, nsa) vs date_from/date_to (eureka, kio, uodo, eu-sparql)
- paginacja: pageNumber od 0 (saos) / od 1 (nsa), page od 0 (eureka) / od 1 (kio, uodo)
- rozmiar strony: pageSize / page_size / size / limit
Unified: `page` ZAWSZE od 1, `limit` = rozmiar strony (clamp do size_max).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchSpec:
    tool: str
    query_param: str | None = None
    date_from_param: str | None = None
    date_to_param: str | None = None
    page_param: str | None = None
    page_base: int = 1  # 0 = natywna paginacja liczona od 0
    size_param: str | None = None
    size_max: int | None = None
    required_extra: tuple[str, ...] = ()  # natywne parametry wymagane przez konektor


@dataclass(frozen=True)
class GetSpec:
    tool: str
    id_param: str
    id_hint: str
    required_extra: tuple[str, ...] = ()


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    coverage: str
    group: str  # "pl" | "eu"
    runtime: str  # "npx" | "uvx"
    package: str
    search: SearchSpec | None
    get: GetSpec
    native_tools: tuple[str, ...]
    notes: str = ""


SOURCES: dict[str, Source] = {
    s.id: s
    for s in [
        Source(
            id="saos",
            name="SAOS - courts of general jurisdiction + Supreme Court + Constitutional Tribunal",
            coverage="Polish case law from saos.org.pl (common courts, Supreme Court, "
            "Constitutional Tribunal, National Appeal Chamber). Includes citator "
            "(saos_cite_check - is the ruling still good law).",
            group="pl",
            runtime="npx",
            package="@matematicsolutions/mcp-saos",
            search=SearchSpec(
                tool="search",
                query_param="all",
                date_from_param="dateFrom",
                date_to_param="dateTo",
                page_param="pageNumber",
                page_base=0,
                size_param="pageSize",
                size_max=100,
            ),
            get=GetSpec(
                tool="get_judgment",
                id_param="id",
                id_hint="numeric SAOS judgment id from search results; for a case "
                "signature use pl_call tool=search_by_case",
            ),
            native_tools=("search", "get_judgment", "search_by_case", "saos_cite_check"),
            notes="pageSize min=10. courtType enum: COMMON|SUPREME|CONSTITUTIONAL_TRIBUNAL|"
            "NATIONAL_APPEAL_CHAMBER (pass via extra).",
        ),
        Source(
            id="nsa",
            name="NSA/WSA - administrative courts (CBOSA)",
            coverage="Administrative court rulings from orzeczenia.nsa.gov.pl "
            "(Supreme Administrative Court + 16 voivodeship courts). HTML scraping.",
            group="pl",
            runtime="npx",
            package="@matematicsolutions/mcp-nsa",
            search=SearchSpec(
                tool="search",
                query_param="query",
                date_from_param="dateFrom",
                date_to_param="dateTo",
                page_param="pageNumber",
                page_base=1,
                size_param=None,  # CBOSA zawsze 10/strone
            ),
            get=GetSpec(
                tool="get_judgment",
                id_param="doc_id",
                id_hint="10-char hex doc_id from search results (e.g. 7E50984BB7)",
            ),
            native_tools=("search", "get_judgment", "search_by_case"),
            notes="Fixed 10 results/page. court filter (extra) takes full Polish court "
            "names with diacritics, e.g. 'Wojewódzki Sąd Administracyjny w Krakowie'.",
        ),
        Source(
            id="isap",
            name="ISAP/ELI - Polish legislation (Dziennik Ustaw, Monitor Polski)",
            coverage="96k+ legal acts via the official Sejm ELI API. Metadata + full text.",
            group="pl",
            runtime="npx",
            package="@matematicsolutions/mcp-isap",
            search=SearchSpec(
                tool="search_acts",
                query_param="title",
                size_param="limit",
                size_max=50,
            ),
            get=GetSpec(
                tool="get_act_text",
                id_param="eli",
                id_hint="ELI identifier PUBLISHER/YEAR/POSITION, e.g. DU/2018/1000",
            ),
            native_tools=("search_acts", "get_act", "get_act_text"),
            notes="No date-range params - filter by year (number, via extra). "
            "Act metadata via pl_call tool=get_act.",
        ),
        Source(
            id="krs",
            name="KRS - National Court Register (companies, foundations)",
            coverage="Company register extracts from the official Ministry of Justice "
            "API (api-krs.ms.gov.pl). Current + full historical extract, board "
            "composition.",
            group="pl",
            runtime="npx",
            package="@matematicsolutions/mcp-krs",
            search=None,  # brak search - rejestr odpytywany po numerze KRS
            get=GetSpec(
                tool="get_entity",
                id_param="krs",
                id_hint="KRS number (1-10 digits, auto-padded). Full historical extract: "
                "pl_call tool=get_entity_full; board only: pl_call tool=get_board",
            ),
            native_tools=("get_entity", "get_entity_full", "get_board"),
            notes="No search tool - you need the KRS number. rejestr: P (entrepreneurs, "
            "default) | S (associations/foundations), pass via extra.",
        ),
        Source(
            id="eureka",
            name="EUREKA - individual tax interpretations (KIS/MF)",
            coverage="550k+ tax rulings from the Ministry of Finance EUREKA system.",
            group="pl",
            runtime="npx",
            package="@matematicsolutions/mcp-eureka",
            search=SearchSpec(
                tool="search",
                query_param="query",
                date_from_param="date_from",
                date_to_param="date_to",
                page_param="page",
                page_base=0,
                size_param="page_size",
                size_max=50,
            ),
            get=GetSpec(
                tool="get_interpretation",
                id_param="id",
                id_hint="ID_INFORMACJI from search results; for a signature use "
                "pl_call tool=search_by_signature",
            ),
            native_tools=("search", "get_interpretation", "search_by_signature", "list_categories"),
            notes="Category dictionary via pl_call tool=list_categories.",
        ),
        Source(
            id="kio",
            name="KIO - National Appeal Chamber (public procurement)",
            coverage="KIO rulings from orzeczenia.uzp.gov.pl. Search by PZP article, "
            "recent rulings, PDF URLs.",
            group="pl",
            runtime="uvx",
            package="kio-orzeczenia-mcp",
            search=SearchSpec(
                tool="kio_search",
                query_param="phrase",
                date_from_param="date_from",
                date_to_param="date_to",
                page_param="page",
                page_base=1,
                size_param="size",
                size_max=100,
            ),
            get=GetSpec(
                tool="kio_get_orzeczenie",
                id_param="signature_or_id",
                id_hint="case signature 'KIO 2924/21' or internal numeric id",
            ),
            native_tools=(
                "kio_search",
                "kio_get_orzeczenie",
                "kio_recent",
                "kio_by_pzp_article",
                "kio_get_pdf_url",
            ),
            notes="Rate limit 1 req/s upstream. Rulings by PZP article: "
            "pl_call tool=kio_by_pzp_article.",
        ),
        Source(
            id="uodo",
            name="UODO - Polish DPA decisions (GDPR enforcement)",
            coverage="Decisions of the President of UODO from orzeczenia.uodo.gov.pl, "
            "incl. fines, sectors, GDPR article index, aggregate stats.",
            group="pl",
            runtime="uvx",
            package="uodo-orzeczenia-mcp",
            search=SearchSpec(
                tool="uodo_search",
                query_param="keyword",
                date_from_param="date_from",
                date_to_param="date_to",
                page_param="page",
                page_base=1,
                size_param="size",
                size_max=50,
            ),
            get=GetSpec(
                tool="uodo_get_decision",
                id_param="urn_or_signature",
                id_hint="URN or signature, e.g. DKN.5131.16.2025",
            ),
            native_tools=(
                "uodo_search",
                "uodo_get_decision",
                "uodo_recent",
                "uodo_by_gdpr_article",
                "uodo_stats",
            ),
            notes="Stats (fines, sectors) via pl_call tool=uodo_stats "
            "(period_from/period_to required).",
        ),
        Source(
            id="eu-sparql",
            name="EUR-Lex / CJEU - EU law via SPARQL (Cellar)",
            coverage="EU legislation by CELEX, CJEU case law by ECLI or full-text, "
            "GDPRhub decisions. Languages: POL|ENG|FRA|DEU.",
            group="eu",
            runtime="npx",
            package="@matematicsolutions/mcp-eu-sparql",
            search=SearchSpec(
                tool="search_cjeu",
                query_param="query",
                date_from_param="date_from",
                date_to_param="date_to",
                size_param="limit",
                size_max=50,
            ),
            get=GetSpec(
                tool="search_by_celex",
                id_param="celex",
                id_hint="CELEX number (e.g. 32016R0679); for ECLI use "
                "pl_call tool=search_cjeu_by_ecli",
            ),
            native_tools=(
                "search_by_celex",
                "search_by_date_range",
                "search_cjeu",
                "search_cjeu_by_ecli",
                "search_gdprhub",
            ),
            notes="No page param - limit only. pl_search maps to CJEU case-law search; "
            "legislation by date range via pl_call tool=search_by_date_range.",
        ),
        Source(
            id="eu-compliance",
            name="EU compliance corpus - 14 regulations offline (GDPR, AI Act, DORA...)",
            coverage="Verbatim article lookup + FTS across GDPR, AI_ACT, DORA, NIS2, "
            "EIDAS2, CRA, DSA, DMA, DATA_ACT, DGA, LED, EPRIVACY, CYBERSECURITY_ACT, "
            "CER. Offline SQLite corpus (downloaded on connector's first start).",
            group="eu",
            runtime="npx",
            package="@matematicsolutions/mcp-eu-compliance",
            search=SearchSpec(
                tool="eu_search",
                query_param="query",
                size_param="limit",
                size_max=25,
            ),
            get=GetSpec(
                tool="eu_article",
                id_param="article_number",
                id_hint="article number (e.g. '33'); REQUIRES extra={'regulation': 'GDPR'} "
                "(enum of 14 regulations)",
                required_extra=("regulation",),
            ),
            native_tools=("eu_search", "eu_article", "eu_compare", "eu_check_applicability", "eu_evidence"),
            notes="Cross-regulation comparison via pl_call tool=eu_compare; "
            "applicability screening via pl_call tool=eu_check_applicability.",
        ),
        Source(
            id="legalize",
            name="Legalize - law-as-git corpus (32 jurisdictions, 21 EU)",
            coverage="Versioned national legislation as Markdown from legalize-dev; "
            "historical versions by commit SHA, reform timelines.",
            group="eu",
            runtime="uvx",
            package="legalize-mcp",
            search=SearchSpec(
                tool="legalize_search_laws",
                query_param="query",
                size_param="limit",
                size_max=100,
                required_extra=("country",),
            ),
            get=GetSpec(
                tool="legalize_get_law",
                id_param="law_id",
                id_hint="law_id (filename stem, e.g. BOE-A-1978-31229); REQUIRES "
                "extra={'country': 'es'} (ISO alpha-2 lowercase)",
                required_extra=("country",),
            ),
            native_tools=(
                "legalize_list_countries",
                "legalize_search_laws",
                "legalize_get_law",
                "legalize_get_meta",
                "legalize_list_reforms",
            ),
            notes="legalize_search_laws needs a GitHub token (code search). "
            "Reform timeline via pl_call tool=legalize_list_reforms.",
        ),
    ]
}


def get_source(source_id: str) -> Source | None:
    return SOURCES.get(source_id.strip().lower())


def catalog(group: str | None = None) -> list[dict]:
    """Katalog zrodel bez spawnu czegokolwiek (dla pl_list_sources)."""
    out = []
    for s in SOURCES.values():
        if group and s.group != group:
            continue
        entry = {
            "id": s.id,
            "name": s.name,
            "group": s.group,
            "coverage": s.coverage,
            "runtime": f"{s.runtime}:{s.package}",
            "searchable": s.search is not None,
            "document_id": s.get.id_hint,
            "native_tools": list(s.native_tools),
        }
        if s.notes:
            entry["notes"] = s.notes
        out.append(entry)
    return out
