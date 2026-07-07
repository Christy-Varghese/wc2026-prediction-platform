"""KIS — Knockout Intelligence System. Vector-decomposed match-flow report.

See KIS_SPEC.md §6.2 for the full design. This route is a thin FastAPI
wrapper around `ml_engine.kis()` -> `kis_engine.compose()` (backend/ml/) —
all of the actual vector math, Monte Carlo, and knockout-report logic lives
there, reused from `match_flow.py`/`ensemble.py`. Nothing here reimplements
prediction logic.

D4 (KIS_SPEC.md §10) resolved by precedent: like the existing `/api/predict`,
this route does not require `home`/`away` to be a real scheduled fixture —
any two valid team names work, enabling a future "what-if" simulator. Team
names ARE validated against `fixtures.team_index()` (unlike `/api/predict`,
which doesn't validate) since silently accepting a typo'd team name and
returning a plausible-looking but meaningless prediction is worse than a
clear 404.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import fixtures, ml_engine

router = APIRouter(prefix="/api/v1/predict", tags=["kis"])


class KISPredictionRequest(BaseModel):
    home_team: str
    away_team: str
    neutral: bool = True
    knockout: bool = True
    weather_condition: Literal["Clear", "Rain", "Extreme_Heat"] = "Clear"
    referee_strictness: float = Field(0.5, ge=0.0, le=1.0)
    # Optional real-venue override — when given, the actual venue climate
    # signal (weather.py) wins over `weather_condition` (see
    # kis_engine.chaos_sigma()'s docstring). Left None for a hypothetical
    # "what-if" matchup with no real venue.
    city: str | None = None
    kickoff_iso: str | None = None


@router.post("/kis")
def generate_kis_prediction(payload: KISPredictionRequest):
    teams = fixtures.team_index()
    for name in (payload.home_team, payload.away_team):
        if name not in teams:
            raise HTTPException(404, f"team not found: {name!r}")
    if payload.home_team == payload.away_team:
        raise HTTPException(400, "home_team and away_team must differ")

    base = ml_engine.predict_match(payload.home_team, payload.away_team, payload.neutral)
    return ml_engine.kis(
        payload.home_team, payload.away_team, base,
        knockout=payload.knockout, neutral=payload.neutral,
        weather_condition=payload.weather_condition,
        referee_strictness=payload.referee_strictness,
        city=payload.city, kickoff_iso=payload.kickoff_iso,
    )
