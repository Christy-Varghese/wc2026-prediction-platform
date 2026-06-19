"""Model-generated post-match analytics for COMPLETED matches.

IMPORTANT — this is illustrative, not real event data. WC2026 is a forward
simulation and the platform stores only scorelines, so there is no shot/pass/
position feed to draw from. Everything here (scorers, shot map, heat map,
passing network, box-score stats) is *generated* from the final score + squad
ratings + team Elo, seeded by the match id so a given match always renders the
same picture. The API and UI both label it "AI-generated".

Pitch coordinate convention (matches the frontend SVG):
    x in [0,100] = length, y in [0,64] = width.
    Home attacks toward x=100 (right goal); away attacks toward x=0 (left goal).
"""
from __future__ import annotations

import random
from typing import Any

from . import events, fixtures

# position weighting for who scores / shoots
_SCORE_W = {"FW": 1.0, "MF": 0.55, "DF": 0.18, "GK": 0.01}
# 4-3-3-ish slot template: (role, x_home_frac, y_frac). x mirrored for away.
_FORMATION = [
    ("GK", 0.06, 0.50),
    ("DF", 0.22, 0.18), ("DF", 0.22, 0.40), ("DF", 0.22, 0.60), ("DF", 0.22, 0.82),
    ("MF", 0.45, 0.28), ("MF", 0.45, 0.50), ("MF", 0.45, 0.72),
    ("FW", 0.70, 0.22), ("FW", 0.72, 0.50), ("FW", 0.70, 0.78),
]


def _lineup(team: str) -> list[dict]:
    """Build an 11-man starting lineup from the squad, slotted into a 4-3-3."""
    squad = fixtures.squad(team)
    by_pos: dict[str, list[dict]] = {"GK": [], "DF": [], "MF": [], "FW": []}
    for p in sorted(squad, key=lambda x: x["impact"], reverse=True):
        by_pos.get(p["position"], by_pos["MF"]).append(p)
    pool = list(squad)
    out = []
    for i, (role, _xf, _yf) in enumerate(_FORMATION):
        cand = by_pos.get(role) or []
        player = cand.pop(0) if cand else (pool[i] if i < len(pool) else
                 {"name": f"{team} #{i+1}", "position": role, "impact": 60})
        out.append({"name": player["name"], "position": role,
                    "impact": player.get("impact", 60)})
    return out


def _weighted_pick(rng: random.Random, lineup: list[dict]) -> dict:
    weights = [p["impact"] * _SCORE_W.get(p["position"], 0.3) for p in lineup]
    return rng.choices(lineup, weights=weights, k=1)[0]


def _minutes(rng: random.Random, n: int) -> list[int]:
    return sorted(rng.randint(3, 90) for _ in range(n))


def _scorers(rng, lineup, n_goals) -> list[dict]:
    out = []
    for minute in _minutes(rng, n_goals):
        p = _weighted_pick(rng, lineup)
        kind = "penalty" if rng.random() < 0.12 else "goal"
        out.append({"player": p["name"], "minute": minute, "type": kind})
    return out


def _real_scorers(home: str, away: str) -> dict | None:
    """Real scorers from the ESPN web cache, oriented to our home/away.

    Returns {"home": [...], "away": [...]} or None if the fixture isn't cached.
    Handles the case where ESPN stored the fixture with sides swapped.
    """
    rec = events.scorers_for(home, away)
    if rec:
        return rec["scorers"]
    rec = events.scorers_for(away, home)          # swapped orientation
    if rec:
        return {"home": rec["scorers"]["away"], "away": rec["scorers"]["home"]}
    return None


def _shots(rng, lineup, n_goals, n_shots, side) -> list[dict]:
    """Shot locations for one team. `side`='home' attacks right, 'away' left."""
    shots = []
    for k in range(max(n_shots, n_goals)):
        is_goal = k < n_goals
        # cluster near the attacked goal
        depth = rng.uniform(0.62, 0.97) if is_goal else rng.uniform(0.45, 0.96)
        x = depth * 100 if side == "home" else (1 - depth) * 100
        y = rng.uniform(8, 56)
        xg = round(rng.uniform(0.22, 0.78) if is_goal else rng.uniform(0.02, 0.30), 2)
        outcome = ("goal" if is_goal else
                   rng.choices(["on_target", "off_target", "blocked"],
                               weights=[3, 4, 2])[0])
        shots.append({"x": round(x, 1), "y": round(y, 1), "xg": xg,
                      "outcome": outcome, "player": _weighted_pick(rng, lineup)["name"]})
    return shots


