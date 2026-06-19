"""Write a SAMPLE live-injuries cache for demo/offline use.

Real data: set INJURY_API_KEY (api-sports.io) and call
ml/injuries.fetch_api_football() or POST /api/admin/refresh-injuries.

Players here match the curated squads in app/fixtures.py so availability and
`avail_diff` visibly move. Run:  python backend/seed_injuries.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND / "ml"))
from config import RAW  # noqa: E402

ROWS = [
    # team, player, kind, status, detail, return_date
    ("France", "Ousmane Dembélé", "injury", "out", "Hamstring strain", "2026-06-25"),
    ("France", "Aurélien Tchouaméni", "injury", "doubt", "Ankle knock", "2026-06-20"),
    ("Spain", "Rodri", "injury", "out", "Knee (ACL recovery)", "2026-07-01"),
    ("England", "John Stones", "injury", "out", "Calf strain", "2026-06-22"),
    ("Brazil", "Vinícius Júnior", "injury", "doubt", "Thigh tightness", "2026-06-19"),
    ("Argentina", "Cristian Romero", "suspension", "out", "Yellow-card accumulation", "2026-06-21"),
    ("Portugal", "Rúben Dias", "injury", "doubt", "Groin", "2026-06-20"),
]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / "injuries.csv"
    df = pd.DataFrame(ROWS, columns=["team", "player", "kind", "status",
                                     "detail", "return_date"])
    df.to_csv(out, index=False)
    print(f"[seed_injuries] {len(df)} rows -> {out}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
