"""Live injuries / suspensions feed + availability scoring.

Same shape as odds.py: a local cache CSV for offline/demo, an optional live
fetch (API-Football) when INJURY_API_KEY is set, and helpers that turn team
news into an *impact-weighted* availability factor that feeds the ensemble's
`avail_diff` feature.

CSV schema (data/raw/injuries.csv):
    team,player,kind,status,detail,return_date
    kind   = injury | suspension
    status = out | doubt
"""
from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

from config import RAW

INJ_CSV = RAW / "injuries.csv"
INJURY_API_KEY = os.getenv("INJURY_API_KEY", "")
DOUBT_WEIGHT = 0.4          # a doubtful player counts as 40% of an absence


class InjuryBook:
    def __init__(self, df: pd.DataFrame | None = None):
        self._by_team: dict[str, list[dict]] = {}
        if df is not None:
            for r in df.itertuples(index=False):
                # impact_score column (0-100): how much does this player matter?
                # Defaults to 70 (solid starter) when column is absent.
                impact = int(getattr(r, "impact_score", 70) or 70)
                self._by_team.setdefault(r.team, []).append({
                    "player": r.player, "kind": getattr(r, "kind", "injury"),
                    "status": getattr(r, "status", "out"),
                    "detail": getattr(r, "detail", "") or "",
                    "return_date": str(getattr(r, "return_date", "") or ""),
                    "impact_score": impact,
                })

    def report(self, team: str) -> list[dict]:
        return self._by_team.get(team, [])

    def __len__(self):
        return sum(len(v) for v in self._by_team.values())


@lru_cache
def get_book() -> InjuryBook:
    if INJ_CSV.exists():
        return InjuryBook(pd.read_csv(INJ_CSV))
    return InjuryBook()


def reload_book() -> InjuryBook:
    get_book.cache_clear()
    return get_book()


def report(team: str) -> list[dict]:
    return get_book().report(team)


def availability_factor(team: str, squad: list[dict]) -> float:
    """Impact-weighted availability in [0,1]. A star out hurts more than a sub.

    Uses impact_score from injuries.csv when present (0-100 scale), else falls
    back to the player's squad impact rating. Messi/Mbappé absences (impact≥90)
    are therefore correctly modelled as major disruptions.
    """
    if not squad:
        return 1.0
    inj_report = {r["player"]: r for r in report(team)}
    total = sum(max(p.get("impact", 50), 1) for p in squad)
    lost = 0.0
    for p in squad:
        inj = inj_report.get(p["name"])
        if inj:
            s = inj["status"]
            # prefer the injury book's impact_score over the squad's generic one
            w = max(inj.get("impact_score", p.get("impact", 70)), 1)
        else:
            s = p.get("fitness", "fit")
            w = max(p.get("impact", 50), 1)
        if s == "out":
            lost += w
        elif s == "doubt":
            lost += DOUBT_WEIGHT * w
    return round(max(0.0, 1.0 - lost / total), 4)


def apply_to_squad(team: str, squad: list[dict]) -> list[dict]:
    """Overlay live injury status onto a squad's fitness field."""
    status = {r["player"]: r for r in report(team)}
    out = []
    for p in squad:
        r = status.get(p["name"])
        if r:
            out.append({**p, "fitness": r["status"],
                        "news": f"{r['kind']}: {r['detail']}".strip(": "),
                        "return_date": r["return_date"]})
        else:
            out.append(p)
    return out


# ---------------------------------------------------------------- live refresh
def fetch_api_football(api_key: str | None = None,
                       league: int = 1, season: int = 2026) -> int:
    """Refresh cache from API-Football injuries endpoint. Returns rows written.

    Requires INJURY_API_KEY (api-sports.io). No-ops (returns 0) without a key
    so the stack runs offline on the sample cache.
    """
    key = api_key or INJURY_API_KEY
    if not key:
        return 0
    import requests
    resp = requests.get(
        "https://v3.football.api-sports.io/injuries",
        headers={"x-apisports-key": key},
        params={"league": league, "season": season}, timeout=30)
    resp.raise_for_status()
    rows = []
    for it in resp.json().get("response", []):
        pl, team = it.get("player", {}), it.get("team", {})
        typ = (pl.get("type") or "").lower()
        rows.append({
            "team": team.get("name", ""), "player": pl.get("name", ""),
            "kind": "suspension" if "suspend" in typ else "injury",
            "status": "doubt" if "doubt" in (pl.get("reason") or "").lower() else "out",
            "detail": pl.get("reason", ""), "return_date": "",
        })
    if rows:
        RAW.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(INJ_CSV, index=False)
        reload_book()
    return len(rows)
