"""Paginacja 5000 znakow - offline."""

from __future__ import annotations

from pl_legal_mcp.pagination import PAGE_SIZE, paginate


def test_short_text_single_page():
    p = paginate("krotki tekst", 1)
    assert p["content"] == "krotki tekst"
    assert p["total_pages"] == 1
    assert p["has_more"] is False


def test_empty_text():
    p = paginate("", 1)
    assert p["content"] == ""
    assert p["total_pages"] == 1


def test_long_text_pages_cover_everything():
    text = "\n\n".join(f"Akapit {i}. " + "x" * 200 for i in range(200))
    pages = []
    n = 1
    while True:
        p = paginate(text, n)
        pages.append(p["content"])
        if not p["has_more"]:
            break
        n += 1
    assert "".join(pages) == text
    assert all(len(c) <= PAGE_SIZE + 1 for c in pages)


def test_page_out_of_range_clamps_to_last():
    text = "y" * (PAGE_SIZE * 2 + 100)
    p = paginate(text, 999)
    assert p["page_number"] == p["total_pages"]
    assert p["has_more"] is False


def test_page_zero_clamps_to_first():
    p = paginate("z" * (PAGE_SIZE + 10), 0)
    assert p["page_number"] == 1
