"""Tournament-level insights: dark horses and upset alerts.

Dark horse = team whose simulated deep-run probability far exceeds what its
raw Elo ranking would suggest (low seed, high ceiling). Upset alert = an
upcoming match where the Elo underdog has a meaningful win probability.
"""
from __future__ import annotations

import pandas as pd

from config import PROC


def _elo_rank() -> dict[str, int]:
    p = PROC / "elo_ratings.parquet"
    if not p.exists():
        return {}
    s = pd.read_parquet(p)["elo"].sort_values(ascending=False)
    return {t: i + 1 for i, t in enumerate(s.index)}


def dark_horses(top_n: int = 6) -> list[dict]:
    """Teams seeded outside the elite but with strong sim deep-run odds."""
    sp = PROC / "sim_results.parquet"
    if not sp.exists():
        return []
    sim = pd.read_parquet(sp)
    rank = _elo_rank()
    sim = sim.copy()
    sim["elo_rank"] = sim["team"].map(rank).fillna(99).astype(int)
    sim["sim_rank"] = sim["SF"].rank(ascending=False, method="min").astype(int)
    # overperformance: reaches semis more than seed implies, but not a top-8 seed
    sim["overperf"] = sim["elo_rank"] - sim["sim_rank"]
    cand = sim[(sim["elo_rank"] > 8) & (sim["SF"] > 0.10)]
    cand = cand.sort_values(["overperf", "SF"], ascending=False).head(top_n)
    return [{
        "team": r.team, "elo_rank": int(r.elo_rank),
        "semi_prob": round(float(r.SF), 3), "title_prob": round(float(r.Champion), 3),
        "note": f"Seeded #{int(r.elo_rank)} but reaches the semis in "
                f"{r.SF*100:.0f}% of simulations — a live dark horse.",
    } for r in cand.itertuples(index=False)]


def upset_alerts(fixtures: list[dict], engine, threshold: float = 0.33) -> list[dict]:
    """fixtures: [{home, away, neutral}]. Flags underdog danger games."""
    rank = _elo_rank()
    alerts = []
    for fx in fixtures:
        h, a = fx["home"], fx["away"]
        pred = engine.predict(h, a, fx.get("neutral", True))
        rh, ra = rank.get(h, 99), rank.get(a, 99)
        if rh <= ra:
            fav, dog, dog_p = h, a, pred["p_away"]
        else:
            fav, dog, dog_p = a, h, pred["p_home"]
        if dog_p >= threshold:
            alerts.append({
                "match": f"{h} vs {a}", "favorite": fav, "underdog": dog,
                "underdog_win_prob": round(dog_p, 3),
                "draw_prob": pred["p_draw"],
                "note": f"{dog} (underdog) wins {dog_p*100:.0f}% of the time — "
                        f"upset watch.",
            })
    return sorted(alerts, key=lambda x: x["underdog_win_prob"], reverse=True)
