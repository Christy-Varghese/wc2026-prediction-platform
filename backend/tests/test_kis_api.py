"""Integration tests for POST /api/v1/predict/kis (KIS_SPEC.md §6.2, Phase 3).

Uses FastAPI's TestClient against the real app (same pattern as
gen_snapshots.py) — no live server needed. `settings.use_db` is False by
default so this never touches any database.

Runnable via pytest or standalone:
    python backend/tests/test_kis_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_kis_valid_matchup_returns_200_with_full_schema():
    r = client.post("/api/v1/predict/kis",
                    json={"home_team": "Argentina", "away_team": "Switzerland"})
    assert r.status_code == 200
    d = r.json()
    for key in ("predicted_winner", "win_probability", "predicted_score",
               "probabilities", "vector_metrics", "pressure_score",
               "tactical_rating", "chaos_events", "key_players", "pain_points",
               "match_flow", "explainability", "disclaimer", "n_sims"):
        assert key in d, f"missing key: {key}"
    assert d["n_sims"] == 50_000
    assert "Not betting advice" in d["disclaimer"]


def test_kis_unknown_home_team_404s():
    r = client.post("/api/v1/predict/kis",
                    json={"home_team": "Nonexistent Team XYZ", "away_team": "Argentina"})
    assert r.status_code == 404


def test_kis_unknown_away_team_404s():
    r = client.post("/api/v1/predict/kis",
                    json={"home_team": "Argentina", "away_team": "Nonexistent Team XYZ"})
    assert r.status_code == 404


def test_kis_same_team_both_sides_400s():
    r = client.post("/api/v1/predict/kis",
                    json={"home_team": "Argentina", "away_team": "Argentina"})
    assert r.status_code == 400


def test_kis_referee_strictness_out_of_range_422s():
    r = client.post("/api/v1/predict/kis",
                    json={"home_team": "Argentina", "away_team": "Switzerland",
                          "referee_strictness": 1.5})
    assert r.status_code == 422


def test_kis_hypothetical_matchup_not_scheduled_still_works():
    # D4 (KIS_SPEC.md §10) resolved by precedent: not restricted to a real
    # scheduled fixture. Brazil vs Germany aren't currently drawn together.
    r = client.post("/api/v1/predict/kis",
                    json={"home_team": "Brazil", "away_team": "Germany"})
    assert r.status_code == 200
    assert r.json()["home_team"] == "Brazil"


def test_kis_weather_condition_enum_accepted_without_city():
    r = client.post("/api/v1/predict/kis",
                    json={"home_team": "Argentina", "away_team": "Switzerland",
                          "weather_condition": "Extreme_Heat"})
    assert r.status_code == 200
    assert r.json()["vector_metrics"]["luck_sigma_chaos"] > 0


def test_kis_consistent_with_match_flow_knockout_report():
    # Acceptance criterion 2 (KIS_SPEC.md §11): KIS's predicted_winner must
    # not diverge from the EXISTING knockout-report engine's output for the
    # same fixture (both resolve a knockout tie to a single winner via the
    # same 90'->ET->pens model — /api/predict's own predicted_winner is a
    # 90'-only market pick and isn't the right comparison for a knockout tie).
    from app import ml_engine
    flow = ml_engine.match_flow("France", "Morocco", knockout=True, neutral=True)
    kis_r = client.post("/api/v1/predict/kis",
                        json={"home_team": "France", "away_team": "Morocco"})
    assert kis_r.status_code == 200
    kis_d = kis_r.json()
    assert kis_d["predicted_winner"] == flow["predicted_winner"]
    assert abs(kis_d["win_probability"] - flow["win_probability"]) < 0.05


def test_kis_route_registered_in_openapi_schema():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/predict/kis" in r.json()["paths"]


def test_kis_stress_repeated_calls_stay_fast_and_consistent():
    # Phase 5 "stress testing": the route (including the cache layer —
    # ml_engine.kis()'s Redis-with-in-process-fallback, see cache.py) under
    # repeated load. First call is a cold compute; later calls should hit
    # cache and be at least as fast, and every call must return the identical
    # predicted_winner (proves the cache isn't serving stale/wrong data
    # across repeated identical requests).
    import time
    payload = {"home_team": "Norway", "away_team": "England"}
    times = []
    winners = set()
    for _ in range(20):
        t0 = time.perf_counter()
        r = client.post("/api/v1/predict/kis", json=payload)
        times.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
        winners.add(r.json()["predicted_winner"])
    assert len(winners) == 1, f"predicted_winner changed across repeated calls: {winners}"
    assert max(times) < 500, f"slowest of 20 repeated calls took {max(times):.1f}ms (budget: 500ms)"


def test_kis_route_confidence_and_win_prob_match_bracket_within_tolerance():
    # Regression guard for a real bug found 2026-07-07: the route originally
    # built `base` via ml_engine.predict_match() directly, skipping
    # services.predict()'s injury-availability + squad-strength-differential
    # context (_ctx_for()) that knockout_engine._resolve_tie() (the bracket's
    # own prediction path) always builds. That silently dropped real signal
    # and produced confidence deltas up to ~22 points against the bracket for
    # the SAME fixture — not modeling disagreement, an implementation gap.
    # Fixed by routing through services.predict() and replicating
    # _resolve_tie()'s pipeline-disagreement confidence penalty in
    # kis_engine.compose(). This test hits the full HTTP route (not just
    # ml_engine.kis()) because the bug lived in the router, not the engine.
    from app import knockout_engine
    bracket = knockout_engine.resolve_bracket()
    upcoming = [m for m in bracket["matches"]
               if m.get("home_score") is None and m.get("home_team")]
    assert upcoming, "expected at least one unresolved bracket tie to check"

    failures = []
    for m in upcoming:
        h, a = m["home_team"], m["away_team"]
        r = client.post("/api/v1/predict/kis", json={"home_team": h, "away_team": a})
        assert r.status_code == 200
        kis = r.json()
        wp_delta = abs(m["win_probability"] - kis["win_probability"]) * 100
        conf_delta = (abs(m["confidence"] - kis["confidence"])
                     if m.get("confidence") is not None and kis.get("confidence") is not None
                     else None)
        if wp_delta > 5.0:  # generous — pure Monte Carlo noise is usually <1.5pp
            failures.append(f"{h} v {a}: win_probability delta {wp_delta:.1f}pp")
        if conf_delta is not None and conf_delta > 0:
            failures.append(f"{h} v {a}: confidence delta {conf_delta} "
                            f"(bracket={m['confidence']}, kis={kis['confidence']})")
    assert not failures, "KIS route diverges from the bracket:\n" + "\n".join(failures)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
