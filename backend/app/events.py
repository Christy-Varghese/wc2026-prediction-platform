"""Real match-event collector — goalscorers from the web (ESPN open API).

ESPN's public scoreboard JSON (no key, no bot-wall) carries real scorers with
minute + penalty/own-goal flags for every played WC2026 match. We fetch by date,
map ESPN team names to our canonical spelling, and cache to
`data/raw/match_events.json` keyed "Home|Away". `match_analytics` then serves
these real scorers (falling back to model-generated only when a match is missing).

Heat maps and passing networks are NOT here: that coordinate-level data lives
behind bot-protected/proprietary widgets (Sofascore returns a 403 challenge,
FotMob requires signed headers), so there is no open web source to scrape. Those
stay model-generated and are labeled as such in the UI.

Refresh:
    cd backend && ../.venv/bin/python -m app.events
"""
from __future__ import annotations

import json
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent.parent / "ml"
CACHE = ML_DIR.parent / "data" / "raw" / "match_events.json"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

# ESPN spelling -> our canonical (fixtures.REAL_GROUPS) spelling
NORMALIZE = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
}

# WC2026 group-stage dates (MD1 Jun 11-17, MD2/MD3 Jun 18-27). Only matches
# reported FULL_TIME by ESPN are cached, so future dates are simply no-ops
# until those games are played.
DATES = ["20260611", "20260612", "20260613", "20260614", "20260615",
         "20260616", "20260617", "20260618", "20260619", "20260620",
         "20260621", "20260622", "20260623", "20260624", "20260625",
         "20260626", "20260627"]


def _canon(name: str) -> str:
    return NORMALIZE.get(name, name)


def _minute(clock_val: str) -> int:
    """'67'' / '90'+3'' -> integer minute."""
    s = (clock_val or "").replace("'", "").strip()
    if "+" in s:
        a, b = s.split("+", 1)
        return int(a) + int(b)
    try:
        return int(float(s))
    except ValueError:
        return 0


def fetch(dates: list[str] | None = None) -> dict:
    """Scrape ESPN for the given dates; return {"home|away": {...}} cache dict."""
    import requests
    out: dict[str, dict] = {}
    for d in (dates or DATES):
        try:
            r = requests.get(ESPN, params={"dates": d}, timeout=20,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            events = r.json().get("events", [])
        except Exception as e:  # noqa: BLE001
            print(f"[events] {d}: fetch failed ({e})")
            continue
        for e in events:
            comp = e["competitions"][0]
            if comp["status"]["type"]["name"] != "STATUS_FULL_TIME":
                continue
            cmap = {c["id"]: c for c in comp["competitors"]}
            home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
            away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
            ht, at = _canon(home["team"]["displayName"]), _canon(away["team"]["displayName"])
            scorers = {"home": [], "away": []}
            for det in comp.get("details", []):
                if not det.get("scoringPlay"):
                    continue
                ath = (det.get("athletesInvolved") or [{}])[0]
                player = ath.get("displayName") or ath.get("shortName") or "Unknown"
                side = "home" if det.get("team", {}).get("id") == home["id"] else "away"
                kind = ("own goal" if det.get("ownGoal")
                        else "penalty" if det.get("penaltyKick") else "goal")
                scorers[side].append({"player": player,
                                      "minute": _minute(det.get("clock", {}).get("displayValue", "")),
                                      "type": kind})
            for s in scorers.values():
                s.sort(key=lambda x: x["minute"])
            out[f"{ht}|{at}"] = {
                "home": ht, "away": at,
                "score": [int(home["score"]), int(away["score"])],
                "scorers": scorers, "source": "ESPN", "date": d,
            }
    return out


def refresh() -> int:
    data = fetch()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"[events] wrote {len(data)} matches -> {CACHE}")
    return len(data)


def load() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def scorers_for(home: str, away: str) -> dict | None:
    """Real scorers for a fixture, or None if not in the cache."""
    return load().get(f"{home}|{away}")


if __name__ == "__main__":
    refresh()
