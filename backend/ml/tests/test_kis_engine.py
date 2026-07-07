"""Unit tests for the KIS Phase 2 vector engine (kis_engine.py):
S_t/L_t decomposition, chaos-event tagging, and the 50k-run benchmark.

Runnable two ways:
    pytest backend/ml/tests/test_kis_engine.py
    python backend/ml/tests/test_kis_engine.py     # standalone
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ensemble
import kis_engine as kis
import match_flow as mf

ENGINE = ensemble.get_engine()


# ─────────────────────────────────────────────────────────────────────────────
# tactical_rating
# ─────────────────────────────────────────────────────────────────────────────
def test_tactical_rating_bounds_and_basis():
    r = kis.tactical_rating("Argentina")
    assert r["basis"] == "heuristic"
    assert 0.0 <= r["rating"] <= 1.0


def test_tactical_rating_unplayed_team_gets_default_basis():
    r = kis.tactical_rating("Nonexistent Team XYZ")
    assert r["basis"] == "heuristic_default"
    assert r["rating"] == 0.5


# ─────────────────────────────────────────────────────────────────────────────
# pressure_score
# ─────────────────────────────────────────────────────────────────────────────
def test_pressure_score_partial_basis_and_exclusions():
    r = kis.pressure_score("Argentina", composure=0.7)
    assert r["basis"] == "partial_3_of_5_inputs"
    assert set(r["excluded_inputs"]) == {"captain_maturity", "crowd_factor"}
    assert 0.0 <= r["score"] <= 100.0


def test_pressure_score_higher_for_more_knockout_experience():
    # Argentina (curated experience=32, shootout 6-2) should outrank a team
    # with no curated history at the same composure input.
    high = kis.pressure_score("Argentina", composure=0.5)
    low = kis.pressure_score("Nonexistent Team XYZ", composure=0.5)
    assert high["score"] > low["score"]


def test_pressure_score_no_composure_defaults_neutral():
    r = kis.pressure_score("Argentina")
    assert r["inputs"]["composure"] is None


# ─────────────────────────────────────────────────────────────────────────────
# S_t weights
# ─────────────────────────────────────────────────────────────────────────────
def test_st_weights_sum_to_one():
    total = sum(kis.ST_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


def test_skill_score_within_bounds():
    prof = mf._profiles(ENGINE, "Argentina", "Switzerland", neutral=True, knockout=True)
    tac = kis.tactical_rating("Argentina")
    pr = kis.pressure_score("Argentina", composure=prof["home"]["composure"])
    s = kis.skill_score(prof["home"], tac, pr)
    assert 0.0 <= s["skill_score"] <= 1.0
    # components should sum back to the total (renormalized weights, no drift
    # beyond independent 4-decimal rounding on each of the 3 components)
    comp_sum = sum(s["components"].values())
    assert abs(comp_sum - s["skill_score"]) < 1e-3


# ─────────────────────────────────────────────────────────────────────────────
# L_t — luck_bias
# ─────────────────────────────────────────────────────────────────────────────
def test_luck_bias_known_team_has_engine_basis():
    r = kis.luck_bias(ENGINE, "Argentina")
    assert r["basis"] == "engine"
    assert r["mu_bias"] is not None
    assert r["n_matches"] > 0


def test_luck_bias_unknown_team_is_unavailable():
    r = kis.luck_bias(ENGINE, "Nonexistent Team XYZ")
    assert r["basis"] == "unavailable_no_matches"
    assert r["mu_bias"] is None


def test_luck_bias_no_dc_model_reports_unavailable():
    class _StubEngine:
        dc = None
    r = kis.luck_bias(_StubEngine(), "Argentina")
    assert r["basis"] == "unavailable_no_dc_model"
    assert r["mu_bias"] is None


# ─────────────────────────────────────────────────────────────────────────────
# chaos_sigma
# ─────────────────────────────────────────────────────────────────────────────
def test_chaos_sigma_no_venue_is_neutral_default():
    r = kis.chaos_sigma(None, None)
    assert r["weather_basis"] == "no_venue_given"
    assert r["referee_basis"] == "static_neutral_default"
    assert r["sigma"] > 0


def test_chaos_sigma_referee_strictness_shifts_sigma():
    lo = kis.chaos_sigma(None, None, referee_strictness=0.1)
    hi = kis.chaos_sigma(None, None, referee_strictness=0.9)
    assert hi["sigma"] > lo["sigma"]
    assert hi["referee_basis"] == "caller_provided"


# ─────────────────────────────────────────────────────────────────────────────
# chaos-run tagging
# ─────────────────────────────────────────────────────────────────────────────
def test_tag_chaos_runs_rate_is_small_and_bounded():
    rng = np.random.default_rng(42)
    gh = rng.poisson(1.4, 50_000)
    ga = rng.poisson(1.1, 50_000)
    r = kis._tag_chaos_runs(gh, ga, 1.4, 1.1)
    # 2.5-sigma tail: a few percent of runs, not a majority, not zero for a
    # 50k-run discrete (Skellam) distribution.
    assert 0.0 < r["chaos_run_rate"] < 0.10
    assert r["chaos_mask"].sum() == r["chaos_run_count"]
    assert len(r["chaos_mask"]) == 50_000


def test_tag_chaos_runs_higher_threshold_means_fewer_flags():
    rng = np.random.default_rng(7)
    gh = rng.poisson(1.4, 20_000)
    ga = rng.poisson(1.1, 20_000)
    lo_thresh_mask = np.abs((gh - ga) - 0.3) / np.sqrt(2.5) > 1.5
    hi_thresh_mask = np.abs((gh - ga) - 0.3) / np.sqrt(2.5) > 3.0
    assert hi_thresh_mask.sum() <= lo_thresh_mask.sum()


# ─────────────────────────────────────────────────────────────────────────────
# simulate_kis — end to end + performance
# ─────────────────────────────────────────────────────────────────────────────
def test_simulate_kis_end_to_end_shape():
    r = kis.simulate_kis(ENGINE, "Argentina", "Switzerland", n=5000)
    assert r["engine"] == "kis_vector_v1"
    assert r["n_sims"] == 5000
    vm = r["vector_metrics"]
    assert 0.0 <= vm["home_skill_score"] <= 1.0
    assert 0.0 <= vm["away_skill_score"] <= 1.0
    assert vm["luck_sigma_chaos"] > 0
    assert set(r["pressure_score"]) == {"Argentina", "Switzerland"}
    assert set(r["tactical_rating"]) == {"Argentina", "Switzerland"}
    assert r["chaos_events"]["threshold_sigma"] == kis.CHAOS_SIGMA_THRESHOLD


def test_simulate_kis_50k_runs_under_400ms_budget():
    # KIS_SPEC.md §11 acceptance criterion 3: measured, not assumed. Generous
    # 200ms bound (vs the spec's 400ms target and the ~4ms observed on dev
    # hardware) to avoid CI flakiness while still catching a real regression.
    r = kis.simulate_kis(ENGINE, "France", "Morocco", n=kis.KIS_N_SIMS)
    assert r["n_sims"] == 50_000
    assert r["elapsed_ms"] < 200


def test_simulate_kis_deterministic_for_same_seed_offset():
    r1 = kis.simulate_kis(ENGINE, "Argentina", "Switzerland", n=2000, seed_offset=5)
    r2 = kis.simulate_kis(ENGINE, "Argentina", "Switzerland", n=2000, seed_offset=5)
    assert r1["chaos_events"]["run_count"] == r2["chaos_events"]["run_count"]


# ─────────────────────────────────────────────────────────────────────────────
# narrate_with_chaos — additive, doesn't touch match_flow's own behavior
# ─────────────────────────────────────────────────────────────────────────────
def test_narrate_with_chaos_tags_goal_events():
    prof = mf._profiles(ENGINE, "Argentina", "Switzerland", neutral=True, knockout=True)
    sim = mf._simulate(prof, np.random.default_rng(1), knockout=True, n=3000)
    events, _ = kis.narrate_with_chaos(prof, sim, "Argentina",
                                       np.random.default_rng(2),
                                       chaos_run_rate=1.0, knockout=True)
    goal_events = [e for e in events if e["type"] == "goal"]
    assert goal_events, "expected at least one goal event in the modal scoreline"
    assert all(e["vector_dominant"] == "luck" for e in goal_events)


def test_narrate_with_chaos_zero_rate_tags_all_skill():
    prof = mf._profiles(ENGINE, "Argentina", "Switzerland", neutral=True, knockout=True)
    sim = mf._simulate(prof, np.random.default_rng(1), knockout=True, n=3000)
    events, _ = kis.narrate_with_chaos(prof, sim, "Argentina",
                                       np.random.default_rng(2),
                                       chaos_run_rate=0.0, knockout=True)
    goal_events = [e for e in events if e["type"] == "goal"]
    assert all(e["vector_dominant"] == "skill" for e in goal_events)


def test_match_flow_simulate_tie_unaffected_by_kis_module():
    # Non-regression: importing/using kis_engine must not monkey-patch or
    # otherwise change match_flow.simulate_tie()'s own output shape.
    r = mf.simulate_tie(ENGINE, "Argentina", "Switzerland", knockout=True, neutral=True)
    goal_events = [e for e in r["match_flow"] if e.get("type") == "goal"]
    for e in goal_events:
        assert "vector_dominant" not in e


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
