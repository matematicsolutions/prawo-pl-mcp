"""Paginacja tekstu po 5000 znakow na strone (wzorzec yargi-mcp).

Dokumenty prawne (orzeczenia, akty) bywaja dlugie; MCP tool zwracajacy 200k
znakow zabija okno kontekstu. Strona ~5000 znakow, ciecie na granicy akapitu
gdy to mozliwe (okno tolerancji 500 znakow wstecz).
"""

from __future__ import annotations

PAGE_SIZE = 5000
_BREAK_TOLERANCE = 500


def paginate(text: str, page_number: int = 1) -> dict:
    """Zwroc strone tekstu + metadane paginacji.

    Zwraca dict: content, page_number, total_pages, total_chars, has_more.
    page_number poza zakresem -> ostatnia strona (nie blad - LLM czesto
    iteruje "do konca").
    """
    text = text or ""
    total_chars = len(text)
    if total_chars == 0:
        return {
            "content": "",
            "page_number": 1,
            "total_pages": 1,
            "total_chars": 0,
            "has_more": False,
        }

    # Wyznacz granice stron z preferencja dla konca akapitu/linii.
    boundaries: list[int] = [0]
    pos = 0
    while pos < total_chars:
        end = min(pos + PAGE_SIZE, total_chars)
        if end < total_chars:
            window = text[max(pos, end - _BREAK_TOLERANCE):end]
            cut = max(window.rfind("\n\n"), window.rfind("\n"))
            if cut > 0:
                end = max(pos, end - _BREAK_TOLERANCE) + cut + 1
        boundaries.append(end)
        pos = end

    total_pages = max(1, len(boundaries) - 1)
    page = min(max(1, page_number), total_pages)
    content = text[boundaries[page - 1]:boundaries[page]]

    return {
        "content": content,
        "page_number": page,
        "total_pages": total_pages,
        "total_chars": total_chars,
        "has_more": page < total_pages,
    }
