"""Generate a realistic SAMPLE betting-odds cache for scheduled fixtures.

Real odds come from The Odds API (`ODDS_API_KEY` -> ml/odds.fetch_the_odds_api).
For offline dev/demo this writes data/raw/odds.csv with bookmaker-style decimal
odds: fair probabilities (Elo/Poisson) nudged by noise so the market is not a
pure echo of the model, then loaded with a ~5% overround (bookmaker margin).

Run:  python backend/seed_odds.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "ml"))

from app import fixtures            # noqa: E402
import poisson as poisson_mod       # noqa: E402
from config import RAW              # noqa: E402

MARGIN = 0.05          # 5% bookmaker overround
NOISE = 0.04           # market vs model divergence
rng = np.random.default_rng(7)


def _odds_for(home: str, away: str, neutral: bool) -> tuple[float, float, float]:
    elo = fixtures._elo()
    eh, ea = elo.get(home, 1500.0), elo.get(away, 1500.0)
    fair = np.array(poisson_mod.outcome_probs(eh, ea, neutral))
    fair = np.clip(fair + rng.normal(0, NOISE, 3), 0.02, None)
    fair = fair / fair.sum()
    implied = fair * (1 + MARGIN)          # add margin -> overround > 1
    o = 1.0 / implied
    return round(float(o[0]), 2), round(float(o[1]), 2), round(float(o[2]), 2)


def main():
    rows = []
    for m in fixtures.schedule():
        oh, od, oa = _odds_for(m["home_team"], m["away_team"], m["neutral"])
        rows.append({"home_team": m["home_team"], "away_team": m["away_team"],
                     "odds_home": oh, "odds_draw": od, "odds_away": oa})
    # marquee non-group fixture for demos
    oh, od, oa = _odds_for("Argentina", "France", True)
    rows.append({"home_team": "Argentina", "away_team": "France",
                 "odds_home": oh, "odds_draw": od, "odds_away": oa})

    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / "odds.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"[seed_odds] {len(rows)} fixtures -> {out}")
    print(pd.DataFrame(rows).head(4).to_string(index=False))


if __name__ == "__main__":
    main()
