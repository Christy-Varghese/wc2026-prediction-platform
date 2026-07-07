"""Refit the ensemble calibrator using completed WC2026 matches.

The existing calibrator.json was fit on 192 pre-tournament backtest samples
and uses scalar temperature scaling. The reliability.json shows non-monotonic
bucket gaps (model says 65% → hits 59%; model says 55% → hits 64%) that scalar
temperature cannot fix. This script refits using vector_temperature, which
gives each outcome class (H/D/A) its own temperature.

Usage:
    cd backend/ml && python refit_calibrator.py

Writes updated calibrator.json and reliability.json to data/processed/.
Run AFTER each round so calibration stays current with tournament outcomes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml"))

from ensemble import Ensemble, MatchContext
import calibration as cal_mod
from tournament_form import WC2026_PLAYED

PROC = ROOT / "data" / "processed"

# All played WC2026 matches with true outcomes (0=home, 1=draw, 2=away) —
# ground-truth labels for calibration. Derived from tournament_form.
# WC2026_PLAYED (the single source of truth for played results, kept current
# on every ingest) rather than a hand-maintained list here: a hardcoded copy
# silently goes stale every time a new round lands (this one stopped at ~75
# games from Jun 30, missing the 19+ games played since). WC2026_PLAYED
# already stores the 90'/ET score for shootout-decided ties, not the penalty
# result, matching this script's "exclude penalty results" requirement for
# free.
WC2026_OUTCOMES = [
    (home, away, 0 if hs > as_ else 1 if hs == as_ else 2)
    for home, away, hs, as_, _neutral in WC2026_PLAYED
]


def collect_raw_blends(engine: Ensemble) -> tuple[np.ndarray, np.ndarray]:
    """Get pre-calibration blended probs and true outcome labels for all played matches."""
    P, y = [], []
    for home, away, outcome in WC2026_OUTCOMES:
        ctx = MatchContext()
        members_raw = engine._member_probs(home, away, neutral=True, ctx=ctx)
        members_raw.pop("_market_real", None)
        members = members_raw
        eff_w = dict(engine.weights)
        w = np.array([eff_w.get(k, 0.0) for k in members])
        w /= w.sum()
        stack = np.vstack([members[k] for k in members])
        blended = (w[:, None] * stack).sum(0)
        blended = blended / blended.sum()
        P.append(blended)
        y.append(outcome)
    return np.array(P), np.array(y)


def refit():
    print("Loading ensemble (this may take a moment)...")
    engine = Ensemble()

    print(f"Collecting pre-calibration predictions for {len(WC2026_OUTCOMES)} matches...")
    P, y = collect_raw_blends(engine)

    # Before: existing calibrator
    existing = engine.calibrator
    P_before = np.array([existing(row) for row in P])
    before_metrics = cal_mod.all_metrics(P_before, y)
    print(f"\nBefore refit: log_loss={before_metrics['log_loss']}, "
          f"ece={before_metrics['ece']}, acc={before_metrics['acc']}")
    print("Calibration buckets (before):")
    for b in cal_mod.confidence_buckets(P_before, y, bins=6):
        gap_flag = "  ← BAD" if abs(b["gap"]) > 0.06 else ""
        print(f"  {b['bucket']}: n={b['n']:3d}  conf={b['avg_conf']:.3f}  "
              f"hit={b['hit_rate']:.3f}  gap={b['gap']:+.3f}{gap_flag}")

    # Fit on all 72 games (full tournament calibration)
    # Split 70/30 for train/val to avoid overfitting
    cut = int(len(P) * 0.70)
    P_tr, y_tr = P[:cut], y[:cut]
    P_va, y_va = P[cut:], y[cut:]

    print("\nFitting vector-temperature calibrator...")
    new_cal = cal_mod.select_calibrator(P_tr, y_tr, P_va, y_va)
    print(f"Selected method: {new_cal['method']}")

    # After: new calibrator
    P_after = cal_mod.apply_calibrator(P, new_cal)
    after_metrics = cal_mod.all_metrics(P_after, y)
    print(f"\nAfter refit: log_loss={after_metrics['log_loss']}, "
          f"ece={after_metrics['ece']}, acc={after_metrics['acc']}")
    print("Calibration buckets (after):")
    for b in cal_mod.confidence_buckets(P_after, y, bins=6):
        gap_flag = "  ← BAD" if abs(b["gap"]) > 0.06 else ""
        print(f"  {b['bucket']}: n={b['n']:3d}  conf={b['avg_conf']:.3f}  "
              f"hit={b['hit_rate']:.3f}  gap={b['gap']:+.3f}{gap_flag}")

    # Only write if the new calibrator beats the existing one on val set
    before_val = cal_mod.log_loss(P_before[cut:], y_va)
    after_val  = cal_mod.log_loss(P_after[cut:], y_va)
    if after_val < before_val - 1e-4:
        cal_artifact = {
            **new_cal,
            "metadata": {
                "source": "wc2026_tournament_games",
                "n_train": int(cut),
                "n_val": int(len(P) - cut),
                "before_val_ll": round(before_val, 4),
                "after_val_ll": round(after_val, 4),
                "n_matches": len(WC2026_OUTCOMES),
            },
        }
        rel_artifact = {
            "ece": round(cal_mod.ece(P_after, y), 4),
            "brier": round(cal_mod.brier(P_after, y), 4),
            "confidence_bucket_stats": cal_mod.confidence_buckets(P_after, y),
            "n_samples": len(WC2026_OUTCOMES),
        }
        (PROC / "calibrator.json").write_text(json.dumps(cal_artifact, indent=2))
        (PROC / "reliability.json").write_text(json.dumps(rel_artifact, indent=2))
        print(f"\n✓ Calibrator updated (val log-loss {before_val:.4f} → {after_val:.4f})")
    else:
        print(f"\n✗ New calibrator did not improve val log-loss "
              f"({before_val:.4f} → {after_val:.4f}). Existing calibrator kept.")

    return after_metrics


if __name__ == "__main__":
    refit()
