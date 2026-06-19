"""Matches: list (filterable) + full detail with prediction."""
from fastapi import APIRouter, HTTPException, Query

from .. import fixtures, match_analytics, services

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("")
def list_matches(group: str | None = None, team: str | None = None,
                 date: str | None = None, matchday: str | None = None,
                 upcoming: bool = False, limit: int = Query(120, le=200),
                 predictions: bool = True):
    rows = fixtures.schedule()
    if group:
        rows = [m for m in rows if m["group"].upper() == group.upper()]
    if team:
        rows = [m for m in rows
                if team.lower() in (m["home_team"].lower(), m["away_team"].lower())]
    if date:
        rows = [m for m in rows if m["kickoff"].startswith(date)]
    if matchday:
        rows = [m for m in rows if m["matchday"].upper() == matchday.upper()]
    if upcoming:
        rows = [m for m in rows if not m.get("played")]
    rows.sort(key=lambda m: m["kickoff"])  # chronological
    rows = rows[:limit]
    if predictions:
        return [services.match_card(m) for m in rows]
    return rows


@router.get("/{match_id}")
def match_detail(match_id: int):
    d = services.match_detail(match_id)
    if not d:
        raise HTTPException(404, "match not found")
    return d


@router.get("/{match_id}/analytics")
def match_analytics_view(match_id: int):
    """AI-generated post-match analytics (scorers, shot map, heat map, passing
    network, box score). Only available once the match is played."""
    a = match_analytics.analytics(match_id)
    if a is None:
        raise HTTPException(404, "match not played yet")
    return a
