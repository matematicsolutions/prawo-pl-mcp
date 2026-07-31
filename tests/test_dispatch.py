"""Dispatch unified -> natywne parametry. Offline - POOL.call mockowany."""

from __future__ import annotations

import json

import pytest

import prawo_pl_mcp.server as srv
from prawo_pl_mcp.server import (
    PLLegalError,
    pl_call,
    pl_get_document,
    pl_list_sources,
    pl_search,
)


class _CapturePool:
    def __init__(self, response: str = "ok"):
        self.calls: list[tuple[str, str, dict]] = []
        self.response = response
        # tool -> input_schema; puste = konektor nie deklaruje schematu
        self.schemas: dict[str, dict] = {}
        self.list_tools_calls = 0

    async def call(self, source, tool, arguments):
        self.calls.append((source.id, tool, arguments))
        return self.response

    async def list_tools(self, source, use_cache: bool = False):
        self.list_tools_calls += 1
        return [
            {"name": t, "description": "", "input_schema": self.schemas.get(t, {})}
            for t in source.native_tools
        ]


@pytest.fixture()
def pool(monkeypatch):
    cap = _CapturePool()
    monkeypatch.setattr(srv, "POOL", cap)
    return cap


async def test_saos_search_maps_camelcase_and_zero_based_page(pool):
    await pl_search("saos", query="skarga", date_from="2024-01-01", page=2, limit=200)
    sid, tool, args = pool.calls[0]
    assert (sid, tool) == ("saos", "search")
    assert args["all"] == "skarga"
    assert args["dateFrom"] == "2024-01-01"
    assert args["pageNumber"] == 1  # unified page=2 -> natywnie od 0
    assert args["pageSize"] == 100  # clamp do size_max


async def test_saos_limit_below_native_minimum_is_raised(pool):
    await pl_search("saos", query="x", limit=3)
    _, _, args = pool.calls[0]
    assert args["pageSize"] == 10  # SAOS odrzuca/ignoruje pageSize < 10


async def test_kio_search_maps_snakecase_one_based(pool):
    await pl_search("kio", query="rażąco niska cena", page=3, limit=10)
    _, tool, args = pool.calls[0]
    assert tool == "kio_search"
    assert args["phrase"] == "rażąco niska cena"
    assert args["page"] == 3
    assert args["size"] == 10


async def test_extra_passthrough_wins_over_common(pool):
    await pl_search("saos", query="x", extra={"all": "override", "courtType": "SUPREME"})
    _, _, args = pool.calls[0]
    assert args["all"] == "override"  # extra ma pierwszenstwo (setdefault)
    assert args["courtType"] == "SUPREME"


async def test_krs_has_no_search():
    with pytest.raises(PLLegalError) as e:
        await pl_search("krs", query="MateMatic")
    assert e.value.code == "invalid_arg"


async def test_isap_rejects_dates():
    with pytest.raises(PLLegalError) as e:
        await pl_search("isap", query="RODO", date_from="2020-01-01")
    assert e.value.code == "invalid_arg"


async def test_legalize_requires_country():
    with pytest.raises(PLLegalError) as e:
        await pl_search("legalize", query="constitucion")
    assert e.value.code == "invalid_arg"
    assert "country" in str(e.value)


async def test_unknown_source():
    with pytest.raises(PLLegalError) as e:
        await pl_search("cbosa", query="x")
    assert e.value.code == "unknown_source"


async def test_get_document_paginates_and_wraps(pool):
    pool.response = "A" * 12000
    raw = await pl_get_document("nsa", "7E50984BB7")
    page = json.loads(raw)
    assert page["source"] == "nsa"
    assert page["total_pages"] == 3
    assert page["has_more"] is True
    _, tool, args = pool.calls[0]
    assert tool == "get_judgment"
    assert args["doc_id"] == "7E50984BB7"


async def test_eu_compliance_get_requires_regulation(pool):
    with pytest.raises(PLLegalError) as e:
        await pl_get_document("eu-compliance", "33")
    assert e.value.code == "invalid_arg"

    await pl_get_document("eu-compliance", "33", extra={"regulation": "GDPR"})
    _, tool, args = pool.calls[0]
    assert (tool, args["regulation"], args["article_number"]) == ("eu_article", "GDPR", "33")


async def test_list_sources_catalog_offline(pool):
    raw = await pl_list_sources()
    data = json.loads(raw)
    assert len(data["sources"]) >= 10
    assert pool.calls == []  # katalog nie spawnuje niczego


# ---------- spojnosc nazw parametrow (dogfooding 2026-07-31) ----------


async def test_page_is_the_same_name_in_search_and_get(pool):
    """Model, ktory nauczyl sie `page` w pl_search, nie moze dostac bledu w get."""
    await pl_search("kio", query="x", page=2)
    await pl_get_document("nsa", "7E50984BB7", page=1)
    assert pool.calls[0][2]["page"] == 2


async def test_page_number_alias_still_works_in_get(pool):
    pool.response = "A" * 12000
    raw = await pl_get_document("nsa", "7E50984BB7", page_number=2)
    out = json.loads(raw)
    assert out["page"] == 2
    assert out["page_number"] == 2  # alias echo - stary klient nie peka


async def test_page_number_alias_also_accepted_in_search(pool):
    await pl_search("kio", query="x", page_number=4)
    assert pool.calls[0][2]["page"] == 4


