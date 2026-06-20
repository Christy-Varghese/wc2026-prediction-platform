"""Predictions, home dashboard, and insights (dark horses / upset alerts)."""
from fastapi import APIRouter

from .. import fixtures, knockout_engine, ml_engine, services

router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/predict")
def predict(home: str, away: str, neutral: bool = True):
    return services.predict(home, away, neutral)


@router.get("/home")
def home():
    upcoming = [m for m in fixtures.schedule() if not m.get("played")]
    featured = [services.match_card(m) for m in upcoming[:6]]
    sim = ml_engine.sim_table(top=10)
    return {
        "featured_matches": featured,
        "top_winners": [{"team": r["team"],
                         "title_prob": round(r.get("Champion", 0), 3)}
                        for r in sim],
        "title_chart": [{"team": r["team"],
                         "Champion": round(r.get("Champion", 0), 3),
                         "Final": round(r.get("Final", 0), 3),
                         "SF": round(r.get("SF", 0), 3)} for r in sim],
        "dark_horses": ml_engine.dark_horses(4),
        "model_update": ml_engine.meta(),
    }


@router.get("/knockout")
def knockout():
    """Projected knockout bracket (R32 -> Final).

    Group slots are resolved from projected final standings (real results +
    predicted remaining games); each tie is run through the predictor. Enriched
    matches keep their original `home_label`/`away_label` and add `home_team`/
    `away_team` + a `prediction` block. Falls back to placeholder labels if the
    projection engine errors."""
    try:
        return knockout_engine.resolve_bracket()
    except Exception:  # noqa: BLE001 - never 500 the bracket view
        rows = fixtures.knockout()
        rounds: dict[str, list] = {}
        for m in rows:
            rounds.setdefault(m["round"], []).append(m)
        return {"projected": False, "champion": None,
                "rounds": [{"round": r, "matches": ms} for r, ms in rounds.items()],
                "matches": rows}


@router.get("/insights")
def insights():
    upcoming = [m for m in fixtures.schedule() if not m.get("played")][:24]
    fx = [{"home": m["home_team"], "away": m["away_team"],
           "neutral": m["neutral"]} for m in upcoming]
    return {
        "dark_horses": ml_engine.dark_horses(6),
        "upset_alerts": ml_engine.upset_alerts(fx, threshold=0.32)[:8],
    }
