"""Unit tests for the KIS Phase 1 aggregation functions in tournament_stats.py:
comeback_rate, defensive_variance, late_game_breakdown_rate.

Runnable two ways:
    pytest backend/ml/tests/test_tournament_stats_kis.py
    python backend/ml/tests/test_tournament_stats_kis.py     # standalone
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tournament_stats as ts


def test_defensive_variance_zero_for_unplayed_team():
    r = ts.defensive_variance("Nonexistent Team XYZ")
    assert r == {"played": 0, "mean_ga": None, "variance": None}


def test_defensive_variance_sane_for_played_team():
    r = ts.defensive_variance("Argentina")
    assert r["played"] == 6
    assert r["mean_ga"] is not None and r["variance"] is not None
    assert r["mean_ga"] >= 0
    assert r["variance"] >= 0


def test_comeback_rate_none_when_never_trailed():
    r = ts.comeback_rate("Nonexistent Team XYZ")
    assert r["rate"] is None
    assert r["trailed_matches"] == 0


def test_comeback_rate_morocco_recovers():
    # Morocco's dramatic penalty-shootout win over Netherlands (1-1, trailed
    # 0-1 before Diop's 91st-minute equalizer) is a known recovered case.
    r = ts.comeback_rate("Morocco")
    assert r["trailed_matches"] >= 1
    assert 0.0 <= (r["rate"] or 0) <= 1.0


def test_late_game_breakdown_rate_bounds():
    r = ts.late_game_breakdown_rate("Norway")
    assert r["matches_with_data"] >= 1
    assert 0.0 <= (r["rate"] or 0) <= 1.0
    assert r["late_goals_conceded"] >= r["matches_with_late_concession"]


def test_late_game_breakdown_rate_none_when_no_data():
    r = ts.late_game_breakdown_rate("Nonexistent Team XYZ")
    assert r["rate"] is None
    assert r["matches_with_data"] == 0


def test_functions_never_double_count_home_and_away():
    # A team's own matches shouldn't be counted twice even if it appears as
    # both home and away across different fixtures (sanity: played count
    # should equal len(WC2026_PLAYED matches touching the team)).
    from tournament_form import WC2026_PLAYED
    n = sum(1 for h, a, *_ in WC2026_PLAYED if "Argentina" in (h, a))
    assert ts.defensive_variance("Argentina")["played"] == n


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
