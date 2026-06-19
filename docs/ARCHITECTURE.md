# Architecture

How the WC2026 Prediction Platform is put together, end to end.

## High-level flow
```
internationals CSV ─┐
                    ├─ retrain.py ─▶ Elo ratings ─▶ Dixon-Coles fit ─▶ XGBoost
WC2026 results  ────┘                    │                                │
(fixtures.py)                            ▼                                ▼
                              data/processed/*.parquet, *.pkl  (model artifacts)
                                         │
   live feeds (odds, injuries, weather) │
   ESPN scorers (events.py)             ▼
                              ┌──────────────────────┐
                              │   ensemble.Ensemble   │  blends members +
                              │  + player_condition   │  squad-condition shift
                              └──────────┬───────────┘
                                         │
              ┌──────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
     /api/predict (match)        simulate.py (50k MC)        predict_wc2026.py
     /api/matches/{id}           → champion / stage odds      (CLI full report)
     /api/matches/{id}/analytics
                                         │
                                         ▼
                                 Next.js dashboard (frontend/)
```

## Backend layers

### 1. Data provider — `app/fixtures.py`
Single source of truth for the real 2026 draw, the full schedule (MD1 results +
MD2/MD3 fixtures with ET kickoffs and venues), curated marquee squads, and
team metadata. Canonical team names match the martj42 results dataset so Elo /
Dixon-Coles lookups line up. The API runs entirely off this provider when
Postgres is disabled (the default).

`group_tables()` computes live standings (MP/W/D/L/GF/GA/GD/Pts) from played
matches, sorted by FIFA tie-break order.

### 2. ML package — `ml/` (flat, importable modules)
- **`elo.py`** — FiveThirtyEight-style Elo with margin-of-victory scaling over
  ~150 years of internationals.
- **`poisson.py`** — independent Poisson goal model from Elo-implied rates.
- **`model.py`** — Dixon-Coles bivariate-Poisson with time decay. Produces the
  score matrix everything else samples from.
- **`xgb_model.py` / `nn_model.py`** — feature classifiers (form, rest, h2h,
  availability, market edge). NN is optional (PyTorch).
- **`tournament_form.py`** — patches Elo with the actual WC2026 MD1/MD2 results
  using a lighter K-factor, so in-tournament form propagates to every member.
- **`player_condition.py`** — `TeamConditionEngine`: builds a 0–1 condition
  score per team from player form, fitness, availability, attack/defence. Two
  outputs: a logit shift on win probabilities, and `win_reasons()` (ranked
  plain-language "3 reasons this team wins"). Momentum is excluded from the
  applied shift to avoid double-counting the Elo patch.
- **`ensemble.py`** — blends members with renormalizing weights, then applies
  availability, travel/weather, and squad-condition shifts. Returns W/D/L,
  expected goals, top-3 scorelines, confidence, upset probability, explanation,
  predicted winner, and win reasons.
- **`simulate.py`** — 50k Monte Carlo tournaments. Pre-caches all 2,256 pairwise
  Dixon-Coles score matrices once (≈40× speedup), tilts each by its squad-
  condition shift, then samples. Aggregates per-team stage probabilities.
- **`insights.py`** — dark horses (over-performing their seed) + upset alerts.
- **`backtest.py`** — walk-forward, leak-free validation over the 2014/18/22
  World Cups (pooled RPS ≈ 0.205, beating the 0.243 base rate).

### 3. Post-match analytics — `app/match_analytics.py` + `app/events.py`
- `events.py` scrapes **real goalscorers** from ESPN's open scoreboard JSON
  (date-by-date), maps team names to canonical spelling, caches to
  `data/raw/match_events.json`.
- `match_analytics.py` serves scorers (real when cached, else model-generated)
  plus a **deterministic** (seeded by match id) shot map, heat map, passing
  network, and box score. The maps are illustrative — labeled in the API and UI
  — because coordinate-level event data isn't openly available.

### 4. API — `app/main.py` + `app/routers/`
FastAPI. `ml_engine.py` is the bridge: it owns the singleton `Ensemble`, wraps
predictions in an optional Redis cache, and adds `ml/` to `sys.path` so the flat
modules import unchanged. Postgres (SQLAlchemy) is optional via `USE_DB`.

## Frontend — `frontend/`
Next.js 14 App Router + TypeScript + Tailwind. `lib/api.ts` is the typed client
(defaults to `http://localhost:8000`). `components/ui.tsx` holds shared widgets
(MatchCard, ProbBar, Flag, etc.); `components/match-analytics.tsx` renders the
SVG pitch visualizations. Data is fetched with SWR; charts use Recharts; motion
via Framer Motion. Layouts are mobile-first responsive (names wrap, wide tables
scroll, hero rows stack on small screens).

## Key design decisions
- **Graceful degradation:** any missing ensemble member (no `torch`, no odds for
  a fixture, untrained artifact) drops out and weights renormalize. The API
  never crashes for a missing optional dependency.
- **No double-counting:** tournament momentum lives in the Elo patch only; the
  squad-condition shift deliberately excludes it. The same shift is applied in
  both the match-level ensemble and the Monte Carlo sim, so they agree.
- **Deterministic illustrations:** generated analytics are seeded by match id so
  a given match always renders the same picture.
- **Artifacts are regenerated, not committed:** large data/models are gitignored;
  `retrain.py` rebuilds them. Small real sample data is committed for an
  out-of-the-box demo.
