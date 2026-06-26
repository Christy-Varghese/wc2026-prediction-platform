"""Teams: list + profile (squad, form, group + knockout progression)."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from .. import fixtures, ml_engine

router = APIRouter(prefix="/api/teams", tags=["teams"])


def _progression(name: str) -> dict | None:
    for r in ml_engine.sim_table():
        if r["team"] == name:
            return {"advance_R32": round(r.get("R32", 0), 3),
                    "reach_QF": round(r.get("QF", 0), 3),
                    "reach_SF": round(r.get("SF", 0), 3),
                    "reach_Final": round(r.get("Final", 0), 3),
                    "win_title": round(r.get("Champion", 0), 3)}
    return None


@router.get("")
def list_teams():
    return fixtures.teams()


@router.get("/{name}")
def team_profile(name: str):
    t = fixtures.team_index().get(name)
    if not t:
        raise HTTPException(404, "team not found")
    squad = ml_engine.squad_with_injuries(name, fixtures.squad(name))
    return {
        **t,
        "squad": squad,
        "key_players": fixtures.key_players(name),
        "availability": ml_engine.team_availability(name, fixtures.squad(name)),
        "injury_report": ml_engine.injuries_report(name),
        "group_rivals": [x for x in fixtures._draw().get(t["group"], []) if x != name],
        "progression": _progression(name),
    }


@router.get("/{name}/players")
def team_players(name: str):
    if name not in fixtures.team_index():
        raise HTTPException(404, "team not found")
    return fixtures.squad(name)
