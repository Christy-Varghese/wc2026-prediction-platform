"""World-football Elo ratings computed from match history.

Margin-of-victory scaled K, home-field advantage. Produces a rating
per team that the Dixon-Coles model and the sim consume as a strength prior.
"""
from __future__ import annotations

import math
import pandas as pd

from config import (ELO_START, ELO_K, ELO_HOME_ADV, ELO_MOV, PROC)


def _expected(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


def _mov_mult(goal_diff: int, elo_diff: float) -> float:
    """Goal-difference multiplier (FiveThirtyEight-style)."""
    if not ELO_MOV:
        return 1.0
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    return math.log(gd + 1) * (2.2 / (0.001 * abs(elo_diff) + 2.2))


def compute(df: pd.DataFrame) -> tuple[dict[str, float], pd.DataFrame]:
    """Run Elo forward over sorted matches.

    Returns (final ratings dict, df with pre-match home/away ratings attached).
    """
    ratings: dict[str, float] = {}
    home_pre, away_pre = [], []

    for row in df.itertuples(index=False):
        h, a = row.home_team, row.away_team
        rh = ratings.get(h, ELO_START)
        ra = ratings.get(a, ELO_START)
        home_pre.append(rh)
        away_pre.append(ra)

        adv = 0.0 if row.neutral else ELO_HOME_ADV
        exp_h = _expected(rh + adv, ra)
        score_h = 1.0 if row.result == "H" else 0.5 if row.result == "D" else 0.0

        gd = row.home_score - row.away_score
        k = ELO_K * _mov_mult(gd, (rh + adv) - ra)
        delta = k * (score_h - exp_h)

        ratings[h] = rh + delta
        ratings[a] = ra - delta

    out = df.copy()
    out["home_elo"] = home_pre
    out["away_elo"] = away_pre
    return ratings, out


def main() -> None:
    df = pd.read_parquet(PROC / "results_clean.parquet")
    ratings, enriched = compute(df)
    enriched.to_parquet(PROC / "results_elo.parquet")
    sr = pd.Series(ratings).sort_values(ascending=False)
    sr.to_frame("elo").to_parquet(PROC / "elo_ratings.parquet")
    print("[elo] top 20:")
    print(sr.head(20).round(0).to_string())


if __name__ == "__main__":
    main()
