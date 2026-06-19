
"""Project config: paths, 2026 World Cup format, qualified/projected teams."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROC = DATA / "processed"
for _d in (RAW, PROC):
    _d.mkdir(parents=True, exist_ok=True)

# International results CSV (martj42 dataset, mirrored on GitHub).
RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/"
    "master/results.csv"
)
RESULTS_CSV = RAW / "results.csv"

# --- 2026 World Cup format -------------------------------------------------
# 48 teams, 12 groups of 4. Top 2 of each group + 8 best 3rd-place advance
# to a 32-team knockout round.
N_GROUPS = 12
TEAMS_PER_GROUP = 4
N_THIRD_PLACE_ADVANCE = 8  # best 8 of 12 third-placed teams

# Elo model params
ELO_START = 1500.0
ELO_K = 40.0          # base K-factor
ELO_HOME_ADV = 65.0   # rating points added to home side
ELO_MOV = True        # scale K by margin of victory

# Dixon-Coles params
DC_XI = 0.0018        # time-decay (per day); ~0.5 weight at ~1 year
DC_MAX_GOALS = 10     # truncate Poisson grid

# Monte Carlo
N_SIMS = 50000

# Real 2026 World Cup group draw (5 Dec 2025) — used by simulate.py so the MC
# runs within the ACTUAL bracket, not a random re-draw each simulation.
REAL_GROUPS_2026: list[list[str]] = [
    ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    ["Brazil", "Morocco", "Haiti", "Scotland"],
    ["United States", "Paraguay", "Australia", "Turkey"],
    ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    ["Netherlands", "Japan", "Sweden", "Tunisia"],
    ["Belgium", "Egypt", "Iran", "New Zealand"],
    ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    ["France", "Senegal", "Iraq", "Norway"],
    ["Argentina", "Algeria", "Austria", "Jordan"],
    ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    ["England", "Croatia", "Ghana", "Panama"],
]

# Real 2026 World Cup field — the 48 qualified teams (final draw, 5 Dec 2025).
# Canonical names match the martj42/Kaggle results dataset for Elo/DC lookups.
PROJECTED_FIELD = [
    "Mexico", "South Africa", "South Korea", "Czech Republic",
    "Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland",
    "Brazil", "Morocco", "Haiti", "Scotland",
    "United States", "Paraguay", "Australia", "Turkey",
    "Germany", "Curaçao", "Ivory Coast", "Ecuador",
    "Netherlands", "Japan", "Sweden", "Tunisia",
    "Belgium", "Egypt", "Iran", "New Zealand",
    "Spain", "Cape Verde", "Saudi Arabia", "Uruguay",
    "France", "Senegal", "Iraq", "Norway",
    "Argentina", "Algeria", "Austria", "Jordan",
    "Portugal", "DR Congo", "Uzbekistan", "Colombia",
    "England", "Croatia", "Ghana", "Panama",
]
