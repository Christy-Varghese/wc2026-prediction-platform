"""Lightweight independent-Poisson goal model (Elo-driven).

Simpler sibling of the Dixon-Coles model: expected goals come from team Elo
and the league baseline, with no low-score correlation correction. Kept as a
distinct ensemble member so the blend has an independent view of scorelines.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import poisson

DEF_BASE = 1.35          # avg goals per side baseline
MAX_GOALS = 10


def expected_goals(elo_home: float, elo_away: float, neutral: bool = True,
                   home_adv: float = 65.0, base: float = DEF_BASE) -> tuple[float, float]:
    adv = 0.0 if neutral else home_adv
    diff = (elo_home + adv - elo_away) / 400.0
    p_home = 1.0 / (1.0 + 10 ** (-diff))
    total = base * 2.0
    lh = total * (0.30 + 0.40 * p_home)
    la = total * (0.30 + 0.40 * (1 - p_home))
    return float(lh), float(la)


def score_matrix(elo_home: float, elo_away: float, neutral: bool = True) -> np.ndarray:
    lh, la = expected_goals(elo_home, elo_away, neutral)
    ph = poisson.pmf(np.arange(MAX_GOALS + 1), lh)
    pa = poisson.pmf(np.arange(MAX_GOALS + 1), la)
    m = np.outer(ph, pa)
    return m / m.sum()


def outcome_probs(elo_home: float, elo_away: float, neutral: bool = True) -> tuple[float, float, float]:
    m = score_matrix(elo_home, elo_away, neutral)
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())
