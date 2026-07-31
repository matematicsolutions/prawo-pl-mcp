"""Dispatch unified -> natywne parametry. Offline - POOL.call mockowany."""

from __future__ import annotations

import json

import pytest

import prawo_pl_mcp.server as srv
from prawo_pl_mcp.server import (
    PLLegalError,
    pl_get_document,
    pl_list_sources,
    pl_search,
)


class _CapturePool:
    def __init__(self, response: str = "ok"):
        self.calls: list[tuple[str, str, dict]] = []
        self.response = response

    async def call(self, source, tool, arguments):
        self.calls.append((source.id, tool, arguments))
        return self.response

    async def list_tools(self, source):
        return [{"name": t, "description": "", "input_schema": {}} for t in source.native_tools]


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
