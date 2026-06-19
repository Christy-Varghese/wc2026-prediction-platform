"""PyTorch MLP match-outcome classifier (optional ensemble member).

Small feed-forward net over the same engineered features. Torch is imported
lazily so the rest of the stack runs without it; if torch is missing, train()
raises and load() returns None so the ensemble simply drops this member.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from config import PROC
from features import FEATURE_COLS, build_training_frame

MODEL_PATH = PROC / "nn_model.pt"
SCALER_PATH = PROC / "nn_scaler.pkl"


def _build_net(n_in: int):
    import torch.nn as nn
    return nn.Sequential(
        nn.Linear(n_in, 64), nn.ReLU(), nn.Dropout(0.3),
        nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(32, 3),
    )


def train(df_elo: pd.DataFrame, since: str = "2006-01-01", epochs: int = 40):
    import torch
    from torch import nn, optim

    feats = build_training_frame(df_elo)
    feats = feats[feats.date >= since]
    X = feats[FEATURE_COLS].to_numpy(dtype=np.float32)
    y = feats["y"].to_numpy()

    mean, std = X.mean(0), X.std(0) + 1e-6
    Xs = (X - mean) / std
    cut = int(len(Xs) * 0.85)
    Xt = torch.tensor(Xs[:cut]); yt = torch.tensor(y[:cut])

    net = _build_net(len(FEATURE_COLS))
    opt = optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss()
    net.train()
    for ep in range(epochs):
        opt.zero_grad()
        out = net(Xt)
        loss = lossf(out, yt)
        loss.backward(); opt.step()

    torch.save(net.state_dict(), MODEL_PATH)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump({"mean": mean, "std": std, "cols": FEATURE_COLS}, f)
    return MODEL_PATH


def load():
    if not (MODEL_PATH.exists() and SCALER_PATH.exists()):
        return None
    try:
        import torch
    except ImportError:
        return None
    net = _build_net(len(FEATURE_COLS))
    net.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
    net.eval()
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    return {"net": net, "scaler": scaler}


def predict_proba(bundle, x: np.ndarray) -> np.ndarray:
    import torch
    s = bundle["scaler"]
    xs = (x - s["mean"]) / s["std"]
    with torch.no_grad():
        logits = bundle["net"](torch.tensor(xs, dtype=torch.float32).reshape(1, -1))
        p = torch.softmax(logits, dim=1).numpy()[0]
    return p / p.sum()


def main():
    df = pd.read_parquet(PROC / "results_elo.parquet")
    print(f"[nn] trained -> {train(df)}")


if __name__ == "__main__":
    main()
