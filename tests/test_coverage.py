"""Element 9 gate - the connector must declare its own holes.

The load-bearing assertion is ``known_gaps`` being non-empty. A gate over an empty list
passes every time and reads as a clean result, which is exactly how silent incompleteness
ships.
"""

from __future__ import annotations

import asyncio

from prawo_pl_mcp.coverage import build_coverage
from prawo_pl_mcp.server import pl_coverage


def _coverage():
    fn = getattr(pl_coverage, "fn", pl_coverage)
    return asyncio.run(fn())


def test_families_are_named():
    cov = build_coverage()
    assert cov.families, "empty denominator - a gate with nothing to check passes always"
    for fam in cov.families:
        assert fam.name and fam.tool and fam.source


def test_known_gaps_never_silently_empty():
    assert build_coverage().known_gaps, (
        "EMPTY known_gaps = BLOCK. No legal corpus is complete; an empty list means "
        "'not checked', not 'no gaps'."
    )


def test_every_gap_has_id_and_a_way_out():
    gaps = build_coverage().known_gaps
    ids = [g.id for g in gaps]
    assert len(ids) == len(set(ids)), "duplicate gap ids: {}".format(ids)
    for gap in gaps:
        assert gap.id and gap.family and gap.missing
        assert gap.fallback, "gap {} names a hole but no way around it".format(gap.id)


def test_gap_families_exist():
    cov = build_coverage()
    names = {f.name for f in cov.families}
    for gap in cov.known_gaps:
        assert gap.family in names, "gap {} points at unknown family {}".format(gap.id, gap.family)


def test_snapshot_families_carry_a_capture_date():
    for fam in build_coverage().families:
        if not fam.live:
            assert fam.captured_at, "snapshot family {} carries no captured_at".format(fam.name)


def test_tool_is_registered_and_returns_coverage():
    cov = _coverage()
    assert cov.status in {"ok", "degraded", "failed"}
    assert cov.known_gaps
