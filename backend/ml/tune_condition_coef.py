"""Sweep CONDITION_COEF on completed WC2026 matches to find the optimal value.

Usage:
    cd backend/ml && python tune_condition_coef.py

The script builds ensemble predictions for every played match (without
seeing the result) and measures log-loss and outcome accuracy over a grid
of CONDITION_COEF values. The best value should replace the constant in
ensemble.py.

Output:
    - Table of coef → log_loss, accuracy, avg_correct_prob
    - Recommendation (lowest log-loss)
    - Writes best value to data/processed/condition_coef_tune.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml"))

from tournament_form import WC2026_PLAYED
import ensemble as ens_mod
from ensemble import Ensemble, MatchContext, DRAW_PROB_MIN, DRAW_BALANCE
from player_condition import TeamConditionEngine

PROC = ROOT / "data" / "processed"
OUT  = PROC / "condition_coef_tune.json"

# Coefficient grid to test (covers the realistic range)
COEF_GRID = [0.0, 0.3, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 2.0, 2.45, 3.0]

# Completed WC2026 matches + true outcomes
PLAYED_MATCHES = [
    # (home, away, outcome)   0=home, 1=draw, 2=away
    # Group stage (sampled — use all 72 for best sweep, but penalties excluded)
    ("Mexico",        "South Africa",           0),
    ("South Korea",   "Czech Republic",         0),
    ("Canada",        "Bosnia and Herzegovina", 1),
    ("United States", "Paraguay",               0),
    ("Qatar",         "Switzerland",            1),
    ("Brazil",        "Morocco",                1),
    ("Haiti",         "Scotland",               2),
    ("Australia",     "Turkey",                 0),
    ("Germany",       "Curaçao",                0),
    ("Netherlands",   "Japan",                  1),
    ("Ivory Coast",   "Ecuador",                0),
    ("Sweden",        "Tunisia",                0),
    ("Spain",         "Cape Verde",             1),
    ("Belgium",       "Egypt",                  1),
    ("Saudi Arabia",  "Uruguay",                1),
    ("Iran",          "New Zealand",            1),
    ("France",        "Senegal",                0),
    ("Iraq",          "Norway",                 2),
    ("Argentina",     "Algeria",                0),
    ("Austria",       "Jordan",                 0),
    ("Portugal",      "DR Congo",               1),
    ("England",       "Croatia",                0),
    ("Ghana",         "Panama",                 0),
    ("Uzbekistan",    "Colombia",               2),
    # MD2
    ("Czech Republic","South Africa",           1),
    ("Switzerland",   "Bosnia and Herzegovina", 0),
    ("Canada",        "Qatar",                  0),
    ("Mexico",        "South Korea",            0),
    ("United States", "Australia",              0),
    ("Scotland",      "Morocco",                2),
    ("Brazil",        "Haiti",                  0),
    ("Paraguay",      "Turkey",                 0),
    ("Netherlands",   "Sweden",                 0),
    ("Germany",       "Ivory Coast",            0),
    ("Ecuador",       "Curaçao",                1),
    ("Tunisia",       "Japan",                  2),
    ("Spain",         "Saudi Arabia",           0),
    ("Belgium",       "Iran",                   1),
    ("Uruguay",       "Cape Verde",             1),
    ("Argentina",     "Austria",                0),
    ("New Zealand",   "Egypt",                  2),
    ("France",        "Iraq",                   0),
    ("Norway",        "Senegal",                0),
    ("Jordan",        "Algeria",                2),
    ("Portugal",      "Uzbekistan",             0),
    ("England",       "Ghana",                  1),
    ("Panama",        "Croatia",                2),
    ("Colombia",      "DR Congo",               0),
    # MD3
    ("Switzerland",   "Canada",                 0),
    ("Bosnia and Herzegovina", "Qatar",         0),
    ("Scotland",      "Brazil",                 2),
    ("Morocco",       "Haiti",                  0),
    ("South Africa",  "South Korea",            0),
    ("Czech Republic","Mexico",                 2),
    ("Ecuador",       "Germany",                0),
    ("Curaçao",       "Ivory Coast",            2),
    ("Japan",         "Sweden",                 1),
    ("Tunisia",       "Netherlands",            2),
    ("Turkey",        "United States",          0),
    ("Paraguay",      "Australia",              1),
    ("Norway",        "France",                 2),
    ("Senegal",       "Iraq",                   0),
    ("Cape Verde",    "Saudi Arabia",           1),
    ("Uruguay",       "Spain",                  2),
    ("Egypt",         "Iran",                   1),
    ("New Zealand",   "Belgium",                2),
    ("Panama",        "England",                2),
    ("Croatia",       "Ghana",                  0),
    ("Colombia",      "Portugal",               1),
    ("DR Congo",      "Uzbekistan",             0),
    ("Algeria",       "Austria",                1),
    ("Jordan",        "Argentina",              2),
    # R32 (no penalties — purely model-predicted outcomes)
    ("South Africa",  "Canada",                 2),
    ("Brazil",        "Japan",                  0),
    ("Ivory Coast",   "Norway",                 2),
]


def _log_loss(probs: list[float], y: list[int]) -> float:
    eps = 1e-9
    return float(-np.mean([np.log(max(p[yi], eps)) for p, yi in zip(probs, y)]))


def _accuracy(preds: list[int], y: list[int]) -> float:
    return float(np.mean([p == yi for p, yi in zip(preds, y)]))


def sweep():
    base_engine = Ensemble()
    cond_engine = TeamConditionEngine()

    results = []
    for coef in COEF_GRID:
        probs_all, preds_all, y_all = [], [], []

        for home, away, true_outcome in PLAYED_MATCHES:
            ctx = MatchContext()
            # Get base blend (without condition shift)
            members_raw = base_engine._member_probs(home, away, neutral=True, ctx=ctx)
            members_raw.pop("_market_real", None)
            members = members_raw
            eff_w = dict(base_engine.weights)
            w = np.array([eff_w.get(k, 0.0) for k in members])
            w /= w.sum()
            stack = np.vstack([members[k] for k in members])
            blended = (w[:, None] * stack).sum(0)
            blended = blended / blended.sum()
            blended = base_engine.calibrator(blended)
            blended = base_engine._availability_adjust(blended, ctx.avail_diff)
            blended = base_engine._conditions_adjust(blended, ctx)

            # Apply condition shift at this coef value
            if coef > 0:
                cond_info = cond_engine.match_condition_adjustment(
                    home, away, include_momentum=False)
                shift = cond_info["logit_shift"]
                if abs(shift) > 1e-6:
                    ph, pd_, pa = blended
                    ph = np.exp(np.log(max(ph, 1e-9)) + coef * shift)
                    pa = np.exp(np.log(max(pa, 1e-9)) - coef * shift)
                    blended = np.array([ph, pd_, pa])
                    blended /= blended.sum()

            ph, pd_, pa = float(blended[0]), float(blended[1]), float(blended[2])
            probs_all.append([ph, pd_, pa])

            if pd_ >= DRAW_PROB_MIN and abs(ph - pa) <= DRAW_BALANCE:
                pred = 1
            else:
                pred = 0 if ph >= pa else 2
            preds_all.append(pred)
            y_all.append(true_outcome)

        ll = _log_loss(probs_all, y_all)
        acc = _accuracy(preds_all, y_all)
        avg_correct = float(np.mean([probs_all[i][y_all[i]] for i in range(len(y_all))]))

        results.append({
            "coef": coef,
            "log_loss": round(ll, 4),
            "accuracy": round(acc, 4),
            "avg_correct_prob": round(avg_correct, 4),
        })

    # Print results
    print(f"\n{'Coef':>6}  {'LogLoss':>8}  {'Accuracy':>9}  {'AvgCorrect':>11}")
    print("-" * 42)
    for r in results:
        print(f"{r['coef']:>6.2f}  {r['log_loss']:>8.4f}  "
              f"{r['accuracy']:>9.4f}  {r['avg_correct_prob']:>11.4f}")

    best = min(results, key=lambda r: r["log_loss"])
    print(f"\n→ Best CONDITION_COEF = {best['coef']} "
          f"(log_loss={best['log_loss']}, acc={best['accuracy']})")
    print(f"  Current value is 1.20. Original was 2.45.")

    PROC.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"results": results, "best": best}, indent=2))
    print(f"\nWritten to {OUT}")
    return best


if __name__ == "__main__":
    sweep()
