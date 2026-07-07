"""Tournament momentum: apply WC 2026 in-tournament micro-Elo updates.

As group-stage matches are played, we update each team's Elo rating on top of
the trained baseline using the ACTUAL WC2026 results. This means:

  - A 3-0 Argentina win vs Algeria immediately boosts Argentina's rating
  - A shock loss by a favourite immediately deflates that team's rating
  - All ensemble members (Elo, DC's attack/defence rates proxy, XGBoost) get
    more accurate team-strength estimates for remaining matches

The updates use the same FiveThirtyEight-style formula as elo.py but with a
SMALLER K (= 20 instead of 40) since WC group matches have high variance and
we don't want to over-react to a single result. Knockout-stage results get a
higher K (= 30) — single-elimination, no dead rubbers/rotation to explain away
a shock result, so a knockout win/loss should move ratings faster than a group
game did.

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
# Knockout-stage results are higher-signal (no dead rubbers, full effort every
# game) so they get a bigger nudge — but still below the full 40 used to train
# the pre-tournament prior, so a single shootout fluke can't swing a team's
# rating for the rest of the bracket.
TOURNEY_K_KNOCKOUT = 30.0
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
# WC 2026 results played so far — split into group stage and knockout stage
# so apply_tournament_updates() can apply TOURNEY_K to one and
# TOURNEY_K_KNOCKOUT to the other. WC2026_PLAYED (below) concatenates both,
# in play order, for every OTHER consumer (knockout_engine, real_bracket,
# tournament_stats, match_flow, backtest, tune_condition_coef) — none of them
# need to change.
# Format: (home, away, home_score, away_score, neutral)
# ---------------------------------------------------------------------------
# Mirrors the canonical played games in app/fixtures.py (group stage) and
# app/knockout.json (knockout stage). Kept in lock-step with those sources —
# whenever a result is ingested there, add the same (home, away, hs, as,
# neutral) row to WC2026_PLAYED_GROUP (group stage; frozen now that the
# group stage is complete) or WC2026_PLAYED_KNOCKOUT (Round of 32 onward) so
# the form/Elo engine used to predict remaining ties never falls behind
# reality. A drawn knockout tie decided on penalties is recorded as its
# 90'/ET score (a draw) — the shootout itself isn't modeled in Elo.
# neutral=False only when a host nation (USA / Mexico / Canada) plays a
# match in its own country.
WC2026_PLAYED_GROUP: list[tuple[str, str, int, int, bool]] = [
    # ── Matchday 1 ──
    ("Mexico",          "South Africa",            2, 0, False),
    ("South Korea",     "Czech Republic",          2, 1, True),
    ("Canada",          "Bosnia and Herzegovina",  1, 1, False),
    ("United States",   "Paraguay",                4, 1, False),
    ("Qatar",           "Switzerland",             1, 1, True),
    ("Brazil",          "Morocco",                 1, 1, True),
    ("Haiti",           "Scotland",                0, 1, True),
    ("Australia",       "Turkey",                  2, 0, True),
    ("Germany",         "Curaçao",                 7, 1, True),
    ("Netherlands",     "Japan",                   2, 2, True),
    ("Ivory Coast",     "Ecuador",                 1, 0, True),
    ("Sweden",          "Tunisia",                 5, 1, True),
    ("Spain",           "Cape Verde",              0, 0, True),
    ("Belgium",         "Egypt",                   1, 1, True),
    ("Saudi Arabia",    "Uruguay",                 1, 1, True),
    ("Iran",            "New Zealand",             2, 2, True),
    ("France",          "Senegal",                 3, 1, True),
    ("Iraq",            "Norway",                  1, 4, True),
    ("Argentina",       "Algeria",                 3, 0, True),
    ("Austria",         "Jordan",                  3, 1, True),
    ("Portugal",        "DR Congo",                1, 1, True),
    ("England",         "Croatia",                 4, 2, True),
    ("Ghana",           "Panama",                  1, 0, True),
    ("Uzbekistan",      "Colombia",                1, 3, True),
    # ── Matchday 2 (played so far) ──
    ("Czech Republic",  "South Africa",            1, 1, True),
    ("Switzerland",     "Bosnia and Herzegovina",  4, 1, True),
    ("Canada",          "Qatar",                   6, 0, False),
    ("Mexico",          "South Korea",             1, 0, False),
    ("United States",   "Australia",               2, 0, False),
    ("Scotland",        "Morocco",                 0, 1, True),
    ("Brazil",          "Haiti",                   3, 0, True),
    ("Paraguay",        "Turkey",                  1, 0, True),
    ("Netherlands",     "Sweden",                  5, 1, True),
    ("Germany",         "Ivory Coast",             2, 1, True),
    ("Ecuador",         "Curaçao",                 0, 0, True),
    ("Tunisia",         "Japan",                   0, 4, True),
    ("Spain",           "Saudi Arabia",            4, 0, True),
    ("Belgium",         "Iran",                    0, 0, True),
    ("Uruguay",         "Cape Verde",              2, 2, True),
    ("Argentina",       "Austria",                 2, 0, True),
    ("New Zealand",     "Egypt",                   1, 3, True),
    ("France",          "Iraq",                    3, 0, True),
    ("Norway",          "Senegal",                 3, 2, True),
    ("Jordan",          "Algeria",                 1, 2, True),
    ("Portugal",        "Uzbekistan",              5, 0, True),
    ("England",         "Ghana",                   0, 0, True),
    ("Panama",          "Croatia",                 0, 1, True),
    ("Colombia",        "DR Congo",                1, 0, True),
    # ── Matchday 3 (Jun 24) ──
    ("Switzerland",     "Canada",                  2, 1, False),
    ("Bosnia and Herzegovina", "Qatar",            3, 1, True),
    ("Scotland",        "Brazil",                  0, 3, True),
    ("Morocco",         "Haiti",                   4, 2, True),
    ("South Africa",    "South Korea",             1, 0, True),
    ("Czech Republic",  "Mexico",                  0, 3, False),
    # ── Matchday 3 (Jun 25) ──
    ("Ecuador",         "Germany",                 2, 1, True),
    ("Curaçao",         "Ivory Coast",             0, 2, True),
    ("Japan",           "Sweden",                  1, 1, True),
    ("Tunisia",         "Netherlands",             1, 3, True),
    ("Turkey",          "United States",           3, 2, True),
    ("Paraguay",        "Australia",               0, 0, True),
    # ── Matchday 3 (Jun 26) ──
    ("Norway",          "France",                  1, 4, True),
    ("Senegal",         "Iraq",                    5, 0, True),
    ("Cape Verde",      "Saudi Arabia",            0, 0, True),
    ("Uruguay",         "Spain",                   0, 1, True),
    ("Egypt",           "Iran",                    1, 1, True),
    ("New Zealand",     "Belgium",                 1, 5, True),
    # ── Matchday 3 (Jun 27) ──
    ("Panama",          "England",                 0, 2, True),
    ("Croatia",         "Ghana",                   2, 1, True),
    ("Colombia",        "Portugal",                0, 0, True),
    ("DR Congo",        "Uzbekistan",              3, 1, True),
    ("Algeria",         "Austria",                 3, 3, True),
    ("Jordan",          "Argentina",               1, 3, True),
]

WC2026_PLAYED_KNOCKOUT: list[tuple[str, str, int, int, bool]] = [
    # ── Round of 32 (Jun 28-29) ──
    ("South Africa",    "Canada",                  0, 1, True),
    ("Brazil",          "Japan",                   2, 1, True),
    ("Germany",         "Paraguay",                1, 1, True),  # Paraguay won 4-3 pens
    ("Netherlands",     "Morocco",                 1, 1, True),  # Morocco won 3-2 pens
    # ── Round of 32 (Jun 29 - Jul 3) ──
    ("France",          "Sweden",                  3, 0, True),
    ("Ivory Coast",     "Norway",                  1, 2, True),
    ("Mexico",          "Ecuador",                 2, 0, False),  # host, Mexico City
    ("England",         "DR Congo",                2, 1, True),
    ("United States",   "Bosnia and Herzegovina",  2, 0, False),  # host, San Francisco
    ("Belgium",         "Senegal",                 3, 2, True),
    ("Portugal",        "Croatia",                 2, 1, True),
    ("Spain",           "Austria",                 3, 0, True),
    ("Switzerland",     "Algeria",                 2, 0, True),
    ("Australia",       "Egypt",                   1, 1, True),  # Egypt won 4-2 pens
    ("Argentina",       "Cape Verde",              3, 2, True),  # AET
    ("Colombia",        "Ghana",                   1, 0, True),
    # ── Round of 16 (Jul 4) ──
    ("Canada",          "Morocco",                 0, 3, True),
    ("Paraguay",        "France",                  0, 1, True),
    # ── Round of 16 (Jul 5) ──
    ("Brazil",          "Norway",                  1, 2, True),
    ("Mexico",          "England",                 2, 3, True),
    # ── Round of 16 (Jul 6) ──
    ("Portugal",        "Spain",                   0, 1, True),
    ("United States",   "Belgium",                 1, 4, False),  # host, Seattle
]

# Full play-order ledger for consumers that don't care about stage (form/
# stats/bracket resolution) — see the module docstring above.
WC2026_PLAYED: list[tuple[str, str, int, int, bool]] = WC2026_PLAYED_GROUP + WC2026_PLAYED_KNOCKOUT


@lru_cache(maxsize=1)
def apply_tournament_updates(base_elo: tuple[tuple[str, float], ...]) -> dict[str, float]:
    """Apply WC2026 in-tournament results on top of trained Elo.

    Args:
        base_elo: tuple of (team, rating) pairs (hashable for lru_cache).

    Returns:
        Updated ratings dict {team: elo}.
    """
    ratings: dict[str, float] = dict(base_elo)

    games = (
        [(m, TOURNEY_K) for m in WC2026_PLAYED_GROUP]
        + [(m, TOURNEY_K_KNOCKOUT) for m in WC2026_PLAYED_KNOCKOUT]
    )
    for (home, away, hs, as_, neutral), base_k in games:
        rh = ratings.get(home, 1500.0)
        ra = ratings.get(away, 1500.0)

        adv = 0.0 if neutral else ELO_HOME_ADV
        exp_h = _expected(rh + adv, ra)
        score_h = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0

        gd = hs - as_
        k = base_k * _mov_mult(gd, (rh + adv) - ra)
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
