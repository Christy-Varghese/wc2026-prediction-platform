"""FastAPI entrypoint — FIFA World Cup 2026 prediction API."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import admin, awards, kis, matches, players, predictions, simulate, teams

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

for r in (predictions, matches, teams, players, simulate, awards, admin, kis):
    app.include_router(r.router)


@app.get("/api/news")
def news():
    from . import news as news_mod
    return news_mod.build()


@app.get("/api/tournament-summary")
def tournament_summary():
    """Champion/finalists + full-tournament CAI accuracy breakdown, for the
    /champions wrap-up page — only meaningful once the Final is played, but
    safe (nulls) to call before that. Reuses news.compute_accuracy() (single
    source of truth for the points-ladder math, shared with the ticker) and
    knockout_engine.resolve_bracket() rather than re-deriving either."""
    from . import fixtures, news as news_mod
    from .knockout_engine import resolve_bracket

    ko = resolve_bracket()
    by_id = {m["id"]: m for m in ko.get("matches", [])}
    final, third = by_id.get(104), by_id.get(103)

    def _winner(m):
        if not m or m.get("home_score") is None:
            return None, None
        hs, aws = m["home_score"], m["away_score"]
        ph, pa = m.get("pen_home"), m.get("pen_away")
        if hs > aws:
            return m["home_team"], m["away_team"]
        if aws > hs:
            return m["away_team"], m["home_team"]
        if ph is not None and pa is not None:
            return (m["home_team"], m["away_team"]) if ph > pa else (m["away_team"], m["home_team"])
        return None, None

    champion, runner_up = _winner(final)
    third_place, fourth_place = _winner(third)

    sched = fixtures.schedule()
    played = sorted([m for m in sched if m["played"]], key=lambda m: m["kickoff"])
    accuracy = news_mod.compute_accuracy(played)

    return {
        "final_played": final is not None and final.get("home_score") is not None,
        "champion": champion, "runner_up": runner_up,
        "third_place": third_place, "fourth_place": fourth_place,
        "final_match_id": 104, "third_place_match_id": 103,
        "accuracy": accuracy,
        "final_predicted_winner": (final or {}).get("model_predicted_winner")
                                   or (final or {}).get("predicted_winner"),
        "final_predicted_confidence": (final or {}).get("confidence"),
    }


@app.get("/api/health")
def health():
    from . import ml_engine
    e = ml_engine.engine()
    return {"ok": True, "environment": settings.environment,
            "members_loaded": {
                "dixon_coles": e.dc is not None,
                "elo": bool(e.elo),
                "xgboost": e.xgb is not None,
                "neural_net": e.nn is not None,
            }}


@app.on_event("startup")
def _startup():
    if settings.use_db:
        from .db import init_db
        init_db()
