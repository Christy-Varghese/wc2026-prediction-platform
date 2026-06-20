# WC2026 Prediction Platform — Session Handover

Date: 2026-06-20
Branch: `main` · **nothing committed yet** — all changes are in the working tree.

---

## 1. ML ensemble priority re-weighting — DONE

Goal: prioritise player form / team combination / manager stats; de-prioritise
location stats.

Files: `backend/ml/ensemble.py`, `backend/ml/player_condition.py`

- `CONDITION_COEF` 1.35 → **1.75** (squad signal hits harder).
- `TRAVEL_COEF` 0.16 → **0.08**, `WEATHER_COEF` 0.07 → **0.035** (location halved).
- Elo `home_adv` 65 → **35** in `_elo_probs` (softer venue edge; WC games neutral anyway).
- `player_condition.py`:
  - condition composite: form weight 0.30 → **0.42**, momentum 0.15 → **0.03**.
  - new `MANAGER_WINRATE` table (8 marquee teams, default 0.50) — kept local so
    `ml/` stays standalone (no `app` import).
  - `match_condition_adjustment` logit shift: `cond_delta` 0.40 → **0.55**,
    `att_def_adv` (team combination) 0.25 → **0.30**, **+0.20 × manager_delta**.
    Returns `home/away_manager_wr`.
- Verified end-to-end; manager delta flows through. Monte Carlo `simulate.py`
  reads the same `match_condition_adjustment`, so champion odds inherit it.

---

## 2. Reliability-aware confidence + calibration + dynamic weights — DONE

Goal: confidence reflects real reliability (not cosmetic inflation); calibration;
dynamic member weighting; all with graceful fallback; no API break.

New file: `backend/ml/calibration.py` (offline fit-side toolkit)
- Metrics: LogLoss, RPS, Brier, ECE (10-bin), top-1 acc, confidence buckets.
- Calibrator fitters: scalar temperature + per-class vector temperature
  (`select_calibrator` adopts a fit ONLY if it beats identity on a held-out
  split — else identity).
- `fit_dynamic_weights` (inverse-log-loss, capped, min-sample gated).
- `build_artifacts()` writes the 3 runtime artifacts (honest before/after).

`backend/ml/ensemble.py`
- `_confidence()` coverage bug fixed (`/5` → `/TOTAL_MEMBERS` = `len(WEIGHTS)` = 6).
- New confidence formula: `0.35 agreement + 0.35 decisiveness + 0.12 coverage +
  0.18 reliability`, clipped 5..99, monotonic.
- `Calibrator` class: method dispatch (`temperature` | `vector_temperature`),
  identity fallback on missing/corrupt; output guaranteed normalized/finite/positive.
- `_weights_from_metrics` gated by `MIN_MEMBER_SAMPLES` (30).
- `_reliability_from_metrics` keys off ECE + confidence-bucket gap (dropped
  mis-scaled multiclass Brier term).
- Synthetic-market de-trust: `SYNTH_MARKET_WEIGHT_PENALTY` (0.25) shrinks the
  Elo-synthesised market weight at predict time + `SYNTH_MARKET_CONF_PENALTY` (4)
  docks confidence. Wired into `predict()` (`eff_w`).
- `__init__` loads `self.weights` / `self.calibrator` / `self.reliability` (all fall back safely).

`backend/ml/backtest.py`
- Emits OOS member columns: `poisson_*` + synthetic `market_*`.
- `fit_reliability_artifacts()` scores held-out, fits + writes artifacts, prints before/after.
- `run()` now returns the calibration report.

`backend/ml/retrain.py` — added `_calibrate` step (runs backtest → artifacts).

`backend/ml/features.py` — `feature_coverage_report()` flags dead train-time
features, warns, persists `feature_coverage.json`. Hooked into `build_training_frame`.

### Generated artifacts (in `backend/data/processed/`)
`calibrator.json`, `member_metrics.json`, `reliability.json`, `feature_coverage.json`.

### Tests — ALL PASS (32)
- `backend/tests/test_calibration_engine.py` (7)
- `backend/tests/test_ensemble_reliability.py` (11)
- `backend/ml/tests/test_ensemble_confidence.py` (14)
- Run: `source .venv/bin/activate && python backend/tests/test_calibration_engine.py`
  (each file is standalone-runnable; also pytest-compatible).

### Honest backtest result (held-out WC 2014/18/22, 192 matches)
| Metric | legacy blend | after (de-trust + calib) | vs legacy |
|---|---|---|---|
| LogLoss | 0.9727 | 0.9710 | +0.2% |
| ECE | 0.0724 | 0.0587 | **+18.9%** |
| RPS | 0.2042 | 0.2037 | +0.2% |

- ECE + RPS gates met. **LogLoss 3% target NOT met** — model already near the
  irreducible ~0.97 floor for 3-way football; learned weights/temperature overfit
  the 3-tournament structure (confirmed by LOTO-CV). Refused to game it with
  in-sample fitting. Calibrator correctly ships near-identity; the real win is the
  principled synthetic-market de-trust.
- Biggest future lever: real book-odds feed + the NN member (`torch` not installed).

README: added "How calibration + dynamic weighting works" section.

---

## 3. Knockout projection + page update — IN PROGRESS (NOT STARTED CODING)

Goal: run the knockout matches from available data; fill the bracket with real
projected teams (current + past player/team info); update the knockout page.

