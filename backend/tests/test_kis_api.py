"""Integration tests for GET /api/v1/predict/kis (KIS_SPEC.md §6.2, Phase 3).

Uses FastAPI's TestClient against the real app (same pattern as
gen_snapshots.py) — no live server needed. `settings.use_db` is False by
default so this never touches any database.

GET, not POST — see routers/kis.py's docstring: matches this app's own
`/api/predict?home=&away=` convention and is required for the snapshot
system (gen_snapshots.py / lib/api.ts) to be able to pre-generate this
route's results for the backend-free Vercel demo at all.

Runnable via pytest or standalone:
    python backend/tests/test_kis_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_kis_valid_matchup_returns_200_with_full_schema():
    r = client.get("/api/v1/predict/kis",
                   params={"home_team": "Argentina", "away_team": "Switzerland"})
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
    r = client.get("/api/v1/predict/kis",
                   params={"home_team": "Nonexistent Team XYZ", "away_team": "Argentina"})
    assert r.status_code == 404


def test_kis_unknown_away_team_404s():
    r = client.get("/api/v1/predict/kis",
                   params={"home_team": "Argentina", "away_team": "Nonexistent Team XYZ"})
    assert r.status_code == 404


def test_kis_same_team_both_sides_400s():
    r = client.get("/api/v1/predict/kis",
                   params={"home_team": "Argentina", "away_team": "Argentina"})
    assert r.status_code == 400


def test_kis_referee_strictness_out_of_range_422s():
    r = client.get("/api/v1/predict/kis",
                   params={"home_team": "Argentina", "away_team": "Switzerland",
                           "referee_strictness": 1.5})
    assert r.status_code == 422


def test_kis_hypothetical_matchup_not_scheduled_still_works():
    # D4 (KIS_SPEC.md §10) resolved by precedent: not restricted to a real
    # scheduled fixture. Brazil vs Germany aren't currently drawn together.
    r = client.get("/api/v1/predict/kis",
                   params={"home_team": "Brazil", "away_team": "Germany"})
    assert r.status_code == 200
    assert r.json()["home_team"] == "Brazil"


def test_kis_weather_condition_enum_accepted_without_city():
    r = client.get("/api/v1/predict/kis",
                   params={"home_team": "Argentina", "away_team": "Switzerland",
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
    kis_r = client.get("/api/v1/predict/kis",
                       params={"home_team": "France", "away_team": "Morocco"})
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
    params = {"home_team": "Norway", "away_team": "England"}
    times = []
    winners = set()
    for _ in range(20):
        t0 = time.perf_counter()
        r = client.get("/api/v1/predict/kis", params=params)
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
    if not upcoming:
        pytest.skip("tournament complete — no unresolved bracket ties left to check")

    failures = []
    for m in upcoming:
        h, a = m["home_team"], m["away_team"]
        r = client.get("/api/v1/predict/kis", params={"home_team": h, "away_team": a})
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


def test_kis_confidence_matches_match_flow_for_a_near_coinflip_fixture():
    # Regression guard for a real bug found 2026-07-14, pinned to a specific
    # fixture (rather than "whichever bracket tie is next", which stops
    # exercising this once that tie resolves): kis_engine.compose() checked
    # its pipeline-disagreement penalty against ITS OWN KIS_N_SIMS=50,000
    # regulation-time simulation instead of match_flow.simulate_tie()'s
    # N_SIMS=6,000 one. Both start from the identical seed
    # (match_flow._seed(home, away)), but `_simulate()` draws home goals then
    # away goals sequentially off the SAME rng: the home-goals draw is
    # prefix-stable across `n`, but by the away-goals draw the underlying
    # bit-stream position has already diverged (it depends on how many
    # samples the home-goals draw consumed, which depends on `n`). So a
    # 6,000-sample and a 50,000-sample run from the same seed are two
    # independent realizations past the first draw, not the same estimate at
    # different precision -- for a near-50/50 fixture like France v Spain
    # they can land on opposite sides of "who's favored in regulation",
    # producing a confidence delta against the bracket for the SAME fixture
    # (observed pre-fix: bracket confidence 32, KIS confidence 17).
    from app import knockout_engine, ml_engine

    bracket = knockout_engine.resolve_bracket()
    tie = next((m for m in bracket["matches"]
               if {m.get("home_team"), m.get("away_team")} == {"France", "Spain"}), None)
    if tie is None or tie.get("home_score") is not None:
        import pytest
        pytest.skip("France v Spain is no longer an unresolved bracket tie")

    flow = ml_engine.match_flow("France", "Spain", neutral=True)
    r = client.get("/api/v1/predict/kis", params={"home_team": "France", "away_team": "Spain"})
    assert r.status_code == 200
    kis_confidence = r.json()["confidence"]

    assert kis_confidence == tie["confidence"], (
        f"KIS confidence ({kis_confidence}) diverges from the bracket's "
        f"({tie['confidence']}) for France v Spain -- regulation split was "
        f"{flow['probabilities']['regulation']}"
    )


def test_kis_get_request_is_snapshottable_shape():
    # The whole point of switching to GET: gen_snapshots.py's grab() only
    # does client.get(path) — this locks in that the route stays GET-shaped
    # so it never regresses back to POST-only (and unsnapshottable).
    from app.routers import kis as kis_router
    route = next(r for r in kis_router.router.routes
                if r.path == "/api/v1/predict/kis")
    assert "GET" in route.methods
    assert "POST" not in route.methods


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
