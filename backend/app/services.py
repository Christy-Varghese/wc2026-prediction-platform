"""Assembly services: turn fixtures + ensemble output into API payloads."""
from __future__ import annotations

from . import fixtures, ml_engine


# ── prediction scoring ───────────────────────────────────────────────────────
# Points ladder for grading a prediction against a played match's actual
# result, out of 3 per match. Same rule for group-stage and knockout matches:
# pass an already-penalty-resolved `actual_winner` for knockout ties (a
# shootout always produces a decisive winner, never "Draw" — the 1pt draw
# tier is reachable only for group-stage matches).
#   3 pts — predicted_winner correct AND the actual result wasn't a draw
#   1 pt  — actual result was a draw (flat, regardless of what was predicted —
#           even correctly calling "Draw" caps here, it does not reach 3)
#   0 pts — predicted_winner wrong (the other side won, no draw)
# Exact-scoreline hits are NOT part of this 0-3 total — see
# `prediction_exact_bonus()` below, tracked as its own separate stat.
def prediction_points(predicted_winner: str | None, predicted_score: str | None,
                      home_team: str, away_team: str,
                      actual_home: int, actual_away: int,
                      actual_winner: str | None = None) -> int:
    if not predicted_winner:
        return 0
    if actual_winner is None:
        actual_winner = (home_team if actual_home > actual_away
                         else away_team if actual_away > actual_home else "Draw")
    if actual_winner == "Draw":
        return 1
    if predicted_winner == actual_winner:
        return 3
    return 0


# Separate exact-scoreline bonus (+1), independent of the 0-3 ladder above —
# tracked as its own tally (e.g. "N exact scores"), never summed into a
# match's points total.
def prediction_exact_bonus(predicted_score: str | None,
                           actual_home: int, actual_away: int) -> int:
    if predicted_score is None:
        return 0
    return 1 if predicted_score == f"{actual_home}-{actual_away}" else 0


def _conditions(home: str, away: str, match: dict | None) -> dict:
    """Rest, travel (km) and weather severity for a scheduled match."""
    if not match:
        return {}
    import venues, weather  # ml on path via ml_engine import
    city = match.get("city", "")
    wx = weather.conditions(city, match.get("kickoff", ""))
    h_prev = fixtures.prev_city(home, match["id"])
    a_prev = fixtures.prev_city(away, match["id"])
    home_travel = venues.haversine_km(h_prev, city) if h_prev else 0.0
    away_travel = venues.haversine_km(a_prev, city) if a_prev else 0.0
    return {
        "rest_diff": float(match.get("home_rest_days", 4) - match.get("away_rest_days", 4)),
        "travel_diff_km": round(home_travel - away_travel, 1),
        "weather_severity": wx["severity"],
        "_weather": wx, "_home_travel": home_travel, "_away_travel": away_travel,
    }


def _ctx_for(home: str, away: str, match: dict | None = None) -> dict:
    """Build a MatchContext dict from current team data + match conditions.

    Availability is impact-weighted and merges the live injuries feed. When a
    scheduled `match` is given, rest days, inter-city travel and venue weather
    severity are added too.
    """
    def avail(team: str) -> float:
        return ml_engine.team_availability(team, fixtures.squad(team))
    th, ta = fixtures.team_index().get(home, {}), fixtures.team_index().get(away, {})
    ctx = {
        "avail_diff": round(avail(home) - avail(away), 3),
        "squad_val_diff": round((th.get("strength_index", 50)
                                 - ta.get("strength_index", 50)) / 100, 3),
    }
    cond = _conditions(home, away, match)
    for k in ("rest_diff", "travel_diff_km", "weather_severity"):
        if k in cond:
            ctx[k] = cond[k]
    return ctx


def predict(home: str, away: str, neutral: bool = True,
            match: dict | None = None) -> dict:
    return ml_engine.predict_match(home, away, neutral, _ctx_for(home, away, match))


def _tactical(home: str, away: str, pred: dict) -> dict:
    xg = pred["expected_goals"]
    th = fixtures.team_index().get(home, {})
    ta = fixtures.team_index().get(away, {})
    return {
        "attack": {home: round(xg["home"], 2), away: round(xg["away"], 2)},
        "strength_index": {home: th.get("strength_index"),
                           away: ta.get("strength_index")},
        "edge": (home if xg["home"] > xg["away"] else away),
        "summary": (f"{home if xg['home'] >= xg['away'] else away} holds the "
                    f"attacking edge; the lower-xG side must rely on defensive "
                    f"organisation and transitions."),
    }


def match_detail(mid: int) -> dict | None:
    m = fixtures.match_by_id(mid)
    if not m:
        return None
    pred = predict(m["home_team"], m["away_team"], m["neutral"], match=m)
    cond = _conditions(m["home_team"], m["away_team"], m)
    # Full match-flow simulation (same engine as the knockout bracket). Group
    # fixtures are simulated as non-knockout: a 90' draw is a valid result and
    # there is no extra time / shootout.
    is_ko = m.get("stage", "group") != "group"
    try:
        flow = ml_engine.match_flow(m["home_team"], m["away_team"], pred,
                                    knockout=is_ko, neutral=m["neutral"])
    except Exception:  # noqa: BLE001
        flow = None
    return {
        "match": m,
        "prediction": pred,
        "flow": flow,
        "key_players": {
            m["home_team"]: fixtures.key_players(m["home_team"]),
            m["away_team"]: fixtures.key_players(m["away_team"]),
        },
        "team_comparison": {
            m["home_team"]: fixtures.team_index().get(m["home_team"]),
            m["away_team"]: fixtures.team_index().get(m["away_team"]),
        },
        "tactical": _tactical(m["home_team"], m["away_team"], pred),
        "injuries": {
            t: [p for p in ml_engine.squad_with_injuries(t, fixtures.squad(t))
                if p["fitness"] != "fit"]
            for t in (m["home_team"], m["away_team"])
        },
        "availability": {
            t: ml_engine.team_availability(t, fixtures.squad(t))
            for t in (m["home_team"], m["away_team"])
        },
        "conditions": {
            "weather": cond.get("_weather"),
            "rest_days": {m["home_team"]: m.get("home_rest_days"),
                          m["away_team"]: m.get("away_rest_days")},
            "travel_km": {m["home_team"]: cond.get("_home_travel"),
                          m["away_team"]: cond.get("_away_travel")},
        },
    }


def match_card(m: dict) -> dict:
    """Light prediction card for list views."""
    pred = predict(m["home_team"], m["away_team"], m["neutral"], match=m)
    ti = fixtures.team_index()
    return {**m,
            "home_flag": ti.get(m["home_team"], {}).get("flag_url", ""),
            "away_flag": ti.get(m["away_team"], {}).get("flag_url", ""),
            "p_home": pred["p_home"], "p_draw": pred["p_draw"],
            "p_away": pred["p_away"], "confidence": pred["confidence"],
            "top_score": pred["top_scores"][0] if pred["top_scores"] else None,
            "top_scores": pred.get("top_scores"),
            "predicted_winner": pred.get("predicted_winner"),
            "expected_goals": pred.get("expected_goals"),
            "total_goals": pred.get("total_goals"),
            "over_2_5": pred.get("over_2_5"),
            "upset_probability": pred["upset_probability"],
            "market_used": pred.get("market_used", False)}
