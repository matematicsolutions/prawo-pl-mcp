# ADR 0001: Agregacja przez proxy MCP (stdio), nie monorepo-import

Data: 2026-07-31 | Status: zaakceptowany

## Kontekst

MateMatic prowadzi kilkanascie osobnych konektorow MCP do polskich i unijnych zrodel
prawnych. Kazdy jest osobna instalacja i osobnym wpisem w konfiguracji klienta, wiec
odpowiedz na jedno pytanie prawne kosztuje dziesiec instalacji. saidsurucu/yargi-mcp
(16 tureckich instytucji w jednym serwerze, MIT) pokazal, ze zbiorczy serwer krajowy
jest lepiej widoczny niz rozproszona flota. Konektory zostaja osobnymi repozytoriami -
prawo-pl-mcp to cienka warstwa agregujaca, nie ich nastepca.

Rozwazane opcje:

1. **Monorepo w stylu yargi-mcp** - skopiowac kod klientow do jednego repo, toole
   rejestrowane wprost (`mcp_server_main.py`, ~2400 linii u yargi).
2. **Monorepo-import** - prawo-pl-mcp zalezy od pakietow konektorow, importuje ich
   instancje FastMCP i montuje in-process (`mcp.mount()`).
3. **Proxy** - prawo-pl-mcp spawnuje konektory jako podprocesy stdio (`npx -y ...` /
   `uvx ...`) i rozmawia z nimi protokolem MCP przez `fastmcp.Client`.

## Decyzja

**Opcja 3 (proxy stdio) + warstwa unified tools.** Konsolidacja interfejsu w stylu
yargi (42 natywne toole registry v0.1 -> 4 unified), ale bez kopiowania i bez importowania kodu.

## Uzasadnienie

- **Mieszany stack wyklucza opcje 2.** Polowa floty to TypeScript-owe monolity
  (`src/index.ts`: mcp-saos, mcp-nsa, mcp-isap, mcp-krs, mcp-eureka, mcp-eu-sparql,
  mcp-eu-compliance) - nieimportowalne z Pythona. Importowalne sa tylko pakiety
  Python (kio, uodo, legalize). Monorepo-import dalby dwa rezimy agregacji w jednym
  serwerze; proxy traktuje wszystkie 10 zrodel identycznie.
- **Opcja 1 lamie zasade linii produkcyjnej konektorow.** Kopiowanie kodu to drift
  10 kopii wobec 10 repo zrodlowych; wspoldzielony ma byc szkielet, nie proces.
- **Wydanie konektora nie wymaga wydania agregatora.** `npx -y` / `uvx` pobieraja
  zawsze aktualna opublikowana wersje; meta-pakiet nie pinuje zaleznosci. Nowe
  zrodlo to jeden wpis w registry.
- **Granica procesu = granica awarii.** Pad jednego konektora (np. scraping CBOSA
  po zmianie HTML) nie klade calego agregatora; blad wraca jako `upstream_error`
  danego zrodla.
- **Lazy-provisioning jest obowiazkowy** (regula floty): zaden tool nie moze
  bledowac "konektor niezainstalowany" jako normalny stan swiezej instalacji. Drabinka:
  `env override (PRAWO_PL_MCP_CMD_<ID>) -> zywa sesja w puli -> spawn uvx/npx
  (sam pobiera pakiet przy 1. uzyciu) -> czytelny blad source_unavailable`.

## Konsekwencje

- (+) Warstwa zostaje cienka: registry, pula klientow, 4 toole, instructions.
  Zero logiki domenowej po naszej stronie.
- (+) Konektory rozwijaja sie niezaleznie, a agregator podaza za wersjami z npm i PyPI.
- (-) Klient potrzebuje Node 18+ oraz uv. Brak jednego z nich wycina zrodla tego
  runtime (raportowane jako `source_unavailable`), reszta dziala.
- (-) Pierwsze wywolanie zrodla placi za spawn i pobranie pakietu, czyli sekundy.
  Potem sesja zyje w puli.
- (-) Dochodzi hop stdio liczony w milisekundach. Wobec latencji SAOS czy CBOSA
  to szum.
- (-) Unifikacja parametrow wymaga mapowania per zrodlo w registry. Toole
  specjalistyczne (`saos_cite_check`, `uodo_stats`, `get_board`) ida przez
  `pl_call`, zeby nie wrapowac kazdego z osobna.

## Odniesienia

- yargi-mcp: monorepo, unified tools przez parametr dyskryminujacy
  (`search_bedesten_unified(court_types=...)`), paginacja 5000 znakow/strona,
  deklarowane -61,8% tokenow na schematach. Lekcje przejete: unified tools,
  paginacja, tryby stdio+ASGI. Lekcja odrzucona: monolit kodu.
- FastMCP composition: `mount()` (live-link, prefiksy) odrzucone - montowanie
  wszystkich sub-serwerow wystawia 42 toole i placi list_tools u kazdego; unified
  dispatch jest tanszy tokenowo i zgodny z lekcja yargi.
