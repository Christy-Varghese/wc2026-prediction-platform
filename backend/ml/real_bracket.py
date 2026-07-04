"""Resolve the REAL, partially-decided WC2026 knockout bracket.

The group stage is 100% finished, so the 32 R32 qualifiers and their bracket
pairing are real, fixed facts — not something to re-simulate. This module
computes that fixed structure ONCE (`resolve_r32`), reads the fixed
R32->R16->QF->SF->Final tree from `app/knockout.json`, and lets `simulate.py`
walk it per Monte-Carlo trial (`walk_bracket_once`), treating already-played
ties as certain and only randomizing ties that haven't happened yet.

Pure Python, no FastAPI import: `app/knockout_engine.py` already does this
kind of bracket resolution, but importing the `app` package from here risks
a circular import back into `ml/` (via `app.services`/`app.ml_engine`) and
would stop `ml/` scripts from running standalone. Instead we read
`app/knockout.json` directly as data, and port the (pure, FastAPI-free)
third-place qualification logic from `knockout_engine.py` verbatim — the
same trade-off `tournament_form.WC2026_PLAYED` already makes by duplicating
`app/fixtures.py`'s real results instead of importing them.
"""
from __future__ import annotations

import re
from pathlib import Path

import config
import knockout_resolve
from tournament_form import WC2026_PLAYED

GROUP_LETTERS = "ABCDEFGHIJKL"
KNOCKOUT_JSON = Path(__file__).resolve().parent.parent / "app" / "knockout.json"

# Bracket rounds that actually feed the output stage columns, in resolution
# order (so "Winner/Loser Match N" back-references always resolve before
# they're needed). The third-place playoff is excluded: no output column
# depends on it, exactly like the old simulator never modeled it either.
_ROUND_ORDER = {"r32": 0, "r16": 1, "qf": 2, "sf": 3, "final": 4}
NEXT_STAGE = {"r32": "R16", "r16": "QF", "qf": "SF", "sf": "Final", "final": "Champion"}


def load_bracket_rows() -> list[dict]:
    """The 32-team knockout bracket tree, straight from the source JSON."""
    import json
    return json.loads(KNOCKOUT_JSON.read_text())


def final_group_tables() -> dict[str, list[dict]]:
    """Real final group standings: {letter: [{team, group, pts, gd}, ...]}.

    Computed from WC2026_PLAYED (now the group stage is 100% complete, this
    is real history, not a projection). Sort key is (pts, gd) ONLY — matching
    app/knockout_engine.py::project_group_standings(), the function that
    actually produced the labels/actual_home/actual_away values baked into
    knockout.json. app/fixtures.py::group_tables() uses a 3-key (pts,gd,gf)
    tiebreak instead — don't use that rule here, it can silently disagree.
    """
    group_of: dict[str, str] = {}
    for i, teams in enumerate(config.REAL_GROUPS_2026):
        for t in teams:
            group_of[t] = GROUP_LETTERS[i]

    stats = {t: {"team": t, "group": g, "pts": 0, "gd": 0}
             for t, g in group_of.items()}
    played = {g: 0 for g in GROUP_LETTERS[:len(config.REAL_GROUPS_2026)]}

    for home, away, hs, as_, _neutral in WC2026_PLAYED:
        gh, ga = group_of.get(home), group_of.get(away)
        if gh is None or ga is None or gh != ga:
            continue  # cross-group (knockout) tie, not a group-stage game
        gd = hs - as_
        stats[home]["gd"] += gd
        stats[away]["gd"] -= gd
        stats[home]["pts"] += 3 if hs > as_ else (1 if hs == as_ else 0)
        stats[away]["pts"] += 3 if as_ > hs else (1 if hs == as_ else 0)
        played[gh] += 1

    # Guard rail: today every knockout tie is provably cross-group (R32 pairs
    # are always "Winner X"/"Runner-up Y"/"3rd of {group set excluding X,Y}"),
    # but once future R16+ results get appended to WC2026_PLAYED a genuine
    # same-group rematch is structurally possible — fail loudly rather than
    # silently corrupt a group's tally if that filter ever over-includes.
    bad = {g: n for g, n in played.items() if n != 6}
    if bad:
        raise ValueError(f"expected 6 group games per group, got {bad}")

    tables: dict[str, list[dict]] = {}
    for i, teams in enumerate(config.REAL_GROUPS_2026):
        letter = GROUP_LETTERS[i]
        rows = sorted((stats[t] for t in teams),
                      key=lambda s: (s["pts"], s["gd"]), reverse=True)
        tables[letter] = rows
    return tables


# ── ported verbatim from app/knockout_engine.py (pure, no FastAPI deps) ────
def best_eight_thirds(tables: dict[str, list[dict]]) -> list[dict]:
    thirds = [tbl[2] for tbl in tables.values()]
    thirds.sort(key=lambda s: (s["pts"], s["gd"]), reverse=True)
    return thirds[:8]


def _allowed_groups(label: str) -> set[str]:
    m = re.search(r"3rd Group ([A-L/]+)", label)
    return set(m.group(1).split("/")) if m else set()


