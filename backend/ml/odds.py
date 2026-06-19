"""Betting-odds provider + vig removal.

Market odds are the single strongest match predictor, so they enter the
ensemble as a high-weight member. This module:

  1. loads decimal odds from a local cache CSV (offline / demo / backtest), and
  2. optionally refreshes that cache from The Odds API when ODDS_API_KEY is set,
  3. converts bookmaker decimal odds -> de-vigged implied probabilities.

CSV schema (data/raw/odds.csv):
    home_team,away_team,odds_home,odds_draw,odds_away
Decimal (European) odds, e.g. 2.10,3.40,3.60.
"""
from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
import pandas as pd

from config import RAW

ODDS_CSV = RAW / "odds.csv"
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_SPORT = os.getenv("ODDS_API_SPORT", "soccer_fifa_world_cup")


def decimal_to_probs(o_home: float, o_draw: float, o_away: float) -> np.ndarray:
    """Decimal odds -> de-vigged [pHome, pDraw, pAway] (margin removed)."""
    imp = np.array([1.0 / o_home, 1.0 / o_draw, 1.0 / o_away])
    overround = imp.sum()                    # > 1.0 = bookmaker margin
    return imp / overround


def overround(o_home: float, o_draw: float, o_away: float) -> float:
    return float(1.0 / o_home + 1.0 / o_draw + 1.0 / o_away)


class OddsBook:
    """Lookup table of market probabilities keyed by (home, away)."""

    def __init__(self, df: pd.DataFrame | None = None):
        self._book: dict[tuple[str, str], dict] = {}
        if df is not None:
            self._ingest(df)

    def _ingest(self, df: pd.DataFrame):
        for r in df.itertuples(index=False):
            try:
                probs = decimal_to_probs(r.odds_home, r.odds_draw, r.odds_away)
            except (ZeroDivisionError, AttributeError):
                continue
            self._book[(r.home_team, r.away_team)] = {
                "probs": [float(x) for x in probs],
                "overround": round(overround(r.odds_home, r.odds_draw, r.odds_away), 4),
            }

    def lookup(self, home: str, away: str) -> dict | None:
        """Returns {'probs':[H,D,A], 'overround':x} or None. Handles flipped order."""
        if (home, away) in self._book:
            return self._book[(home, away)]
        if (away, home) in self._book:           # stored reversed -> flip H/A
            d = self._book[(away, home)]
            p = d["probs"]
            return {"probs": [p[2], p[1], p[0]], "overround": d["overround"]}
        return None

    def __len__(self):
        return len(self._book)


@lru_cache
def get_book() -> OddsBook:
    if ODDS_CSV.exists():
        return OddsBook(pd.read_csv(ODDS_CSV))
    return OddsBook()


def reload_book() -> OddsBook:
    get_book.cache_clear()
    return get_book()


# ---------------------------------------------------------------- live refresh
def fetch_the_odds_api(api_key: str | None = None) -> int:
    """Refresh the local cache from The Odds API. Returns rows written.

    Free tier: https://the-odds-api.com — set ODDS_API_KEY. No-ops (returns 0)
    if no key/network so the rest of the stack is unaffected.
    """
    key = api_key or ODDS_API_KEY
    if not key:
        return 0
    import requests
    url = f"https://api.the-odds-api.com/v4/sports/{ODDS_API_SPORT}/odds"
    params = {"apiKey": key, "regions": "uk,eu", "markets": "h2h",
              "oddsFormat": "decimal"}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    rows = []
    for ev in resp.json():
        home, away = ev.get("home_team"), ev.get("away_team")
        prices: dict[str, list[float]] = {}
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                if mk.get("key") != "h2h":
                    continue
                for oc in mk["outcomes"]:
                    prices.setdefault(oc["name"], []).append(oc["price"])
        if home in prices and away in prices and "Draw" in prices:
            rows.append({
                "home_team": home, "away_team": away,
                "odds_home": float(np.median(prices[home])),
                "odds_draw": float(np.median(prices["Draw"])),
                "odds_away": float(np.median(prices[away])),
            })
    if rows:
        RAW.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(ODDS_CSV, index=False)
        reload_book()
    return len(rows)
