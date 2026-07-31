# ADR 0001: Agregacja przez proxy MCP (stdio), nie monorepo-import

Data: 2026-07-31 | Status: zaakceptowany (decyzja robocza, finalna nazwa i publikacja = decyzja WM)

## Kontekst

Flota matematicsolutions to 12+ osobnych konektorow MCP dla polskich (i unijnych) zrodel
prawnych. Analiza legal-oss.com (2026-07-31) pokazala, ze jeden zbiorczy serwer w stylu
saidsurucu/yargi-mcp (16 instytucji tureckich, 1,1k gwiazdek, MIT) ma lepsza widocznosc
niz rozproszona flota. Konektory ZOSTAJA osobnymi repo (modularnosc, konstytucja fabryki
eu-legal-mcp: "Factory, not monolith"); pl-legal-mcp jest cienka warstwa agregujaca.

Rozwazane opcje:

1. **Monorepo w stylu yargi-mcp** - skopiowac kod klientow do jednego repo, toole
   rejestrowane wprost (`mcp_server_main.py`, ~2400 linii u yargi).
2. **Monorepo-import** - pl-legal-mcp zalezy od pakietow konektorow, importuje ich
   instancje FastMCP i montuje in-process (`mcp.mount()`).
3. **Proxy** - pl-legal-mcp spawnuje konektory jako podprocesy stdio (`npx -y ...` /
   `uvx ...`) i rozmawia z nimi protokolem MCP przez `fastmcp.Client`.

## Decyzja

**Opcja 3 (proxy stdio) + warstwa unified tools.** Konsolidacja interfejsu w stylu
yargi (42 natywne toole registry v0.1 -> 4 unified), ale bez kopiowania i bez importowania kodu.

## Uzasadnienie

- **Mieszany stack wyklucza opcje 2.** Polowa floty to TypeScript-owe monolity
  (`src/index.ts`: mcp-saos, mcp-nsa, mcp-isap, mcp-krs, mcp-eureka, mcp-eu-sparql,
  mcp-eu-compliance) - nieimportowalne z Pythona. Importowalne sa tylko pakiety
  Python (kio, uodo, sejm-eli, legalize, boutique). Monorepo-import dalby dwa rezimy
  agregacji w jednym serwerze; proxy traktuje wszystkie 12 identycznie.
- **Opcja 1 lamie ADR floty.** Kopiowanie kodu = drift 12 kopii vs 12 repo zrodlowych;
  konstytucja fabryki mowi wprost: wspoldzielony jest szkielet, nie proces.
- **Proxy = zero-maintenance przy release konektora.** `npx -y` / `uvx` pobieraja
  ZAWSZE aktualna opublikowana wersje; meta-pakiet nie pinuje zaleznosci i nie musi
  byc wydawany przy kazdym release konektora. Nowe zrodlo = jeden wpis w registry.
- **Granica procesu = granica awarii.** Pad jednego konektora (np. scraping CBOSA
  po zmianie HTML) nie klade calego agregatora; blad wraca jako `upstream_error`
  danego zrodla.
- **Parytet z regula lazy-provisioning** ([[feedback_korpusowy_konektor_lazy_provisioning_obowiazkowy]]):
  zaden tool nie moze bledowac "konektor niezainstalowany". Drabinka:
  `env override (PL_LEGAL_MCP_CMD_<ID>) -> zywa sesja w puli -> spawn uvx/npx
  (sam pobiera pakiet przy 1. uzyciu) -> czytelny blad source_unavailable`.

## Konsekwencje

- (+) Cienka warstwa: registry + pula klientow + 4 toole + instructions. Bez logiki domenowej.
- (+) Konektory rozwijaja sie niezaleznie; agregator podaza za wersjami z npm/PyPI.
- (-) Wymaga Node >= 18 **i** uv na maszynie klienta (dokumentowane w README; brak
  ktoregos = zrodla danego runtime raportowane jako niedostepne, reszta dziala).
- (-) Pierwsze wywolanie zrodla placi koszt spawnu + pobrania pakietu (sekundy);
  potem sesja zyje w puli (keep-alive).
- (-) Latencja hopu stdio (~ms) - pomijalna vs latencja upstream API.
- Unifikacja parametrow wymaga mapowania per zrodlo (registry), a specjalistyczne
  toole (cite_check, stats, get_board) dostepne przez escape hatch `pl_call` -
  bez wrapowania kazdego toola z osobna.

## Odniesienia

- yargi-mcp: monorepo, unified tools przez parametr dyskryminujacy
  (`search_bedesten_unified(court_types=...)`), paginacja 5000 znakow/strona,
  deklarowane -61,8% tokenow na schematach. Lekcje przejete: unified tools,
  paginacja, tryby stdio+ASGI. Lekcja odrzucona: monolit kodu.
- FastMCP composition: `mount()` (live-link, prefiksy) odrzucone - montowanie
  wszystkich sub-serwerow wystawia 42 toole i placi list_tools u kazdego; unified
  dispatch jest tanszy tokenowo i zgodny z lekcja yargi.
