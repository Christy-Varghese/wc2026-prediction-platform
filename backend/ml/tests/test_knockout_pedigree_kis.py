"""Unit tests for the KIS Phase 1 curated knockout-pedigree table in
player_condition.py (KNOCKOUT_PEDIGREE / knockout_pedigree()).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import player_condition as pc


def test_all_32_r32_teams_are_curated():
    from tournament_form import WC2026_PLAYED_KNOCKOUT
    r32_teams = {t for h, a, *_ in WC2026_PLAYED_KNOCKOUT[:16] for t in (h, a)}
    assert len(r32_teams) == 32
    missing = r32_teams - set(pc.KNOCKOUT_PEDIGREE)
    assert not missing, f"R32 teams missing curated pedigree: {missing}"


def test_unknown_team_falls_back_to_default_not_a_guess():
    r = pc.knockout_pedigree("Nonexistent Team XYZ")
    assert r["basis"] == "default"
    assert r["knockout_experience"] == 0
    assert r["shootout_win_rate"] is None


def test_curated_team_has_basis_curated():
    r = pc.knockout_pedigree("Argentina")
    assert r["basis"] == "curated"
    assert r["knockout_experience"] > 0


def test_shootout_win_rate_none_when_no_shootout_history():
    # A team with 0 curated shootout wins/losses should report None, not 0.5
    # or 0.0 — "no data" must stay distinguishable from "always loses".
    zero_so_teams = [t for t, (_, w, l) in pc.KNOCKOUT_PEDIGREE.items()
                      if w == 0 and l == 0]
    assert zero_so_teams, "expected at least one curated team with no shootout history"
    r = pc.knockout_pedigree(zero_so_teams[0])
    assert r["shootout_win_rate"] is None


def test_shootout_win_rate_bounds():
    for team in pc.KNOCKOUT_PEDIGREE:
        r = pc.knockout_pedigree(team)
        if r["shootout_win_rate"] is not None:
            assert 0.0 <= r["shootout_win_rate"] <= 1.0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