### Research done (key facts)
- `/api/knockout` (`backend/app/routers/predictions.py:33`) currently returns
  **placeholder labels** ("Winner Group A", "3rd Group A/B/C/D/F", "Winner Match 73").
- Bracket structure is in `backend/app/knockout.json` (32 matches):
  - R32 (16): slots are group winners / runners-up / specific 3rd-place groups.
  - R16/QF/SF/Final/Third (16): slots reference `Winner Match N` / `Loser Match N`.
  - Match-id linkage map (R16→Final) already extracted — see knockout.json.
- Group data: `fixtures.REAL_GROUPS` (A–L → teams), `fixtures.team_group(name)`,
  `fixtures.group_tables()` (standings from PLAYED matches), `fixtures.schedule()`
  (every match, `played` flag + scores + `group` + `stage`). Only **MD1 played**;
  MD2/MD3 unplayed → standings must be **projected**.
- Prediction with reasons: `services.predict(home, away, neutral=True, match=None)`
  → full ensemble dict incl. `predicted_winner`, `win_reasons` (3 player/team
  reasons), `p_home/p_draw/p_away`, `top_scores`, `confidence`. (`services.predict`
  → `ml_engine.predict_match`.)
- `simulate.py` does Monte Carlo but **shuffles advancers** — gives stage odds,
  NOT a deterministic bracket aligned to the official slots. Do not reuse for the
  bracket fill.

### Next steps (build plan)
1. **New module `backend/app/knockout_engine.py`:**
   - `project_group_standings()` — per group, accumulate points/GD: PLAYED matches
     use real scores (`fixtures.schedule()`); UNPLAYED use `services.predict` →
     expected pts (`3·pH + pD` home / `3·pA + pD` away) + expected GD
     (`xg_home − xg_away`). Rank `(pts, gd)` → winner / runner-up / 3rd per group.
   - `best_eight_thirds()` — rank the 12 third-placed teams, take top 8.
   - `assign_third_slots()` — parse each R32 3rd-label's allowed groups
     (e.g. "3rd Group A/B/C/D/F" → {A,B,C,D,F}); backtracking perfect-matching
     (slots ordered fewest-options-first) to place the 8 qualifying thirds. Fallback
     to greedy-by-rank if no perfect matching.
   - `resolve_bracket()` — fill R32 from group projection; process rounds in order
     (r32 → r16 → qf → sf → third/final), resolving `Winner/Loser Match N` from
     prior results; run each tie via `services.predict`; winner = higher win-prob
     side (knockouts have no draw — note penalties when probs ~level). Record
     home/away real teams, probs, predicted winner, predicted score
     (`top_scores[0]`), confidence, 3 reasons, kickoff/city/venue. Memoize with
     `functools.lru_cache` (~80 ensemble predicts total — fine for one API call).
2. **Wire `/api/knockout`** (`routers/predictions.py`) to return the resolved
   bracket. **Keep existing keys** (`rounds`, `matches`) for backward compat;
   enrich each match with: `home_team`, `away_team`, `home_label`/`away_label`
   (keep originals), `prediction` block, `predicted_winner`, `predicted_score`,
   `confidence`, `reasons`. Add top-level `champion` + `projected: true`.
3. **Frontend `frontend/app/knockout/page.tsx`** — render real teams + flags,
   predicted winner highlight, scoreline, win-prob bar, expandable 3 reasons.
   Current page only shows `home_label`/`away_label` + venue (read at lines 46–53).
   Keep graceful fallback to labels when a slot is still unresolved.

### Watch-outs
- Canonical team names must match the Elo/DC dataset (martj42 spelling) — use the
  names already in `REAL_GROUPS` so `services.predict` lookups resolve.
- `services.predict` is ~tens of ms each; memoize the whole resolved bracket.
- Do NOT mutate `knockout.json` — resolve at runtime so it re-projects as MD2/MD3
  results land.

---

## Environment / repro
```bash
cd /Users/christyvarghese/Documents/ObsidianVault/SecondBrain/wc2026-prediction-platform
source .venv/bin/activate
# rebuild ML + calibration artifacts (idempotent):
cd backend/ml && python retrain.py        # full (slow: DC refit + 50k sim + backtest)
# OR just refit calibration artifacts from existing backtest preds (fast):
python -c "import backtest; backtest.fit_reliability_artifacts()"
# run API:
cd backend && uvicorn app.main:app --reload --port 8000
# tests:
python backend/tests/test_calibration_engine.py
python backend/tests/test_ensemble_reliability.py
```

### Open background process
- A `retrain.py` run (started during task 1) may still be alive / network-hung on
  `force_download`. A prior full retrain already completed (`meta.json` ok). Safe to
  `pkill -f retrain.py` if it's stuck; it ran pre-change code so it won't overwrite
  the new calibration artifacts.

## Known caveats
- `ensemble.py` edits were silently rolled back once mid-session (editor/linter)
  and re-applied. If something looks missing, grep for: `vector_temperature`,
  `MIN_MEMBER_SAMPLES`, `SYNTH_MARKET`, `eff_w`, `_sanitize_temp`.
- `torch` not installed → NN member off (intentional). XGBoost member active.
- Nothing committed. Suggested commit grouping: (1) ensemble priority reweight,
  (2) calibration/reliability infra + tests, (3) knockout projection once built.
</content>
