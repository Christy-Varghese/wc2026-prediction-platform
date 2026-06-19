"""Download + clean international match results + player condition inputs.

Primary source (results):
  - martj42 international_results (1872-present)

Primary source (players):
  - Kaggle dataset: swaptr/fifa-wc-2026-players

Outputs:
  - data/processed/results_clean.parquet
  - data/processed/players_features.parquet
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from config import RESULTS_URL, RESULTS_CSV, PROC, RAW, PROJECTED_FIELD

PLAYERS_FEATURES = PROC / "players_features.parquet"
PLAYERS_RAW = RAW / "players_kaggle.csv"

TEAM_ALIAS = {
    "USA": "United States",
    "Congo DR": "DR Congo",
    "Korea Republic": "South Korea",
    "Korea, South": "South Korea",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Ivory Coast": "Ivory Coast",
    "Curacao": "Curaçao",
    "Cape Verde Islands": "Cape Verde",
}


def download_results(force: bool = False) -> pd.DataFrame:
    """Fetch results.csv, cache to data/raw."""
    if RESULTS_CSV.exists() and not force:
        print(f"[ingest] using cached {RESULTS_CSV}")
        return pd.read_csv(RESULTS_CSV, parse_dates=["date"])

    print(f"[ingest] downloading {RESULTS_URL}")
    r = requests.get(RESULTS_URL, timeout=60)
    r.raise_for_status()
    RESULTS_CSV.write_bytes(r.content)
    return pd.read_csv(RESULTS_CSV, parse_dates=["date"])


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize match-result columns, drop incomplete rows."""
    df = df.copy()
    df = df.dropna(subset=["home_score", "away_score"])
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    df["neutral"] = df["neutral"].astype(bool)
    df = df.sort_values("date").reset_index(drop=True)
    # outcome label for convenience
    df["result"] = "D"
    df.loc[df.home_score > df.away_score, "result"] = "H"
    df.loc[df.home_score < df.away_score, "result"] = "A"
    return df


def _download_kaggle_players_csv(force: bool = False) -> Path:
    """Download Kaggle players.csv via kagglehub and copy into data/raw.

    Respects env KAGGLE_PLAYERS_CSV when users want to point to a local file.
    """
    explicit = os.getenv("KAGGLE_PLAYERS_CSV", "").strip()
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"KAGGLE_PLAYERS_CSV not found: {p}")
        if p != PLAYERS_RAW:
            PLAYERS_RAW.write_bytes(p.read_bytes())
        return PLAYERS_RAW

    if PLAYERS_RAW.exists() and not force:
        print(f"[ingest] using cached {PLAYERS_RAW}")
        return PLAYERS_RAW

    try:
        import kagglehub
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "kagglehub not installed. Install it with `pip install kagglehub`."
        ) from e

    print("[ingest] downloading kaggle dataset swaptr/fifa-wc-2026-players")
    ds_dir = Path(kagglehub.dataset_download("swaptr/fifa-wc-2026-players"))
    src = ds_dir / "players.csv"
    if not src.exists():
        raise FileNotFoundError(f"players.csv not found in {ds_dir}")
    PLAYERS_RAW.write_bytes(src.read_bytes())
    print(f"[ingest] players csv cached at {PLAYERS_RAW}")
    return PLAYERS_RAW


def _norm_team(t: str) -> str:
    t = str(t or "").strip()
    return TEAM_ALIAS.get(t, t)


