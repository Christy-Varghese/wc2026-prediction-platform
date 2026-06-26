"""Players: single player profile lookup."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from .. import fixtures

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("/{team}/{name}")
def player_profile(team: str, name: str):
    for p in fixtures.squad(team):
        if p["name"].lower() == name.lower():
            return {**p, "team": team,
                    "impact_breakdown": {
                        "finishing": p["goals"], "creation": p["assists"],
                        "expected": round(p["xg"] + p["xa"], 1),
                        "rating": p["impact"]}}
    raise HTTPException(404, "player not found")
