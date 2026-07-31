"""Sanity registry - offline, zero spawnu."""

from __future__ import annotations

from pl_legal_mcp.registry import SOURCES, catalog, get_source


def test_ids_unique_and_lowercase():
    assert all(s.id == s.id.lower() for s in SOURCES.values())
    assert len(SOURCES) == len({s.id for s in SOURCES.values()})


def test_runtime_valid():
    assert all(s.runtime in ("npx", "uvx") for s in SOURCES.values())


def test_groups_valid():
    assert all(s.group in ("pl", "eu") for s in SOURCES.values())


def test_core_pl_sources_present():
    for expected in ("saos", "nsa", "isap", "krs", "eureka", "kio", "uodo"):
        assert expected in SOURCES, f"Brak zrodla '{expected}' w registry"


def test_search_specs_consistent():
    for s in SOURCES.values():
        if s.search is None:
            continue
        assert s.search.tool in s.native_tools, f"{s.id}: search tool spoza native_tools"
        assert s.search.page_base in (0, 1)
        if s.search.size_max is not None:
            assert s.search.size_param is not None


def test_get_specs_consistent():
    for s in SOURCES.values():
        assert s.get.tool in s.native_tools, f"{s.id}: get tool spoza native_tools"
        assert s.get.id_param
        assert s.get.id_hint


def test_required_extra_documented_in_hint_or_notes():
    for s in SOURCES.values():
        for param in s.get.required_extra:
            assert param in s.get.id_hint, (
                f"{s.id}: required extra '{param}' nieudokumentowane w id_hint"
            )


def test_get_source_normalizes():
    assert get_source("SAOS") is SOURCES["saos"]
    assert get_source(" kio ") is SOURCES["kio"]
    assert get_source("nope") is None


def test_catalog_group_filter():
    assert {e["group"] for e in catalog("pl")} == {"pl"}
    assert {e["group"] for e in catalog("eu")} == {"eu"}
    assert len(catalog()) == len(SOURCES)
