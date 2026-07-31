"""Drift test - INSTRUCTIONS spojne z zarejestrowanymi toolami i kodami bledow.

Fail jesli:
1. INSTRUCTIONS wymienia tool `pl_*` niezarejestrowany w mcp
2. Kod bledu z PLLegalError.VALID_CODES nie jest udokumentowany w INSTRUCTIONS
3. Kod bledu wymieniony w INSTRUCTIONS nie istnieje w PLLegalError.VALID_CODES
4. Docstring toola wymienia kod bledu spoza VALID_CODES
"""

from __future__ import annotations

import re

import pytest

from pl_legal_mcp.instructions import INSTRUCTIONS
from pl_legal_mcp.server import PLLegalError, mcp


async def _registered_tools() -> dict:
    return {t.name: t for t in await mcp.list_tools()}


@pytest.mark.asyncio
async def test_instructions_only_reference_registered_tools():
    registered = set((await _registered_tools()).keys())
    referenced = {m for m in re.findall(r"`(pl_[a-z_]+)`", INSTRUCTIONS)}
    orphan = referenced - registered
    assert not orphan, (
        f"INSTRUCTIONS referencuja niezarejestrowane toole: {orphan}. "
        f"Registered: {sorted(registered)}"
    )


@pytest.mark.asyncio
async def test_all_unified_tools_mentioned_in_instructions():
    registered = set((await _registered_tools()).keys())
    referenced = {m for m in re.findall(r"`(pl_[a-z_]+)`", INSTRUCTIONS)}
    unmentioned = registered - referenced
    assert not unmentioned, f"Toole bez wzmianki w INSTRUCTIONS (call order?): {unmentioned}"


def test_error_codes_documented_in_instructions():
    documented = set(re.findall(r"`([a-z_]+)`", INSTRUCTIONS))
    missing = PLLegalError.VALID_CODES - documented
    assert not missing, f"Kody bledow bez dokumentacji w INSTRUCTIONS: {missing}"


def test_instructions_error_codes_exist():
    # Sekcja "Iterating on errors" - kazdy `kod` z myslnikiem opisu musi istniec.
    section = INSTRUCTIONS.split("## Iterating on errors")[1].split("##")[0]
    codes = set(re.findall(r"- `([a-z_]+)`", section))
    phantom = codes - PLLegalError.VALID_CODES
    assert not phantom, f"INSTRUCTIONS dokumentuja nieistniejace kody: {phantom}"


@pytest.mark.asyncio
async def test_tool_docstrings_reference_valid_error_codes():
    known_noncodes = {"pl_list_sources", "pl_search", "pl_get_document", "pl_call",
                      "content", "page_number", "total_pages", "has_more", "extra",
                      "document_id", "dateFrom", "date_from", "arguments", "regulation",
                      "country", "courtType", "group", "source_id", "query", "limit",
                      "date_to", "page"}
    for name, tool in (await _registered_tools()).items():
        desc = tool.description or ""
        if "Errors:" not in desc:
            continue
        errors_part = desc.split("Errors:")[1]
        codes = set(re.findall(r"`([a-z_]+)`", errors_part)) - known_noncodes
        phantom = codes - PLLegalError.VALID_CODES
        assert not phantom, f"Tool {name} dokumentuje nieistniejace kody bledow: {phantom}"