def clean_players(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Kaggle players file into model-ready player features.

    Output columns:
      player, team, position, club, age,
      goals_per90, assists_per90, shots_per90,
      form (0..10), fitness (0..1), impact (0.45..0.98), status
    """
    d = df.copy()
    d.columns = [c.strip() for c in d.columns]
    d["team"] = d["team_country"].map(_norm_team)
    d = d[d["team"].isin(PROJECTED_FIELD)].copy()

    # Safe numeric conversion
    num_cols = [
        "age", "minutes_90s", "minutes_pct", "goals_per90", "assists_per90",
        "goals_assists_per90", "shots_per90", "points_per_game", "plus_minus_per90",
        "cards_yellow", "cards_red", "games", "minutes"
    ]
    for c in num_cols:
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    # Default fill for missing stats
    for c, v in {
        "goals_per90": 0.0,
        "assists_per90": 0.0,
        "goals_assists_per90": 0.0,
        "shots_per90": 0.0,
        "minutes_90s": 0.0,
        "minutes_pct": 0.0,
        "points_per_game": 1.0,
        "plus_minus_per90": 0.0,
        "cards_yellow": 0.0,
        "cards_red": 0.0,
    }.items():
        if c not in d:
            d[c] = v
        d[c] = d[c].fillna(v)

    # Position map to the condition-engine vocabulary
    pos_map = {
        "GK": "GK", "DF": "CB", "MF": "CM", "FW": "FW",
    }
    d["position"] = d["position"].astype(str).str[:2].map(pos_map).fillna("CM")

    # Fitness proxy: minutes% and availability discipline (cards)
    fitness = 0.65 + 0.35 * (d["minutes_pct"].clip(0, 100) / 100.0)
    discipline_penalty = 0.02 * d["cards_red"].clip(0, 3) + 0.004 * d["cards_yellow"].clip(0, 10)
    d["fitness"] = (fitness - discipline_penalty).clip(0.35, 1.0)

    # Form score (0..10): combines goals/assists/shot generation + team results
    raw_form = (
        3.0 * d["goals_per90"] +
        2.2 * d["assists_per90"] +
        0.7 * d["shots_per90"] +
        0.8 * d["goals_assists_per90"] +
        0.6 * (d["points_per_game"] - 1.0) +
        0.3 * d["plus_minus_per90"]
    )
    lo, hi = np.nanpercentile(raw_form.to_numpy(), [5, 95])
    hi = hi if hi > lo else lo + 1e-6
    d["form"] = ((raw_form - lo) / (hi - lo) * 10.0).clip(0.0, 10.0)

    # Impact score (0.45..0.98): influence + usage + production
    minutes_factor = np.sqrt(d["minutes_90s"].clip(0, 45) / 45.0)
    output_factor = (d["goals_per90"] + d["assists_per90"]).clip(0, 1.2) / 1.2
    impact = 0.45 + 0.35 * minutes_factor + 0.20 * output_factor
    d["impact"] = impact.clip(0.45, 0.98)

    # injury status unknown in this dataset → default fit
    d["status"] = "fit"

    # Keep one row/player/team with highest minutes_90s
    d = d.sort_values(["player", "team", "minutes_90s"], ascending=[True, True, False])
    d = d.drop_duplicates(subset=["player", "team"], keep="first")

    out = d[[
        "player", "team", "position", "club", "age",
        "goals_per90", "assists_per90", "shots_per90",
        "form", "fitness", "impact", "status"
    ]].copy()

    return out.reset_index(drop=True)


def sync_players_dataset(force: bool = False) -> pd.DataFrame:
    """Download + normalize Kaggle players dataset into processed features."""
    csv_path = _download_kaggle_players_csv(force=force)
    raw = pd.read_csv(csv_path)
    players = clean_players(raw)
    players.to_parquet(PLAYERS_FEATURES)
    print(f"[ingest] {len(players):,} player rows -> {PLAYERS_FEATURES}")
    return players


def main() -> None:
    force = "--force" in sys.argv

    # 1) historical results
    df = clean(download_results(force=force))
    out = PROC / "results_clean.parquet"
    df.to_parquet(out)
    print(f"[ingest] {len(df):,} matches -> {out}")

    # 2) player dataset (optional but enabled by default)
    if "--skip-players" not in sys.argv:
        try:
            sync_players_dataset(force=force)
        except Exception as e:
            print(f"[ingest] player dataset skipped: {type(e).__name__}: {e}")

    print(df.tail(3).to_string())


if __name__ == "__main__":
    main()
