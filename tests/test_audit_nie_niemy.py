"""Nieudany zapis audytu nie blokuje uzytkownika, ale NIE jest niemy (2026-09-24)."""
from __future__ import annotations

import prawo_pl_mcp.audit as audit


def test_nieudany_zapis_jest_policzony_i_slyszalny(monkeypatch, capsys):
    def zepsuty():
        raise PermissionError("brak prawa zapisu")
    monkeypatch.setattr(audit, "_audit_file", zepsuty)
    przed = audit.NIEUDANE_ZAPISY
    audit.log_event(**{k: v for k, v in dict(tool="t", source=None, params={}, result_summary={},
                                              source_urls=[], latency_ms=1.0, cache_hit=False).items()
                        if k in audit.log_event.__code__.co_varnames})
    assert audit.NIEUDANE_ZAPISY == przed + 1
    err = capsys.readouterr()
    assert "wpis NIE zapisany" in err.err
    assert err.out == ""
