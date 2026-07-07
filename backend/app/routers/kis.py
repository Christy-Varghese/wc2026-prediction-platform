"""KIS — Knockout Intelligence System. Vector-decomposed match-flow report.

See KIS_SPEC.md §6.2 for the full design. This route is a thin FastAPI
wrapper around `ml_engine.kis()` -> `kis_engine.compose()` (backend/ml/) —
all of the actual vector math, Monte Carlo, and knockout-report logic lives
there, reused from `match_flow.py`/`ensemble.py`. Nothing here reimplements
prediction logic.

GET, not POST: matches this app's own convention (`GET /api/predict?home=&
away=`), and — the deciding factor — GET-with-querystring is what
`frontend/lib/api.ts`'s snapshot-fallback system and `gen_snapshots.py` are
built around. A POST-only route can never be pre-snapshotted for the
backend-free Vercel demo, which is exactly why the KIS card showed
"backend offline" there. See KIS_SPEC.md's snapshot-support status note.

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

from fastapi import APIRouter, HTTPException, Query

from .. import fixtures, ml_engine, services

router = APIRouter(prefix="/api/v1/predict", tags=["kis"])


@router.get("/kis")
def generate_kis_prediction(
    home_team: str, away_team: str,
    neutral: bool = True, knockout: bool = True,
    weather_condition: Literal["Clear", "Rain", "Extreme_Heat"] = "Clear",
    referee_strictness: float = Query(0.5, ge=0.0, le=1.0),
    # Optional real-venue override — when given, the actual venue climate
    # signal (weather.py) wins over `weather_condition` (see
    # kis_engine.chaos_sigma()'s docstring). Left None for a hypothetical
    # "what-if" matchup with no real venue.
    city: str | None = None, kickoff_iso: str | None = None,
):
    teams = fixtures.team_index()
    for name in (home_team, away_team):
        if name not in teams:
            raise HTTPException(404, f"team not found: {name!r}")
    if home_team == away_team:
        raise HTTPException(400, "home_team and away_team must differ")

    # services.predict() (not ml_engine.predict_match() directly) so `base`
    # carries the same injury-availability + squad-strength-differential
    # context (_ctx_for()) every other prediction on the site builds — the
    # bracket's knockout_engine._resolve_tie() goes through this exact path.
    # Skipping it silently drops real signal and materially shifts
    # `confidence` (observed up to ~20pt swings without it).
    base = services.predict(home_team, away_team, neutral=neutral)
    return ml_engine.kis(
        home_team, away_team, base,
        knockout=knockout, neutral=neutral,
        weather_condition=weather_condition,
        referee_strictness=referee_strictness,
        city=city, kickoff_iso=kickoff_iso,
    )
