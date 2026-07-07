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


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
