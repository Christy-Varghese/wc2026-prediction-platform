"""XGBoost (and LightGBM-ready) 3-class match outcome classifier.

Trains on the engineered feature frame to predict P(Home / Draw / Away).
Falls back gracefully if xgboost is unavailable (returns None from load).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import PROC
from features import FEATURE_COLS, MODEL_FEATURE_COLS, build_training_frame

MODEL_PATH = PROC / "xgb_model.ubj"   # XGBoost native binary format
COLS_PATH  = PROC / "xgb_cols.json"


def train(df_elo: pd.DataFrame, since: str = "2006-01-01") -> Path:
    import xgboost as xgb  # local import so the package is optional

    feats = build_training_frame(df_elo)
    feats = feats[feats.date >= since]
    # Train on structural features only — avail_diff/squad_val_diff/market_home_edge
    # are always 0 in the training corpus (no historical data for them), so the model
    # cannot learn from them. They are applied post-blend as logit shifts instead.
    X = feats[MODEL_FEATURE_COLS].to_numpy()
    y = feats["y"].to_numpy()

    # time-ordered split: last 15% as validation
    cut = int(len(X) * 0.85)
    clf = xgb.XGBClassifier(
        objective="multi:softprob", num_class=3,
        n_estimators=400, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="mlogloss",
        early_stopping_rounds=30, n_jobs=4, tree_method="hist",
    )
    clf.fit(X[:cut], y[:cut], eval_set=[(X[cut:], y[cut:])], verbose=False)

    clf.save_model(str(MODEL_PATH))
    COLS_PATH.write_text(json.dumps(MODEL_FEATURE_COLS))
    return MODEL_PATH


def load():
    if not MODEL_PATH.exists():
        return None
    import xgboost as xgb
    clf = xgb.XGBClassifier()
    clf.load_model(str(MODEL_PATH))
    cols = json.loads(COLS_PATH.read_text()) if COLS_PATH.exists() else FEATURE_COLS
    return {"clf": clf, "cols": cols}


def predict_proba(bundle, x: np.ndarray) -> np.ndarray:
    """x: 1-D feature vector in FEATURE_COLS order -> [pH,pD,pA].

    Slices x down to the cols the model was actually trained on, so old models
    (trained on all 11 cols) and new models (trained on MODEL_FEATURE_COLS)
    both work correctly from the same 11-feature input vector.
    """
    cols = bundle.get("cols", MODEL_FEATURE_COLS)
    idxs = [FEATURE_COLS.index(c) for c in cols]
    p = bundle["clf"].predict_proba(x[idxs].reshape(1, -1))[0]
    return p / p.sum()


def main():
    df = pd.read_parquet(PROC / "results_elo.parquet")
    path = train(df)
    print(f"[xgb] trained -> {path}")


if __name__ == "__main__":
    main()
