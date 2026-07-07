"""Data-driven top news ticker.

Built from live state so it refreshes on every result ingest / re-sim — no hand
editing. Items: current matchday, latest results (with a standout scorer), the
Golden Boot leader, the model's projected champion, and outcome accuracy.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import fixtures, ml_engine, services

PROC = Path(__file__).resolve().parent.parent / "data" / "processed"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def _flag(team: str) -> str:
    code = fixtures.FLAG.get(team, "")
    if len(code) == 2 and code.isalpha():
        return "".join(chr(0x1F1E6 + ord(c) - 97) for c in code.lower())
    return "⚽"


def _match_events() -> dict:
    try:
        return json.loads((RAW / "match_events.json").read_text())
    except Exception:  # noqa: BLE001
        return {}


def _match_top_scorer(events: dict, home: str, away: str) -> str | None:
    rec = events.get(f"{home}|{away}") or events.get(f"{away}|{home}")
    if not rec:
        return None
    score = rec.get("score") or [0, 0]
    # Prefer the winning side's scorer (a draw falls back to either side).
    win_side = "home" if score[0] > score[1] else "away" if score[1] > score[0] else None

    def tally(sides) -> dict[str, int]:
        t: dict[str, int] = {}
        for side in sides:
            for sc in rec.get("scorers", {}).get(side, []):
                if sc.get("type") == "own goal":  # not the scorer's credit
                    continue
                nm = sc.get("player")
                if nm and nm != "Unknown":
                    t[nm] = t.get(nm, 0) + 1
        return t

    t = tally([win_side]) if win_side else {}
    if not t:  # draw, or winner scored only via own goal
        t = tally(["home", "away"])
    if not t:
        return None
    name, n = max(t.items(), key=lambda kv: kv[1])
    return f"{name} {'⚽' * min(n, 3)}" if n >= 2 else name


def build(max_results: int = 6) -> dict:
    sched = fixtures.schedule()
    played = sorted([m for m in sched if m["played"]],
                    key=lambda m: m["kickoff"], reverse=True)
    events = _match_events()
    items: list[str] = []

    # ── current matchday ──
    md = played[0]["matchday"] if played else "MD1"
    items.append(f"🏆 FIFA World Cup 2026 · {md} latest")

    # ── latest results (most recent first) ──
    for m in played[:max_results]:
        h, a = m["home_team"], m["away_team"]
        line = f"{_flag(h)} {h} {m['home_score']}-{m['away_score']} {a}"
        star = _match_top_scorer(events, h, a)
        if star:
            line += f" — {star}"
        items.append(line)

    # ── Golden Boot leader(s) ──
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ml"))
        import tournament_stats as ts
        goals = ts.player_goals()
        if goals:
            top_g = max(goals.values())
            leaders = [n for n, g in goals.items() if g == top_g]
            who = leaders[0] if len(leaders) == 1 else f"{len(leaders)}-way tie"
            items.append(f"👟 Golden Boot: {who} ({top_g} goals)")
    except Exception:  # noqa: BLE001
        pass

    # ── projected champion ──
    try:
        table = ml_engine.sim_table()
        if table:
            top = max(table, key=lambda r: r.get("Champion", 0))
            items.append(f"📊 CAI projects {_flag(top['team'])} {top['team']} "
                         f"champions ({top['Champion'] * 100:.1f}%)")
    except Exception:  # noqa: BLE001
        pass

    # ── outcome accuracy: group stage (points ladder — see services.prediction_points) ──
    try:
        pts = n = 0
        for m in played:
            # Pass `match=m` so this matches the prediction actually shown for
            # the fixture elsewhere (services.match_card does the same) — the
            # rest-days/travel/weather context inputs are only computed when
            # a match dict is supplied, so omitting it silently degrades to a
            # different (less-informed) prediction and disagrees with the
            # accuracy shown on /matches.
            p = services.predict(m["home_team"], m["away_team"], neutral=m["neutral"], match=m)
            pw = p.get("predicted_winner")
            if pw:
                n += 1
                top_scores = p.get("top_scores") or []
                pscore = top_scores[0]["score"] if top_scores else None
                pts += services.prediction_points(
                    pw, pscore, m["home_team"], m["away_team"],
                    m["home_score"], m["away_score"])
        # ── add knockout accuracy from bracket engine ──
        try:
            from .knockout_engine import resolve_bracket
            ko_data = resolve_bracket()
            ko_pts = ko_n = 0
            for km in ko_data.get("matches", []):
                if km.get("home_score") is None:
                    continue
                mpw = km.get("model_predicted_winner") or km.get("predicted_winner")
                if not mpw:
                    continue
                hs, aws = km["home_score"], km["away_score"]
                ph, pa = km.get("pen_home"), km.get("pen_away")
                if hs > aws:
                    actual = km["home_team"]
                elif aws > hs:
                    actual = km["away_team"]
                elif ph is not None and pa is not None:
                    actual = km["home_team"] if ph > pa else km["away_team"]
                else:
                    continue
                ko_n += 1
                ko_pts += services.prediction_points(
                    mpw, km.get("predicted_score"), km["home_team"], km["away_team"],
                    hs, aws, actual_winner=actual)
        except Exception:  # noqa: BLE001
            ko_pts = ko_n = 0

        total_pts = pts + ko_pts
        total_n = n + ko_n
        MAX_PTS = 5
        if total_n:
            max_total = total_n * MAX_PTS
            msg = (f"🎯 CAI accuracy: {total_pts}/{max_total} pts "
                   f"({round(total_pts / max_total * 100)}%)")
            if ko_n:
                rnd_label = "R32" if ko_n <= 16 else "KO"
                max_ko = ko_n * MAX_PTS
                msg += f" · {rnd_label}: {ko_pts}/{max_ko} pts ({round(ko_pts / max_ko * 100)}%)"
            items.append(msg)
    except Exception:  # noqa: BLE001
        pass

    items.append("🤖 CAI: current form + momentum led · 3-scenario knockout xG")
    return {"items": items, "n_played": len(played)}
