"""Error codes are a machine contract - pin the set.

Agents branch on `PLLegalError.code`; humans read the message. The drift test checks that every
code is documented in INSTRUCTIONS and that raised codes belong to the set, but a code renamed
together with its documentation passes both checks. This test fails on any rename, removal or
addition, so the change shows up in a diff and gets a version bump and a CHANGELOG entry.

Intentional change: update PINNED_CODES in the same commit.
"""

from __future__ import annotations

from prawo_pl_mcp.server import PLLegalError

PINNED_CODES = frozenset({
    "invalid_arg",
    "source_unavailable",
    "unknown_source",
    "unknown_tool",
    "upstream_error",
})


def test_error_codes_are_pinned() -> None:
    current = frozenset(PLLegalError.VALID_CODES)
    assert current == PINNED_CODES, (
        "PLLegalError.VALID_CODES changed. "
        f"Added: {sorted(current - PINNED_CODES)}. Removed: {sorted(PINNED_CODES - current)}. "
        "Clients branch on these strings: bump the version, add a CHANGELOG entry and update "
        "PINNED_CODES in the same commit."
    )


def test_pinned_set_is_not_empty() -> None:
    assert PINNED_CODES, "An empty pin would pass for a server with no codes at all."
