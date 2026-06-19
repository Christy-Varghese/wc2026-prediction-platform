"""Live validation script — run after backend is up on :8000."""
import json, urllib.request, sys

BASE = "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def q(s):
    return s.replace(" ", "%20")


# ── 1. Health ────────────────────────────────────────────────────────────────
h = get("/api/health")
print("=== HEALTH ===")
print(f"  ok={h['ok']}  members={h['members_loaded']}")

# ── 2. Fixture audit ──────────────────────────────────────────────────────────
matches = get("/api/matches?limit=200&predictions=false")
played = [m for m in matches if m.get("played")]
upcoming = [m for m in matches if not m.get("played")]
print("\n=== FIXTURES ===")
print(f"  Total={len(matches)}  Played={len(played)}  Upcoming={len(upcoming)}")
dates = sorted(m["kickoff"][:10] for m in matches)
print(f"  Date range: {dates[0]} to {dates[-1]}")
groups = {}
for m in matches:
    groups.setdefault(m["group"], 0)
    groups[m["group"]] += 1
ok_groups = all(v == 6 for v in groups.values())
print(f"  All groups have 6 fixtures: {ok_groups}")
pairs = [tuple(sorted((m["home_team"], m["away_team"]))) for m in matches]
print(f"  Duplicate fixtures: {len(pairs) - len(set(pairs))}")

# Verify today's matches are unplayed (Jun 19 kickoffs)
today = [m for m in matches if m["kickoff"].startswith("2026-06-19")]
print(f"  Jun-19 fixtures (should be unplayed): {len(today)}, "
      f"unplayed={sum(1 for m in today if not m.get('played'))}")

# ── 3. Prediction quality ──────────────────────────────────────────────────────
cards = get("/api/matches?limit=200&predictions=true")
bad = sum(1 for c in cards if abs(c["p_home"] + c["p_draw"] + c["p_away"] - 1) > 0.02)
market_used = sum(1 for c in cards if c.get("market_used"))
print("\n=== PREDICTION QUALITY ===")
print(f"  Bad probability rows: {bad}  (want 0)")
print(f"  Market odds used: {market_used}/{len(cards)} fixtures")

# ── 4. Key upcoming match predictions ────────────────────────────────────────
print("\n=== KEY UPCOMING PREDICTIONS ===")
key_pairs = [
    ("Argentina", "Austria"), ("France", "Iraq"),
    ("Spain", "Saudi Arabia"), ("England", "Ghana"),
    ("Brazil", "Haiti"), ("Germany", "Ivory Coast"),
    ("Norway", "Senegal"), ("Netherlands", "Sweden"),
]
for home, away in key_pairs:
    p = get(f"/api/predict?home={q(home)}&away={q(away)}&neutral=true")
    mkt = "mkt" if p.get("market_used") else "   "
    print(f"  [{mkt}] {home:<22} vs {away:<22}  "
          f"H={p['p_home']:.2f} D={p['p_draw']:.2f} A={p['p_away']:.2f}  "
          f"conf={p['confidence']}  xG={p['expected_goals']}")

# ── 5. Injury impact audit ────────────────────────────────────────────────────
print("\n=== INJURY / AVAILABILITY AUDIT ===")
teams_to_check = ["France", "England", "Brazil", "Argentina",
                  "Spain", "Germany", "Netherlands", "Morocco"]
for team in teams_to_check:
    td = get(f"/api/teams/{q(team)}")
    avail = td.get("availability", 1.0)
    squad = td.get("squad", [])
    injured = [p["name"] for p in squad if p.get("fitness") != "fit"]
    flag = " ⚠" if avail < 0.95 else ""
    print(f"  {team:<18} avail={avail:.3f}{flag}  out/doubt={injured or 'none'}")

# ── 6. Simulation results ──────────────────────────────────────────────────────
sim = get("/api/simulate")
print("\n=== TOURNAMENT SIM (TOP 12) ===")
if isinstance(sim, list):
    top = sorted(sim, key=lambda x: x.get("Champion", 0), reverse=True)[:12]
    total = sum(r.get("Champion", 0) for r in sim)
    print(f"  Teams in sim: {len(sim)}  Champion probs sum: {total:.4f}")
    for r in top:
        print(f"    {r['team']:<25} Champion={r.get('Champion',0)*100:.1f}%  "
              f"Final={r.get('Final',0)*100:.1f}%  SF={r.get('SF',0)*100:.1f}%")
elif isinstance(sim, dict):
    print("  /api/simulate returned dict:", list(sim.keys()))
else:
    print("  unexpected:", type(sim))

# ── 7. Insights ───────────────────────────────────────────────────────────────
ins = get("/api/insights")
print("\n=== INSIGHTS ===")
dh = ins.get("dark_horses", [])
ua = ins.get("upset_alerts", [])
print(f"  Dark horses: {len(dh)}")
for d in dh[:4]:
    print(f"    {d['team']:<20} elo_rank=#{d['elo_rank']}  sf_prob={d['semi_prob']:.1%}  title={d['title_prob']:.1%}")
print(f"  Upset alerts: {len(ua)}")
for u in ua[:4]:
    print(f"    {u['match']}  underdog={u['underdog']}  upsetP={u['underdog_win_prob']:.2f}")

print("\n=== ALL CHECKS DONE ===")
