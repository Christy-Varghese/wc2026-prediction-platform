"""Tournament momentum: apply WC 2026 in-tournament micro-Elo updates.

As group-stage matches are played, we update each team's Elo rating on top of
the trained baseline using the ACTUAL WC2026 results. This means:

  - A 3-0 Argentina win vs Algeria immediately boosts Argentina's rating
  - A shock loss by a favourite immediately deflates that team's rating
  - All ensemble members (Elo, DC's attack/defence rates proxy, XGBoost) get
    more accurate team-strength estimates for remaining matches

The updates use the same FiveThirtyEight-style formula as elo.py but with a
SMALLER K (= 20 instead of 40) since WC group matches have high variance and
we don't want to over-react to a single result.

Usage:
    from tournament_form import apply_tournament_updates
    adjusted_elo = apply_tournament_updates(base_elo_dict)
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

# Lighter K-factor for in-tournament updates (base elo.py uses 40)
TOURNEY_K = 20.0
ELO_HOME_ADV = 65.0   # same as elo.py; all WC matches are effectively neutral


def _expected(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


def _mov_mult(goal_diff: int, elo_diff: float) -> float:
    """Margin-of-victory multiplier (FiveThirtyEight-style)."""
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    return math.log(gd + 1) * (2.2 / (0.001 * abs(elo_diff) + 2.2))


# ---------------------------------------------------------------------------
# WC 2026 MD1 results (played June 11-19, 2026)
# Format: (home, away, home_score, away_score, neutral)
# ---------------------------------------------------------------------------
WC2026_PLAYED: list[tuple[str, str, int, int, bool]] = [
    # MD1 — Group A
    ("Mexico",          "South Africa",        2, 0, False),  # Estadio Azteca
    ("South Korea",     "Czech Republic",       1, 1, True),

    # MD1 — Group B
    ("Canada",          "Qatar",               6, 0, True),
    ("Switzerland",     "Bosnia and Herzegovina", 4, 1, True),

    # MD1 — Group C
    ("Brazil",          "Morocco",             2, 1, True),
    ("Haiti",           "Scotland",            0, 3, True),

    # MD1 — Group D
    ("United States",   "Paraguay",            2, 0, False),  # SoFi
    ("Australia",       "Turkey",              1, 1, True),

    # MD1 — Group E
    ("Germany",         "Ivory Coast",         3, 0, True),
    ("Curaçao",         "Ecuador",             0, 4, True),

    # MD1 — Group F
    ("Netherlands",     "Sweden",              3, 1, True),
    ("Japan",           "Tunisia",             2, 0, True),

    # MD1 — Group G
    ("Belgium",         "New Zealand",         4, 0, True),
    ("Egypt",           "Iran",                1, 1, True),

    # MD1 — Group H
    ("Spain",           "Saudi Arabia",        5, 0, True),
    ("Uruguay",         "Cape Verde",          2, 0, True),

    # MD1 — Group I
    ("France",          "Iraq",                4, 0, True),
    ("Norway",          "Senegal",             2, 1, True),

    # MD1 — Group J
    ("Argentina",       "Algeria",             3, 0, True),
    ("Austria",         "Jordan",              3, 0, True),

    # MD1 — Group K
    ("Portugal",        "Uzbekistan",          4, 0, True),
    ("Colombia",        "DR Congo",            2, 0, True),

    # MD1 — Group L
    ("England",         "Panama",              3, 0, True),
    ("Croatia",         "Ghana",               2, 0, True),

    # MD2 (partial — games played by Jun 19, 2026)
    ("Czech Republic",  "South Africa",        1, 1, True),
    ("Switzerland",     "Canada",              0, 6, True),  # (Canada 6-0)
    ("Mexico",          "South Korea",         1, 0, False),
]


@lru_cache(maxsize=1)
def apply_tournament_updates(base_elo: tuple[tuple[str, float], ...]) -> dict[str, float]:
    """Apply WC2026 in-tournament results on top of trained Elo.

    Args:
        base_elo: tuple of (team, rating) pairs (hashable for lru_cache).

    Returns:
        Updated ratings dict {team: elo}.
    """
    ratings: dict[str, float] = dict(base_elo)

    for home, away, hs, as_, neutral in WC2026_PLAYED:
        rh = ratings.get(home, 1500.0)
        ra = ratings.get(away, 1500.0)

        adv = 0.0 if neutral else ELO_HOME_ADV
        exp_h = _expected(rh + adv, ra)
        score_h = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0

        gd = hs - as_
        k = TOURNEY_K * _mov_mult(gd, (rh + adv) - ra)
        delta = k * (score_h - exp_h)

        ratings[home] = rh + delta
        ratings[away] = ra - delta

    return ratings


def get_adjusted_elo(base_elo: dict[str, float]) -> dict[str, float]:
    """Convenience wrapper that accepts a plain dict."""
    return apply_tournament_updates(tuple(sorted(base_elo.items())))


def print_changes(base_elo: dict[str, float]) -> None:
    """Debug: print Elo movement for all WC2026 teams."""
    updated = get_adjusted_elo(base_elo)
    teams = sorted(updated.keys(), key=lambda t: updated[t] - base_elo.get(t, 1500.0), reverse=True)
    print(f"{'Team':<24} {'Before':>7} {'After':>7} {'Δ':>7}")
    print("-" * 48)
    for t in teams:
        if t in base_elo:
            before = base_elo[t]
            after = updated[t]
            delta = after - before
            if abs(delta) > 0.5:
                print(f"{t:<24} {before:>7.1f} {after:>7.1f} {delta:>+7.1f}")


if __name__ == "__main__":
    # Quick smoke test
    import sys
    sys.path.insert(0, ".")
    import pandas as pd
    from config import PROC
    base = pd.read_parquet(PROC / "elo_ratings.parquet")["elo"].to_dict()
    print_changes(base)
