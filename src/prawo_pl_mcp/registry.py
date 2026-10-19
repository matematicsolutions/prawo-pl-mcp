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
    # Zrodlo stronicuje przez limit/offset zamiast page/pageNumber. Wtedy
    # unified `page` nie ma gdzie trafic przez page_param - liczymy offset.
    offset_param: str | None = None
    size_param: str | None = None
    size_max: int | None = None
    size_min: int | None = None  # np. SAOS pageSize min=10 - clamp zamiast cichego ignorowania
    required_extra: tuple[str, ...] = ()  # natywne parametry wymagane przez konektor


@dataclass(frozen=True)
class GetSpec:
    tool: str
    id_param: str
    id_hint: str
    required_extra: tuple[str, ...] = ()
    # Zrodlo samo stronicuje tresc dokumentu (np. isap: dlugi kodeks). Wtedy
    # unified `page` idzie do konektora, a agregator NIE tnie tego drugi raz -
    # inaczej `total_pages` liczyloby strony jednej strony zrodla i klamalo.
    page_param: str | None = None


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
                size_min=10,
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
                page_param="page",
            ),
            native_tools=("search_acts", "get_act", "get_act_text"),
            notes="Needs mcp-isap >= 1.3.0 (native `page` on get_act_text; older "
            "builds silently ignore it and always return the first page). "
            "No date-range params - filter by year (number, via extra). "
            "Act metadata via pl_call tool=get_act. Long acts are paginated by the "
            "connector itself - jump straight to an article with "
            "extra={'search_text': 'Art. 118.'}. The HTML of a BASE act is the text "
            "AS PROMULGATED, not consolidated; for the wording in force fetch the "
            "newest 'obwieszczenie' (tekst jednolity) the connector points to.",
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
        Source(
            id="law-scrapper",
            name="Law Scrapper MCP - ISAP/ELI legislation with relationship graph",
            coverage="Polish legal acts (DU/MP) with amendment/reference graph, "
            "result-set filtering, change tracking and legal-date math. Upstream is "
            "the same api.sejm.gov.pl as `isap` - only the delta below justifies it.",
            group="pl",
            runtime="git-uvx",
            package="git+https://github.com/numikel/law-scrapper-mcp law-scrapper",
            search=SearchSpec(
                tool="search_legal_acts",
                query_param="keywords",
                date_from_param="date_from",
                date_to_param="date_to",
                offset_param="offset",
                size_param="limit",
            ),
            get=GetSpec(
                tool="get_act_details",
                id_param="eli",
                id_hint="ELI identifier DU/YYYY/POS, e.g. DU/2024/1. Metadata + TOC only - "
                "text needs pl_call tool=read_act_content(eli, section). `search_in_act` "
                "greps within an act.",
            ),
            native_tools=(
                "get_system_metadata",
                "search_legal_acts",
                "browse_acts",
                "get_act_details",
                "read_act_content",
                "list_loaded_documents",
                "search_in_act",
                "analyze_act_relationships",
                "track_legal_changes",
                "calculate_legal_date",
                "filter_results",
                "list_result_sets",
                "compare_acts",
            ),
            notes="SCOPE: prefer `isap` for ordinary act search/fetch - this entry exists "
            "only for the 4 capabilities isap lacks: analyze_act_relationships, "
            "track_legal_changes, filter_results (complete-vs-page scope), "
            "calculate_legal_date. Prefer pl_call for those. Content is TWO-STEP: "
            "pl_get_document returns metadata + TOC, not text; the body comes from "
            "pl_call tool=read_act_content. Pagination is limit/offset (not page), so "
            "`page`/`limit` are translated to offset arithmetic - pass native values "
            "via extra to be explicit. Runs from git (not on PyPI): needs network on "
            "first call. Single-maintainer dependency - pin by commit SHA when stable.",
        ),
        Source(
            id="echr",
            name="ECHR / ETPC - European Court of Human Rights case law (HUDOC)",
            coverage="Judgments, decisions and advisory opinions of the European Court of "
            "Human Rights from the official HUDOC database, in EN/FR (and the Court's "
            "other languages). Search by application number, Convention article, "
            "document type and key date; full judgment text as plain text. The only "
            "connector in the fleet covering the Strasbourg court.",
            group="eu",
            runtime="git-uvx",
            package="git+https://github.com/pawelknorps/echr-mcp echr-mcp",
            search=SearchSpec(
                tool="search_judgments",
                query_param="query",
                date_from_param="kpdate_from",
                date_to_param="kpdate_to",
                offset_param="offset",
                size_param="limit",
                size_max=100,
            ),
            get=GetSpec(
                tool="get_judgment_text",
                id_param="itemid",
                id_hint="HUDOC itemid from search results (e.g. '001-250747'); the "
                "connector resolves the requested language, then falls back to a "
                "same-kind sibling when the itemid is a placeholder. Read the document "
                "name from the search hit first.",
            ),
            native_tools=(
                "search_judgments",
                "get_judgment_text",
                "list_hudoc_filters",
                "echr_coverage",
            ),
            notes="Scope: the ECHR itself (Strasbourg), NOT EU law - use eu-sparql for "
            "CJEU and eu-compliance for EU regulations. `query` free text works only as "
            "a bracketed phrase; structured filters (`appno`, `article`, `doctype`, "
            "date range) are more reliable - pass them via extra using the native names "
            "listed in native_params (extra={'appno': '474/21'}). Enumerations for "
            "doctype/article/collection are static via pl_call tool=list_hudoc_filters. "
            "Pagination is limit/offset (HUDOC start/length), so `page`/`limit` are "
            "translated to offset arithmetic. Runs from git (not on PyPI): needs network "
            "on first call. Single-maintainer dependency - pin by commit SHA when stable.",
        ),
        Source(
            id="sejm-process",
            name="Sejm - legislative process (draft bills, stages, prints)",
            coverage="The legislative track of draft bills and resolutions in the Sejm "
            "(lower chamber): per-term project lists, the full stage timeline of a "
            "process (readings, committee referrals, votes with yes/no/abstain, Senate "
            "position) and parliamentary prints with attachment URLs. Official "
            "api.sejm.gov.pl REST API. This is the *process*, not the enacted text.",
            group="pl",
            runtime="git-uvx",
            package="git+https://github.com/pawelknorps/sejm-process-mcp sejm-process-mcp",
            search=SearchSpec(
                tool="search_drafts",
                query_param="query",
                date_from_param="date_from",
                date_to_param="date_to",
                offset_param="offset",
                size_param="limit",
                size_max=500,
            ),
            get=GetSpec(
                tool="get_process",
                id_param="number",
                id_hint="process number from search_drafts (e.g. '32'); it is a key only "
                "WITHIN a term, so pass the same term via extra={'term': '10'} (default "
                "'10' is the current term). For a print, pl_call tool=get_print with "
                "extra={'term': ..., 'number': ...}.",
            ),
            native_tools=(
                "search_drafts",
                "get_process",
                "get_print",
                "sejm_coverage",
            ),
            notes="Scope split: this is the legislative PROCESS; the enacted text lives in "
            "`isap`/`eli`. The Sejm API has no server-side search, so `search_drafts` "
            "filters ONE fetched page (limit, default 50) client-side - a query can miss "
            "matches on a later page; page through with `page`/`limit` or widen the date "
            "range. `document_type` matching is substring and case-sensitive on Polish "
            "stemming ('ustawy' hits, 'ustawa' does not). The key is `number` + `term`, "
            "not ELI. Pagination is limit/offset, so `page`/`limit` are translated to "
            "offset arithmetic. Runs from git (not on PyPI): needs network on first "
            "call. Single-maintainer dependency - pin by commit SHA when stable.",
        ),
    ]
}


