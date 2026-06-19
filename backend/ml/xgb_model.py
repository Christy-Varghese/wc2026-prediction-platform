"""XGBoost (and LightGBM-ready) 3-class match outcome classifier.

Trains on the engineered feature frame to predict P(Home / Draw / Away).
Falls back gracefully if xgboost is unavailable (returns None from load).
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from config import PROC
from features import FEATURE_COLS, build_training_frame

MODEL_PATH = PROC / "xgb_model.pkl"


def train(df_elo: pd.DataFrame, since: str = "2006-01-01") -> Path:
    import xgboost as xgb  # local import so the package is optional

    feats = build_training_frame(df_elo)
    feats = feats[feats.date >= since]
    X = feats[FEATURE_COLS].to_numpy()
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

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"clf": clf, "cols": FEATURE_COLS}, f)
    return MODEL_PATH


def load():
    if not MODEL_PATH.exists():
        return None
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict_proba(bundle, x: np.ndarray) -> np.ndarray:
    """x: 1-D feature vector in FEATURE_COLS order -> [pH,pD,pA]."""
    p = bundle["clf"].predict_proba(x.reshape(1, -1))[0]
    return p / p.sum()


def main():
    df = pd.read_parquet(PROC / "results_elo.parquet")
    path = train(df)
    print(f"[xgb] trained -> {path}")


if __name__ == "__main__":
    main()