def assign_third_slots(third_slots: list[dict],
                       qualifying: list[dict]) -> dict[int, dict]:
    by_group = {t["group"]: t for t in qualifying}
    qual_groups = set(by_group)

    slots = sorted(third_slots,
                   key=lambda s: len(_allowed_groups(s["away_label"]) & qual_groups))
    assignment: dict[int, str] = {}
    used: set[str] = set()

    def backtrack(i: int) -> bool:
        if i == len(slots):
            return True
        slot = slots[i]
        options = sorted((_allowed_groups(slot["away_label"]) & qual_groups) - used)
        for grp in options:
            assignment[slot["id"]] = grp
            used.add(grp)
            if backtrack(i + 1):
                return True
            used.discard(grp)
            del assignment[slot["id"]]
        return False

    if backtrack(0):
        return {sid: by_group[g] for sid, g in assignment.items()}

    result: dict[int, dict] = {}
    pool = list(qualifying)
    for slot in slots:
        allowed = _allowed_groups(slot["away_label"])
        pick = next((t for t in pool if t["group"] in allowed), None)
        if pick:
            result[slot["id"]] = pick
            pool.remove(pick)
    return result
# ── end ported section ──────────────────────────────────────────────────────


def resolve_r32(rows: list[dict] | None = None) -> tuple[dict[int, tuple[str, str]], list[str]]:
    """The real, fixed 32-team R32 field + bracket pairing.

    Returns ({r32_id: (home_team, away_team)}, [32 team names]).
    """
    rows = rows if rows is not None else load_bracket_rows()
    tables = final_group_tables()
    winners = {g: rows_[0]["team"] for g, rows_ in tables.items()}
    runners = {g: rows_[1]["team"] for g, rows_ in tables.items()}

    r32_rows = [r for r in rows if r["type"] == "r32"]
    third_slots = [r for r in r32_rows if r["away_label"].startswith("3rd Group")]
    qualifying = best_eight_thirds(tables)
    third_by_slot = assign_third_slots(third_slots, qualifying)

    def resolve_label(label: str, slot_id: int) -> str:
        if label.startswith("Winner Group "):
            return winners[label.split()[-1]]
        if label.startswith("Runner-up Group "):
            return runners[label.split()[-1]]
        if label.startswith("3rd Group "):
            return third_by_slot[slot_id]["team"]
        raise ValueError(f"unexpected R32 label: {label!r}")

    pairs: dict[int, tuple[str, str]] = {}
    field: list[str] = []
    for r in r32_rows:
        home = r.get("actual_home") or resolve_label(r["home_label"], r["id"])
        away = r.get("actual_away") or resolve_label(r["away_label"], r["id"])
        # Free self-check, but only for "Winner/Runner-up Group" labels: those
        # have exactly one correct answer from final_group_tables(), so any
        # disagreement with a recorded actual_home/actual_away means the
        # tiebreak/standings logic above is wrong. "3rd Group ..." slots are
        # NOT checked this way: assign_third_slots() is a heuristic fallback
        # for when the real slot isn't known yet, and FIFA's real third-place
        # draw procedure doesn't always match our backtracking's arbitrary
        # pick among several valid matchings — the recorded actual_away is
        # simply trusted directly once it exists (as `resolve_label` above
        # already never runs for it).
        if not r["home_label"].startswith("3rd Group") and r.get("actual_home") and \
                r["actual_home"] != resolve_label(r["home_label"], r["id"]):
            raise ValueError(f"R32 id {r['id']}: computed home != actual_home")
        if not r["away_label"].startswith("3rd Group") and r.get("actual_away") and \
                r["actual_away"] != resolve_label(r["away_label"], r["id"]):
            raise ValueError(f"R32 id {r['id']}: computed away != actual_away")
        pairs[r["id"]] = (home, away)
        field += [home, away]
    return pairs, field


def _actual_winner_loser(row: dict, home: str, away: str) -> tuple[str, str] | None:
    hs, as_ = row.get("home_score"), row.get("away_score")
    if hs is None:
        return None
    if hs != as_:
        return (home, away) if hs > as_ else (away, home)
    ph, pa = row.get("pen_home"), row.get("pen_away")
    return (home, away) if (ph or 0) > (pa or 0) else (away, home)


def _resolve_ref(label: str, results: dict[int, tuple[str, str]]) -> str | None:
    m = re.match(r"(Winner|Loser) Match (\d+)", label)
    if not m:
        return None
    ref = results.get(int(m.group(2)))
    if not ref:
        return None
    winner, loser = ref
    return winner if m.group(1) == "Winner" else loser


def walk_bracket_once(rng, ko_params: dict, r32_pairs: dict[int, tuple[str, str]],
                      rows_by_id: dict[int, dict]) -> dict[str, str]:
    """One walk of the REAL bracket. Returns {team: furthest_stage_reached}.

    Already-decided ties resolve to their real winner every time (no RNG
    consumed); undecided ties are resolved via knockout_resolve.resolve_ko.
    """
    stage = {t: "R32" for pair in r32_pairs.values() for t in pair}
    results: dict[int, tuple[str, str]] = {}  # id -> (winner, loser)

    ordered = sorted((r for r in rows_by_id.values() if r["type"] in _ROUND_ORDER),
                     key=lambda r: (_ROUND_ORDER[r["type"]], r["id"]))
    for row in ordered:
        rtype, rid = row["type"], row["id"]
        if rtype == "r32":
            home, away = r32_pairs[rid]
        else:
            home = _resolve_ref(row["home_label"], results)
            away = _resolve_ref(row["away_label"], results)
            if home is None or away is None:
                continue  # shouldn't happen with a fully-specified bracket

        actual = _actual_winner_loser(row, home, away)
        if actual is not None:
            winner, loser = actual
        else:
            winner = knockout_resolve.resolve_ko(ko_params, rng, home, away)
            loser = away if winner == home else home

        results[rid] = (winner, loser)
        nxt = NEXT_STAGE.get(rtype)
        if nxt:
            stage[winner] = nxt
    return stage
