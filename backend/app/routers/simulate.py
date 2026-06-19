"""Tournament simulator: standings, bracket odds, champion probabilities."""
from fastapi import APIRouter, Query

from .. import fixtures, ml_engine

router = APIRouter(prefix="/api/simulate", tags=["simulate"])


@router.get("")
def simulation(top: int = Query(48, le=48)):
    table = ml_engine.sim_table(top=top)
    return {
        "champion_odds": [{"team": r["team"],
                           "Champion": round(r.get("Champion", 0), 4),
                           "Final": round(r.get("Final", 0), 4),
                           "SF": round(r.get("SF", 0), 4),
                           "QF": round(r.get("QF", 0), 4),
                           "R32": round(r.get("R32", 0), 4)} for r in table],
        "dark_horses": ml_engine.dark_horses(6),
    }


@router.get("/groups")
def group_standings():
    """Live group standings (MP/W/D/L/GF/GA/GD/Pts from played matches) merged
    with simulated advancement + title probability. Ordered by actual points."""
    tables = fixtures.group_tables()
    sim = {r["team"]: r for r in ml_engine.sim_table()}
    tidx = fixtures.team_index()
    out = {}
    for g, rows in tables.items():
        out[g] = [{**r,
                   "flag_url": tidx.get(r["team"], {}).get("flag_url", ""),
                   "advance_prob": round(sim.get(r["team"], {}).get("R32", 0), 3),
                   "win_title": round(sim.get(r["team"], {}).get("Champion", 0), 3)}
                  for r in rows]
    return out