async def test_conflicting_page_and_page_number_is_an_error():
    with pytest.raises(PLLegalError) as e:
        await pl_get_document("nsa", "X", page=3, page_number=7)
    assert e.value.code == "invalid_arg"
    assert "page_number" in str(e.value)


async def test_get_document_page_must_be_one_based():
    with pytest.raises(PLLegalError) as e:
        await pl_get_document("nsa", "X", page=0)
    assert e.value.code == "invalid_arg"


async def test_isap_page_is_forwarded_natively_and_not_recut(pool):
    """Konektor sam stronicuje kodeks - agregator nie moze ciac tego drugi raz."""
    pool.response = "TEKST " * 2000  # 12000 znakow = 3 strony agregatora
    raw = await pl_get_document("isap", "DU/2026/795", page=9)
    out = json.loads(raw)
    _, tool, args = pool.calls[0]
    assert (tool, args["eli"], args["page"]) == ("get_act_text", "DU/2026/795", 9)
    assert out["pagination"] == "native"
    assert out["content"] == pool.response  # nic nie uciete lokalnie
    assert "total_pages" not in out  # nie zgadujemy liczby stron dokumentu


async def test_aggregator_pagination_marks_itself(pool):
    pool.response = "B" * 12000
    out = json.loads(await pl_get_document("nsa", "7E50984BB7", page=2))
    assert out["pagination"] == "aggregator"
    assert out["total_pages"] == 3
    assert out["page"] == out["page_number"] == 2


# ---------- pl_call: alias `args` + walidacja pass-through ----------


async def test_pl_call_accepts_args_alias(pool):
    await pl_call("saos", "saos_cite_check", args={"id": 123})
    assert pool.calls[0][1:] == ("saos_cite_check", {"id": 123})


async def test_pl_call_accepts_arguments_canonical(pool):
    await pl_call("saos", "saos_cite_check", arguments={"id": 123})
    assert pool.calls[0][2] == {"id": 123}


async def test_pl_call_rejects_both_names(pool):
    with pytest.raises(PLLegalError) as e:
        await pl_call("saos", "saos_cite_check", arguments={"id": 1}, args={"id": 1})
    assert e.value.code == "invalid_arg"


async def test_pl_call_parses_json_string_arguments(pool):
    await pl_call("saos", "saos_cite_check", args='{"id": 7}')
    assert pool.calls[0][2] == {"id": 7}


async def test_pl_call_rejects_non_json_string(pool):
    with pytest.raises(PLLegalError) as e:
        await pl_call("saos", "saos_cite_check", arguments="id=7")
    assert e.value.code == "invalid_arg"


async def test_pl_call_names_the_native_param_instead_of_letting_upstream_fail(pool):
    """Regresja: `article` zamiast `article_number` zdradzalo sie dopiero w upstreamie."""
    pool.schemas["eu_article"] = {
        "type": "object",
        "properties": {"regulation": {"type": "string"}, "article_number": {"type": "string"}},
        "required": ["regulation", "article_number"],
    }
    with pytest.raises(PLLegalError) as e:
        await pl_call("eu-compliance", "eu_article", args={"regulation": "GDPR", "article": "33"})
    assert e.value.code == "invalid_arg"
    msg = str(e.value)
    assert "article_number" in msg and "'article'" in msg
    assert pool.calls == []  # nie poszlo do konektora


async def test_pl_call_passes_valid_native_args(pool):
    pool.schemas["eu_article"] = {
        "type": "object",
        "properties": {"regulation": {"type": "string"}, "article_number": {"type": "string"}},
        "required": ["regulation", "article_number"],
    }
    await pl_call("eu-compliance", "eu_article", args={"regulation": "GDPR", "article_number": "33"})
    assert pool.calls[0][1] == "eu_article"


async def test_pl_call_unknown_tool_caught_before_upstream(pool):
    with pytest.raises(PLLegalError) as e:
        await pl_call("saos", "saos_teleport", args={})
    assert e.value.code == "unknown_tool"
    assert pool.calls == []


async def test_pl_call_tolerates_extra_fields_when_schema_satisfied(pool):
    """Forward-compat: nadmiarowe pole bez podobienstwa do znanego przechodzi."""
    pool.schemas["uodo_stats"] = {
        "type": "object",
        "properties": {"period_from": {"type": "string"}, "period_to": {"type": "string"}},
        "required": ["period_from"],
    }
    await pl_call("uodo", "uodo_stats", args={"period_from": "2024-01-01", "sektor": "banki"})
    assert pool.calls[0][2]["sektor"] == "banki"


async def test_catalog_exposes_native_param_names(pool):
    """Punkt 3 dogfoodingu: `article_number` widoczne bez spawnu konektora."""
    data = json.loads(await pl_list_sources())
    by_id = {e["id"]: e for e in data["sources"]}
    eu = by_id["eu-compliance"]["native_params"]
    assert eu["pl_get_document"]["document_id"] == "article_number"
    assert eu["pl_get_document"]["required_extra"] == ["regulation"]
    saos = by_id["saos"]["native_params"]["pl_search"]
    assert (saos["query"], saos["page"], saos["page_base"]) == ("all", "pageNumber", 0)
    assert by_id["isap"]["native_params"]["pl_get_document"]["pagination"] == "native"
    assert pool.list_tools_calls == 0  # katalog nadal nie spawnuje niczego