def _heat_grid(rng, side, possession) -> list[list[float]]:
    """6 cols x 4 rows intensity 0..1, weighted toward the attacking third."""
    cols, rows = 6, 4
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            col_frac = c / (cols - 1)
            attack = col_frac if side == "home" else (1 - col_frac)
            base = 0.25 + 0.6 * attack * (possession / 55.0)
            centre = 1 - abs(r - (rows - 1) / 2) / ((rows - 1) / 2) * 0.4
            row.append(max(0.05, min(1.0, base * centre + rng.uniform(-0.08, 0.08))))
        grid.append(row)
    mx = max(max(r) for r in grid) or 1
    return [[round(v / mx, 2) for v in r] for r in grid]


def _network(rng, lineup, side) -> dict:
    """Passing network: nodes at formation slots, weighted edges between them."""
    nodes = []
    for (role, xf, yf), p in zip(_FORMATION, lineup):
        x = xf * 100 if side == "home" else (1 - xf) * 100
        nodes.append({"player": p["name"], "pos": role,
                      "x": round(x, 1), "y": round(yf * 64, 1), "passes": 0})
    # connect each player to 1-3 nearby players
    edges = []
    for i, a in enumerate(nodes):
        dists = sorted(
            [(j, (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2)
             for j, b in enumerate(nodes) if j != i], key=lambda t: t[1])
        for j, _ in dists[: rng.randint(1, 3)]:
            if any(e["from"] == j and e["to"] == i for e in edges):
                continue
            w = rng.randint(4, 22)
            edges.append({"from": i, "to": j, "weight": w})
            nodes[i]["passes"] += w
            nodes[j]["passes"] += w
    return {"nodes": nodes, "edges": edges}


def _box_score(rng, eh, ea, gh, ga) -> dict:
    poss_h = max(34, min(66, round(50 + (eh - ea) / 18 + rng.uniform(-4, 4))))
    sh_h = max(gh, round(7 + gh * 2 + poss_h / 12 + rng.uniform(-2, 3)))
    sh_a = max(ga, round(7 + ga * 2 + (100 - poss_h) / 12 + rng.uniform(-2, 3)))
    return {
        "possession": [poss_h, 100 - poss_h],
        "shots": [sh_h, sh_a],
        "shots_on_target": [max(gh, round(sh_h * rng.uniform(0.35, 0.55))),
                            max(ga, round(sh_a * rng.uniform(0.35, 0.55)))],
        "xg": [round(max(0.3, gh + rng.uniform(-0.6, 0.9)), 1),
               round(max(0.3, ga + rng.uniform(-0.6, 0.9)), 1)],
        "corners": [rng.randint(2, 9), rng.randint(2, 9)],
        "fouls": [rng.randint(6, 15), rng.randint(6, 15)],
        "yellow_cards": [rng.randint(0, 3), rng.randint(0, 3)],
    }


def analytics(match_id: int) -> dict | None:
    """Full generated post-match analytics, or None if the match isn't played."""
    m = fixtures.match_by_id(match_id)
    if not m or not m.get("played"):
        return None
    home, away = m["home_team"], m["away_team"]
    gh, ga = m["home_score"], m["away_score"]
    elo = fixtures._elo()
    eh, ea = elo.get(home, 1500.0), elo.get(away, 1500.0)

    rng = random.Random(match_id * 7919 + gh * 31 + ga)  # stable per match
    lh, la = _lineup(home), _lineup(away)
    box = _box_score(rng, eh, ea, gh, ga)

    # Goalscorers: prefer REAL data scraped from the web (ESPN), fall back to
    # model-generated when a fixture isn't in the cache.
    real = _real_scorers(home, away)
    if real is not None:
        scorers, scorers_source = real, "ESPN (web)"
    else:
        scorers = {"home": _scorers(rng, lh, gh), "away": _scorers(rng, la, ga)}
        scorers_source = "model-generated"

    return {
        "match_id": match_id, "home": home, "away": away,
        "score": [gh, ga], "generated": True,
        "scorers_source": scorers_source,
        "maps_source": "model-generated",
        "disclaimer": (
            "Goalscorers are real, collected from the web (ESPN). "
            if scorers_source.startswith("ESPN") else
            "Goalscorers are model-generated (fixture not yet in the web feed). "
        ) + "Shot map, heat map and passing network are model-generated "
            "illustrations — that coordinate-level data is not openly available "
            "(Sofascore/FotMob block automated access).",
        "scorers": scorers,
        "box_score": box,
        "shot_map": {
            "home": _shots(rng, lh, gh, box["shots"][0], "home"),
            "away": _shots(rng, la, ga, box["shots"][1], "away"),
        },
        "heat_map": {
            "home": _heat_grid(rng, "home", box["possession"][0]),
            "away": _heat_grid(rng, "away", box["possession"][1]),
        },
        "passing_network": {
            "home": _network(rng, lh, "home"),
            "away": _network(rng, la, "away"),
        },
    }
