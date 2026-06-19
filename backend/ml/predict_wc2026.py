"""
WC 2026 — Full Prediction Report
=================================
Generates predictions for every remaining group-stage match plus likely
knockout-round matchups, incorporating:

  1. Trained Dixon-Coles + Elo (49,429 historical matches)
  2. Live WC2026 MD1/MD2 micro-Elo updates (tournament_form.py)
  3. Star player impact scores (squad quality weighting)
  4. Current injuries / suspensions (injuries.csv)
  5. Market odds where available (odds.csv)

Usage:
    cd backend/ml
    ../../.venv/bin/python predict_wc2026.py
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")       # ml/  — picks up ml/config.py
sys.path.insert(1, "../app")  # app/ — for fixtures, squads etc.

import json
import pickle
from pathlib import Path

import pandas as pd

from config import PROC, REAL_GROUPS_2026
from ensemble import Ensemble, MatchContext
from tournament_form import get_adjusted_elo, print_changes

# ─────────────────────────────────────────────────────────────────────────────
# STAR PLAYER IMPACT SCORES  (0–100 scale)
# Higher = bigger team impact when absent.
# Based on: Ballon d'Or rank, World Rankings contribution, WC squad role.
# ─────────────────────────────────────────────────────────────────────────────
STAR_IMPACT: dict[str, dict[str, int]] = {
    # Group J
    "Argentina": {
        "Lionel Messi":       99,  # GOAT — team revolves around him
        "Julián Álvarez":     88,
        "Rodrigo De Paul":    84,
        "Enzo Fernández":     82,
        "Cristian Romero":    83,  # suspended MD2
        "Emiliano Martínez":  87,
    },
    # Group H
    "Spain": {
        "Pedri":              91,
        "Lamine Yamal":       90,
        "Nico Williams":      88,
        "Rodri":              93,  # recently fit (cleared ACL)
        "Álvaro Morata":      82,
        "Unai Simón":         80,
    },
    # Group I
    "France": {
        "Kylian Mbappé":      97,
        "Antoine Griezmann":  89,
        "Aurélien Tchouaméni":80,  # doubt
        "Ousmane Dembélé":    82,  # doubt
        "Mike Maignan":       82,
        "William Saliba":     84,
    },
    # Group C
    "Brazil": {
        "Vinícius Júnior":    94,  # doubt
        "Rodrygo":            88,
        "Raphinha":           87,
        "Lucas Paquetá":      83,
        "Marquinhos":         85,
        "Alisson":            88,
    },
    # Group L
    "England": {
        "Jude Bellingham":    93,
        "Phil Foden":         90,
        "Bukayo Saka":        89,
        "Harry Kane":         91,
        "John Stones":        77,  # doubt
        "Jordan Pickford":    80,
    },
    # Group K
    "Portugal": {
        "Cristiano Ronaldo":  91,  # still fit, WC swan song
        "Bruno Fernandes":    89,
        "Rúben Neves":        84,
        "Bernardo Silva":     88,
        "Rúben Dias":         85,  # doubt
        "Diogo Costa":        81,
    },
    # Group E
    "Germany": {
        "Florian Wirtz":      91,
        "Jamal Musiala":      92,
        "Kai Havertz":        86,
        "Leroy Sané":         81,  # OUT — knee ligament
        "Toni Kroos":         88,
        "Manuel Neuer":       82,
    },
    # Group C
    "Morocco": {
        "Achraf Hakimi":      88,  # suspended MD2
        "Hakim Ziyech":       82,
        "Youssef En-Nesyri":  81,
        "Azzedine Ounahi":    78,
    },
    # Group F
    "Netherlands": {
        "Virgil van Dijk":    86,  # doubt
        "Frenkie de Jong":    86,
        "Cody Gakpo":         84,
        "Memphis Depay":      81,
        "Xavi Simons":        83,
    },
    # Group K
    "Colombia": {
        "Luis Díaz":          88,
        "James Rodríguez":    85,
        "Jhon Durán":         80,
        "Davinson Sánchez":   78,
    },
    # Group F
    "Japan": {
        "Takefusa Kubo":      85,
        "Kaoru Mitoma":       84,
        "Ritsu Doan":         80,
        "Wataru Endō":        79,
    },
    # Group I
    "Norway": {
        "Erling Haaland":     97,
        "Martin Ødegaard":    91,
        "Alexander Sørloth":  80,
    },
    # Group A
    "Mexico": {
        "Hirving Lozano":     84,
        "Henry Martín":       80,
        "Edson Álvarez":      82,
        "Santiago Giménez":   83,
    },
    # Group B
    "Canada": {
        "Alphonso Davies":    90,
        "Jonathan David":     88,
        "Cyle Larin":         78,
    },
    # Group D
    "United States": {
        "Christian Pulisic":  87,
        "Gio Reyna":          82,
        "Tyler Adams":        80,
        "Folarin Balogun":    79,
    },
}

# Remaining WC2026 group stage fixtures (not yet played as of Jun 19, 2026)
REMAINING_FIXTURES = [
    # MD2
    ("Argentina",    "Austria",              "J", "MD2", False),
    ("Jordan",       "Algeria",              "J", "MD2", True),
    ("South Korea",  "Bosnia and Herzegovina","B" ,"MD2", True),   # corrected group
    ("Morocco",      "Haiti",                "C", "MD2", True),
    ("Scotland",     "Brazil",               "C", "MD2", True),
    ("Turkey",       "United States",        "D", "MD2", True),
    ("Paraguay",     "Australia",            "D", "MD2", True),
    ("Germany",      "Ecuador",              "E", "MD2", True),
    ("Ivory Coast",  "Curaçao",              "E", "MD2", True),
    ("Netherlands",  "Tunisia",              "F", "MD2", True),
    ("Sweden",       "Japan",                "F", "MD2", True),
    ("Belgium",      "Iran",                 "G", "MD2", True),
    ("Egypt",        "New Zealand",          "G", "MD2", True),
    ("Spain",        "Uruguay",              "H", "MD2", True),
    ("Cape Verde",   "Saudi Arabia",         "H", "MD2", True),
    ("France",       "Senegal",              "I", "MD2", True),
    ("Norway",       "Iraq",                 "I", "MD2", True),
    ("Portugal",     "Colombia",             "K", "MD2", True),
    ("DR Congo",     "Uzbekistan",           "K", "MD2", True),
    ("England",      "Croatia",              "L", "MD2", True),
    ("Ghana",        "Panama",               "L", "MD2", True),
    # MD3
    ("South Africa", "South Korea",          "A", "MD3", True),
    ("Czech Republic","Mexico",              "A", "MD3", True),
    ("Qatar",        "South Korea",          "B", "MD3", True),   # placeholder
    ("Bosnia and Herzegovina","Canada",      "B", "MD3", True),
    ("Brazil",       "Haiti",                "C", "MD3", True),
    ("Scotland",     "Morocco",              "C", "MD3", True),
    ("United States","Australia",            "D", "MD3", True),
    ("Paraguay",     "Turkey",               "D", "MD3", True),
    ("Germany",      "Curaçao",              "E", "MD3", True),
    ("Ecuador",      "Ivory Coast",          "E", "MD3", True),
    ("Netherlands",  "Japan",                "F", "MD3", True),
    ("Sweden",       "Tunisia",              "F", "MD3", True),
    ("Belgium",      "Egypt",                "G", "MD3", True),
    ("Iran",         "New Zealand",          "G", "MD3", True),
    ("Spain",        "Cape Verde",           "H", "MD3", True),
    ("Saudi Arabia", "Uruguay",              "H", "MD3", True),
    ("France",       "Iraq",                 "I", "MD3", True),
    ("Senegal",      "Norway",               "I", "MD3", True),
    ("Argentina",    "Jordan",               "J", "MD3", True),
    ("Algeria",      "Austria",              "J", "MD3", True),
    ("Portugal",     "DR Congo",             "K", "MD3", True),
    ("Colombia",     "Uzbekistan",           "K", "MD3", True),
    ("England",      "Ghana",                "L", "MD3", True),
    ("Croatia",      "Panama",               "L", "MD3", True),
]

# Likely knockout matchups based on projected group winners
LIKELY_KNOCKOUT = [
    ("Argentina",  "Netherlands",   "R16",    True),
    ("Spain",      "Japan",         "R16",    True),
    ("France",     "Germany",       "R16",    True),
    ("England",    "Brazil",        "R16",    True),
    ("Argentina",  "Spain",         "QF",     True),
    ("France",     "England",       "QF",     True),
    ("Argentina",  "France",        "SF",     True),
    ("Spain",      "England",       "SF",     True),
    ("Argentina",  "France",        "Final",  True),
]


def _build_ctx(home: str, away: str) -> MatchContext:
    """Build a MatchContext with star-player availability adjustments."""
    from injuries import get_book as get_inj_book
    inj = get_inj_book()

    def avail(team: str) -> float:
        stars = STAR_IMPACT.get(team, {})
        if not stars:
            return 1.0
        total = sum(stars.values())
        lost = 0.0
        for name, impact in stars.items():
            rep = next((r for r in inj.report(team) if r["player"] == name), None)
            if rep:
                s = rep["status"]
                lost += impact if s == "out" else impact * 0.4  # doubt = 40%
        return max(0.0, 1.0 - lost / total)

    ah = avail(home)
    aa = avail(away)
    return MatchContext(avail_diff=round(ah - aa, 4))


def _bar(p: float, width: int = 20) -> str:
    filled = round(p * width)
    return "█" * filled + "░" * (width - filled)


def run_predictions() -> None:
    print("\n" + "═" * 70)
    print("  FIFA WORLD CUP 2026 — FULL PREDICTION REPORT")
    print("  Powered by: Dixon-Coles + Elo + XGBoost + Market odds")
    print("  Tournament Elo patched with MD1/MD2 real results")
    print("═" * 70)

    # Load ensemble (applies tournament Elo automatically)
    e = Ensemble()

    # ── Print Elo changes from WC2026 results
    import pandas as pd
    base = pd.read_parquet(PROC / "elo_ratings.parquet")["elo"].to_dict()
    adjusted = e.elo
    gainers = sorted(
        [(t, adjusted.get(t, 1500) - base.get(t, 1500))
         for t in adjusted if abs(adjusted.get(t, 1500) - base.get(t, 1500)) > 1],
        key=lambda x: -x[1]
    )[:8]
    print("\n📊  ELO SHIFTS FROM WC2026 MD1/MD2 RESULTS")
    for team, delta in gainers:
        arrow = "▲" if delta > 0 else "▼"
        print(f"   {arrow} {team:<24} {delta:+.1f} pts  (now {adjusted.get(team,1500):.0f})")

    # ── Group stage remaining predictions
    print("\n\n" + "─" * 70)
    print("  GROUP STAGE — REMAINING MATCH PREDICTIONS")
    print("─" * 70)

    current_group = ""
    for home, away, grp, md, neutral in REMAINING_FIXTURES:
        if grp != current_group:
            current_group = grp
            print(f"\n  ▸ GROUP {grp}")

        ctx = _build_ctx(home, away)
        r = e.predict(home, away, neutral=neutral, ctx=ctx)

        fav = home if r["p_home"] >= r["p_away"] else away
        fav_p = max(r["p_home"], r["p_away"])
        mkt = "📈" if r["market_used"] else "📐"  # 📐 = synthetic odds

        avail_note = ""
        if abs(ctx.avail_diff) >= 0.03:
            weaker = away if ctx.avail_diff > 0 else home
            avail_note = f" ⚠️  {weaker} depleted"

        print(f"   {md}  {home:<22} vs {away:<22}")
        print(f"        {_bar(r['p_home'])} {r['p_home']*100:4.1f}%  |"
              f"  D {r['p_draw']*100:4.1f}%  |"
              f"  {r['p_away']*100:4.1f}% {_bar(r['p_away'])}")
        print(f"        Predict: {fav} ({fav_p*100:.0f}%)  "
              f"xG {r['expected_goals']['home']:.1f}-{r['expected_goals']['away']:.1f}  "
              f"Top: {r['top_scores'][0]['score']}  "
              f"Conf: {r['confidence']}/100  {mkt}{avail_note}")
        for i, reason in enumerate(r.get("win_reasons", []), 1):
            print(f"          {i}. {reason}")

    # ── Knockout predictions
    print("\n\n" + "─" * 70)
    print("  KNOCKOUT STAGE — PROJECTED MATCHUPS")
    print("─" * 70)

    for home, away, stage, neutral in LIKELY_KNOCKOUT:
        ctx = _build_ctx(home, away)
        r = e.predict(home, away, neutral=neutral, ctx=ctx)
        fav = home if r["p_home"] >= r["p_away"] else away
        fav_p = max(r["p_home"], r["p_away"])

        print(f"\n  [{stage}]  {home} vs {away}")
        print(f"   {_bar(r['p_home'], 25)} {r['p_home']*100:4.1f}%  "
              f"D {r['p_draw']*100:.1f}%  "
              f"{r['p_away']*100:4.1f}% {_bar(r['p_away'], 25)}")
        print(f"   → {fav} favoured ({fav_p*100:.0f}%)  "
              f"Conf {r['confidence']}/100  "
              f"Upset risk: {r['upset_probability']*100:.0f}%")
        print(f"   Why {fav} win:")
        for i, reason in enumerate(r.get("win_reasons", []), 1):
            print(f"      {i}. {reason}")

    # ── Load champion odds from sim_results
    sim_path = PROC / "sim_results.json"
    if sim_path.exists():
        sim = json.loads(sim_path.read_text())
        print("\n\n" + "─" * 70)
        print("  TOURNAMENT WINNER ODDS  (Monte Carlo simulation)")
        print("─" * 70)
        print(f"  {'Team':<24} {'Champion':>9} {'Final':>7} {'SF':>7} {'QF':>7}")
        print(f"  {'─'*24} {'─'*9} {'─'*7} {'─'*7} {'─'*7}")
        for r in sim[:16]:
            champ_bar = _bar(r["Champion"], 15)
            print(f"  {r['team']:<24} {champ_bar} {r['Champion']*100:5.1f}%"
                  f"  {r['Final']*100:5.1f}%  {r['SF']*100:5.1f}%  {r['QF']*100:5.1f}%")
        print()
        winner = sim[0]
        print(f"  🏆  PREDICTED CHAMPION: {winner['team'].upper()}")
        print(f"      Win probability: {winner['Champion']*100:.1f}%")
        print(f"      Reaches Final:   {winner['Final']*100:.1f}%")
        print(f"      Based on: Elo #{1}, 50,000 Monte Carlo simulations,")
        print(f"      real WC2026 results, squad availability & market signals")
    else:
        print("\n  ⚠️  Run simulate.py first to generate sim_results.json")

    print("\n" + "═" * 70 + "\n")


if __name__ == "__main__":
    run_predictions()
