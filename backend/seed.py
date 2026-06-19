"""Seed Postgres from the in-memory fixtures provider + ML artifacts.

Run once after `docker compose up db` (and set USE_DB=true) to populate teams,
players, matches, predictions and an admin user. Idempotent: clears + reloads.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import auth, fixtures, services
from app.db import Base, engine, get_session
from app.models import Match, Player, Prediction, Team, User


def seed():
    Base.metadata.drop_all(bind=engine())
    Base.metadata.create_all(bind=engine())
    db = next(get_session())

    name_to_id = {}
    for t in fixtures.teams():
        team = Team(code=t["code"], name=t["name"], confederation=t.get("confederation", ""),
                    flag_url=t["flag_url"], elo=t["elo"], fifa_rank=t["fifa_rank"],
                    manager=t["manager"], manager_winrate=t["manager_winrate"],
                    group=t["group"])
        db.add(team); db.flush()
        name_to_id[t["name"]] = team.id
        for p in fixtures.squad(t["name"]):
            db.add(Player(team_id=team.id, name=p["name"], position=p["position"],
                          club=p["club"], goals=p["goals"], assists=p["assists"],
                          xg=p["xg"], xa=p["xa"], impact=p["impact"],
                          fitness=p["fitness"]))

    for m in fixtures.schedule():
        match = Match(stage=m["stage"], group=m["group"], home_team=m["home_team"],
                      away_team=m["away_team"], venue=m["venue"], city=m["city"],
                      kickoff=datetime.fromisoformat(m["kickoff"].rstrip("Z")),
                      neutral=m["neutral"], weather=m["weather"])
        db.add(match); db.flush()
        try:
            p = services.predict(m["home_team"], m["away_team"], m["neutral"])
            db.add(Prediction(match_id=match.id, p_home=p["p_home"], p_draw=p["p_draw"],
                              p_away=p["p_away"], xg_home=p["expected_goals"]["home"],
                              xg_away=p["expected_goals"]["away"], confidence=p["confidence"],
                              upset_prob=p["upset_probability"], top_scores=p["top_scores"],
                              members=p["members"], explanation=p["explanation"]))
        except Exception as e:
            print(f"  ! prediction failed for {m['home_team']} v {m['away_team']}: {e}")

    db.add(User(username="admin", password_hash=auth.hash_password("admin")))
    db.commit()
    print(f"[seed] {len(name_to_id)} teams, {len(fixtures.schedule())} matches loaded")


if __name__ == "__main__":
    seed()