def get_source(source_id: str) -> Source | None:
    return SOURCES.get(source_id.strip().lower())


def offset_for(spec: SearchSpec, page: int, limit: int | None) -> int:
    """Offset dla zrodel stronicujacych limit/offset. `page` jest 1-based.

    Rozmiar strony: jawny `limit`, inaczej size_max, inaczej 20. Bez tego
    unified `page` nie mialby jak trafic do zrodla bez page_param.
    """
    page_size = limit if limit is not None else (spec.size_max or 20)
    return (page - 1) * page_size


def native_params(s: Source) -> dict:
    """Na jakie NATYWNE nazwy tlumaczy sie kazdy parametr unified.

    Bez tego natywna nazwa (np. `article_number` w eu_article) byla widoczna
    dopiero w bledzie upstreamu - trzeba bylo zgadnac albo zaplacic za spawn
    konektora przez pl_list_sources(source_id=...). Zrodlo prawdy to ten sam
    registry, ktory robi dispatch, wiec pole nie moze zdryfowac od zachowania.
    """
    out: dict[str, dict] = {}
    if s.search is not None:
        sp = s.search
        entry: dict = {"tool": sp.tool}
        if sp.query_param:
            entry["query"] = sp.query_param
        if sp.date_from_param:
            entry["date_from"] = sp.date_from_param
        if sp.date_to_param:
            entry["date_to"] = sp.date_to_param
        if sp.page_param:
            entry["page"] = sp.page_param
            entry["page_base"] = sp.page_base  # unified `page` zawsze od 1
        if sp.offset_param:
            entry["page"] = sp.offset_param
            entry["pagination"] = "offset"  # unified `page` liczy offset z rozmiaru strony
        if sp.size_param:
            entry["limit"] = sp.size_param
            if sp.size_max is not None:
                entry["limit_max"] = sp.size_max
            if sp.size_min is not None:
                entry["limit_min"] = sp.size_min
        if sp.required_extra:
            entry["required_extra"] = list(sp.required_extra)
        out["pl_search"] = entry

    g = s.get
    get_entry: dict = {"tool": g.tool, "document_id": g.id_param}
    if g.page_param:
        get_entry["page"] = g.page_param
        get_entry["pagination"] = "native"
    if g.required_extra:
        get_entry["required_extra"] = list(g.required_extra)
    out["pl_get_document"] = get_entry
    return out


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
            "native_params": native_params(s),
        }
        if s.notes:
            entry["notes"] = s.notes
        out.append(entry)
    return out
