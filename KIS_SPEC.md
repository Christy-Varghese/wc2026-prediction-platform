# KIS — Knockout Intelligence System
### Product & architecture spec — extends WC26 CAI Predictor

Status: **All 5 phases shipped 2026-07-07. KIS v1 is complete.** `/kis` is
live end to end — data pipeline, vector engine, API, frontend, and now full
regression coverage across every played WC2026 knockout match plus stress/
edge-case testing. 116/116 backend tests passing. All four open decisions
(D1-D4) resolved — see §10. One known, documented gap remains (DB
idempotency, acceptance criterion 5 — can't be exercised in this dev
environment; see the Phase 5 status note).

**Post-v1 — KIS surfaced on the live bracket (2026-07-07):**
- Ran KIS against every one of the 9 currently-unresolved bracket ties (R16
  through the Final, via `knockout_engine.resolve_bracket()`'s live
  cascade — not a frozen list) and compared to the existing engine's
  projected winner for each. **Answer: no, KIS does not change any
  projected result.** Argentina remains projected champion, Spain runner-up,
  every intermediate tie agrees. Expected, given Phase 5 already confirmed
  100% agreement across all 23 *played* matches — KIS reprojects the same
  underlying model at higher N, it isn't a competing model. Enforced going
  forward as `test_kis_agrees_with_bracket_on_every_upcoming_tie` (checks
  the live bracket, not a hardcoded snapshot, so it keeps validating as
  results come in).
- `frontend/components/kis-powered-card.tsx` (new) — surfaces a live KIS
  simulation on `/knockout/[id]`, the per-tie detail page every bracket
  match already links to, for **upcoming (unplayed) ties only** (played
  ties keep their own post-match analysis). Reuses `KisVectorGrid`/
  `KisPressureGauge` from the `/kis` Hub — no duplicated vector-rendering
  logic. A click-to-expand "ⓘ How it works" section explains the Skill/Luck
  methodology in plain language, closing the loop the original request
  asked for ("when clicked on it will describe how it works").
- Browser-verified (France v Morocco QF, an upcoming tie): collapsed and
  expanded states both render correctly, zero console errors, the existing
  pre-match prediction and the new KIS card visibly agree on the same
  winner/scoreline — which is itself useful UI signal (independent
  confirmation, not a contradiction a user has to reconcile).

**Post-v1 follow-up — a real bug found by asking "does KIS change the win% and
confidence, specifically" (2026-07-07):** Predicted *winner* agreement (above)
turned out to hide a real gap: comparing win_probability/confidence directly
against `resolve_bracket()`'s numbers for the same 9 fixtures showed
confidence deltas up to **22 points** — not modeling disagreement, an
implementation bug.

- **Root cause**: `backend/app/routers/kis.py` built `base` via
  `ml_engine.predict_match()` directly, skipping `services.predict()`'s
  `_ctx_for()` context (injury-availability + squad-strength differentials)
  that `knockout_engine._resolve_tie()` — the bracket's own prediction path —
  always builds. Confirmed directly: `services.predict("France","Morocco")`
  → conf 29; the same call via bare `ml_engine.predict_match()` → conf 39.
  Real signal was silently dropped.
- **Second gap**: `_resolve_tie()` docks confidence by 15 points when the
  ensemble's stat-driven pick and the Monte Carlo's regulation-time pick
  disagree (a genuine uncertainty signal). `kis_engine.compose()` never
  replicated that check, so it always reported the raw, undocked confidence.
- **Fix**: `routers/kis.py` now calls `services.predict()`; `compose()` now
  replicates the pipeline-disagreement penalty inline. Re-verified against
  all 9 upcoming ties, through the actual HTTP route (not just the internal
  engine call): **confidence now matches exactly (0 delta) on every tie**;
  win_probability delta dropped to a max of 1.23 percentage points — genuine
  Monte Carlo noise (N=6,000 vs N=50,000 of the same model), not a bug.
- **Why Phase 5's regression suite didn't catch this**: those tests built
  `base` the same (buggy) way for both the `match_flow` and `kis` sides of
  each comparison — internally consistent, but never checked against the
  bracket's own `services.predict()`-based numbers. Added
  `test_kis_route_confidence_and_win_prob_match_bracket_within_tolerance`
  (routes through the actual FastAPI endpoint, not `ml_engine.kis()`
  directly, since the bug lived in the router) to close that gap
  permanently.
- Full suite: **118/118 passing** (117 + this new test).

**Post-v1 follow-up #2 — the deployed demo showed "backend offline"
(2026-07-07):** The Vercel deployment is backend-free by design (see
`README.md`) — `frontend/lib/api.ts` falls back to pre-generated static
JSON (`gen_snapshots.py`) whenever the live backend is unreachable. That
fallback only works for **GET** requests (`gen_snapshots.py`'s `grab()` only
calls `client.get(path)`); `/api/v1/predict/kis` was a POST route, so it
could never be pre-snapshotted and always showed "KIS simulation
unavailable — backend offline" on the deployed site.

- **Fix**: converted the route from `POST` (JSON body) to `GET`
  (querystring) — `home_team`/`away_team`/etc. as query params, matching
  this app's own existing convention (`GET /api/predict?home=&away=`) that
  the original mega-request's literal `POST` sample deviated from without
  good reason. `kis-powered-card.tsx` and `/kis/page.tsx` updated to fetch
  via `api()`'s normal GET path, which already has snapshot fallback built
  in — no new frontend fallback logic needed.
- `gen_snapshots.py` now pre-generates a KIS snapshot for every
  **currently-unresolved bracket tie**, pulled live from the knockout
  response (not hardcoded), so it stays correct as results come in. An
  arbitrary "what-if" pairing typed into the `/kis` Hub that isn't one of
  those ties still needs a live backend — there's no way to pre-snapshot
  every possible team combination, and the existing offline error is the
  honest behavior for that case.
- **Verified for real**, not assumed: ran the frontend with
  `NEXT_PUBLIC_STATIC_ONLY=1` and the Python backend **not running at all**
  (curl confirmed connection refused) — both `/knockout/97` (France v
  Morocco, an upcoming tie) and the `/kis` Hub (Spain v Belgium, a snapshotted
  matchup) rendered the full KIS breakdown from the static snapshot alone.
  Zero "backend offline" errors, zero console errors.
- Tests updated to GET (`test_kis_api.py`, all 10 tests), plus a new
  `test_kis_get_request_is_snapshottable_shape` guard so the route can't
  silently regress back to POST-only. Full suite: **119/119 passing.**

**Phase 1 — what actually shipped:**
- `backend/ml/xgb_model.py` confirmed already trained (`data/processed/xgb_model.ubj`
  exists, `xgb_model.load()` returns non-None) and already live in
  `ensemble.py`'s blend (`WEIGHTS["xgb"] = 0.18`). The §6.3 open question is
  resolved: **no new ML pipeline work needed** — KIS reuses the existing
  ensemble as-is.
- `backend/ml/tournament_stats.py`: added `comeback_rate()`,
  `defensive_variance()`, `late_game_breakdown_rate()` (KIS §4[1]/[5]).
  Pure functions over `WC2026_PLAYED` + `match_events.json`; matches without
  minute-stamped event data are excluded from denominators, not counted as 0.
- `backend/ml/player_condition.py`: added `KNOCKOUT_PEDIGREE` (curated,
  real pre-2026 knockout experience + shootout record for all 32 WC2026
  Round-of-32 teams) and `knockout_pedigree(team)` accessor, feeding KIS
  §4[6] Pressure Score. Unlisted teams get `basis: "default"`, not a guess.
- **Scoped out of Phase 1, deferred to Phase 3**: `captain_maturity` and
  `sub_aggression` (two of the five Pressure Score inputs in §4[6]) need
  per-player data — captain identity, caps — that isn't in `squads.json`
  (name/position/club/number only) and can't be responsibly curated for a
  fictional 2026 squad list the way real-world knockout/shootout history
  can. Building a Pressure Score composite with 3/5 real inputs and 2/5
  fabricated ones would violate the spec's own §2/D1 honesty principle, so
  those two inputs are left for Phase 3 to solve properly (or drop) rather
  than faked now.
- Tests: `backend/ml/tests/test_tournament_stats_kis.py` (7),
  `backend/ml/tests/test_knockout_pedigree_kis.py` (5). Full suite:
  51/51 passing.

**Phase 2 — what actually shipped:**
- `backend/ml/kis_engine.py` — new standalone module (not imported by any
  API route). Implements:
  - `tactical_rating(team)` — §4[2] heuristic proxy (`basis: "heuristic"`,
    per the D1 honesty principle — not PPDA, clearly labeled).
  - `pressure_score(team, composure)` — §4[6] composite using the 3 inputs
    that exist (knockout experience + shootout record from Phase 1,
    composure reused from `match_flow`), renormalized and labeled
    `basis: "partial_3_of_5_inputs"` with `excluded_inputs` named explicitly
    (`captain_maturity`, `crowd_factor` — still deferred, see Phase 1 note).
  - `skill_score()` — §5.2 S_t, reprojecting `match_flow.MODEL_WEIGHTS`'
    5-way blend into 3 renormalized terms (fatigue, tactical, psychology;
    weather is treated as an L_t input, not S_t — see the module docstring).
  - `luck_bias()` — §5.3 mu_bias, computed as mean(actual goals - Dixon-Coles
    `_lambdas()` retrospective estimate) across each team's played WC2026
    matches. Returns `basis: "unavailable_no_matches"` / `"unavailable_no_dc_model"`
    rather than a fabricated 0 when the signal can't be computed.
  - `chaos_sigma()` — §5.3 sigma_chaos, blends the existing `weather.py`
    severity signal with a `referee_strictness` input that defaults to a
    labeled neutral (`basis: "static_neutral_default"`) — the spec's flagged
    gap (no referee dataset exists) is surfaced, not silently defaulted away.
  - `_tag_chaos_runs()` / `simulate_kis()` — §5.4/§5.5: reuses
    `match_flow._simulate()`'s vectorized Poisson core (not reimplemented)
    at `KIS_N_SIMS = 50,000`, then flags runs whose sampled goal margin
    deviates >2.5σ from the model's expected margin (Skellam-distribution
    sigma = √(λ_home + λ_away), not a fitted parameter).
  - `narrate_with_chaos()` — §5.5 minute-tagged narrative overlay. Wraps
    (doesn't modify) `match_flow._narrative()`, tagging goal events
    `vector_dominant: "skill"|"luck"`. Confirmed non-invasive: existing
    `match_flow.simulate_tie()` output is byte-for-byte unaffected
    (`test_match_flow_simulate_tie_unaffected_by_kis_module`).
- **§5.5 benchmark — measured, not assumed** (the spec's own requirement):
  50,000-run `simulate_kis()` calls across 6 different real fixtures, 5 runs
  each (n=30): **p50 = 3.66ms, p95 = 4.01ms, max = 4.01ms** — over 100×
  under the 400ms target. Confirms the §5.5 recommendation (vectorized
  whole-match core, not a literal per-minute loop) was the right call, with
  headroom to spare even after the Phase 3 API/DB layer adds overhead.
- Tests: `backend/ml/tests/test_kis_engine.py` (20, including the 50k-run
  performance regression guard). Full suite: **71/71 passing.**

**Phase 3 — what actually shipped:**
- `backend/ml/kis_engine.py::compose()` — the §4[8] composition layer.
  Mirrors (does not call) `match_flow.simulate_tie()`'s orchestration —
  same `_profiles()`/`_simulate()`/seed, but at `KIS_N_SIMS` (50,000) and
  with `narrate_with_chaos()`-tagged events instead of the untagged
  `_narrative()`. `match_flow.py` remains untouched. Verified: `predicted_winner`
  matches `match_flow.simulate_tie()`'s for the same fixture on every tested
  pair (Argentina/Switzerland, France/Morocco, Spain/Belgium, Norway/England),
  win-probability deltas 0.002-0.012 (Monte Carlo noise from N=6k vs N=50k of
  the identical model) — acceptance criterion 2 confirmed empirically.
- **D4 resolved by precedent, not guesswork**: checked whether the existing
  app already supports "what-if" (non-scheduled) matchups — `services.predict()`
  has zero fixture-scheduling validation, any two team names work. KIS follows
  the same pattern (`match_id` nullable in the schema below); the API route
  adds team-name-existence validation (404 on a typo) that `/api/predict`
  itself lacks, since a plausible-looking prediction for a misspelled team is
  worse than a clear error.
- `backend/app/routers/kis.py` — `POST /api/v1/predict/kis`. Validates both
  team names exist (`fixtures.team_index()`) and differ; delegates entirely
  to `ml_engine.kis()` → `kis_engine.compose()`.
- `backend/app/ml_engine.py::kis()` — bridge function, same Redis-cache
  pattern as the existing `match_flow()` (cache key extended with
  weather/referee inputs, since those change the output).
- `backend/app/models.py` — added `KISSimulation` (nullable `match_id` per
  D4) and `TeamPressureInput` ORM models, purely additive. **Not yet
  migrated/populated** — `settings.use_db` defaults `False` and the default
  `database_url` points to `localhost`, not any live/production database
  (confirmed: `frontend/lib/supabase.ts`'s Supabase Postgres, used for the
  `feedback` table, is a completely separate connection the Python backend
  never touches). No live schema was touched by this change. Note: this repo's
  `models.py` already required Python 3.10+ for its pre-existing `Match`/`ModelRun`
  classes' `X | None` union-type annotations (confirmed via `git stash` — the
  same failure reproduces on unmodified `main`), so ORM-level validation
  couldn't be exercised in this Python-3.9 dev environment; my additions
  follow the same syntax convention as the rest of the file and are
  unaffected beyond that pre-existing, environment-specific limitation.
- Reconciled one shape mismatch between the original request and Phase 2:
  the request's `weather_condition` enum (Clear/Rain/Extreme_Heat) is now a
  **fallback** used only when no real `city` is given — a real venue's
  `weather.py` climate signal always wins when available, never silently
  overridden by the enum.
- Tests: `backend/tests/test_kis_api.py` (9, via FastAPI `TestClient` —
  same pattern `gen_snapshots.py` already uses, no live server needed).
  Full suite: **80/80 passing.**

**Phase 4 — what actually shipped:**
- **D2 resolved**: rather than a generic `pitch`-green token, added ONE new
  KIS-scoped color (`chaos`, violet `#B14EFF`) and reused the site's
  existing `success` grass-green for "Skill" — `success` already means
  "on-model / correct" sitewide (`PredictionBadge`, `FitBadge`), so Skill
  inherits that meaning for free instead of introducing a redundant green.
  Added to `tailwind.config.ts`, used only in the three `kis-*.tsx`
  components below — confirmed no other page's styling changed.
- **Found the disclaimer requirement was already satisfied**: checked
  `frontend/app/layout.tsx` before adding anything — the sitewide footer
  already reads "Not affiliated with FIFA. Not betting advice. Tournament
  predictions for entertainment." Added no second, redundant disclaimer;
  the KIS Hub surfaces the API's own `disclaimer` field once at the bottom
  of the results for extra clarity given it's a live simulation, not a
  duplicate footer.
- `frontend/app/kis/page.tsx` — the KIS Hub. Team-vs-team picker (two
  `<select>`s sourced from the existing `/api/teams` list, idle/loading/
  error states following `feedback.tsx`'s established pattern) that POSTs
  to `/api/v1/predict/kis` and renders the result. Composes:
  - `<MatchFlowReport flow={result} />` — **reused unmodified**. Confirmed
    `compose()`'s Phase 3 output shape renders correctly through this
    existing component with zero changes to `match-flow.tsx`, because
    `compose()` was deliberately built to mirror `simulate_tie()`'s exact
    field names (§4[8]'s point, now visually confirmed).
  - `kis-vector-grid.tsx` (net-new) — Skill/Luck bars per team + tactical
    rating + shared σ_chaos, with `basis`/`3/5 inputs` disclosure tooltips
    (D1 honesty principle carried into the UI, not just the API).
  - `kis-pressure-gauge.tsx` (net-new) — radial 0-100 gauges, explicit
    "ⓘ 3/5 inputs" label (same D1 principle).
  - `kis-chaos-timeline.tsx` (net-new) — the vertical chronological
    match-flow timeline the original request asked for, extending
    `match_flow`'s events with skill/luck tags from
    `narrate_with_chaos()` (Phase 2), plus a footnote clarifying the
    tagging is a narrative overlay on the fixture's overall chaos rate,
    not a per-goal measurement.
- `nav.tsx` — added the KIS tab (`⚡` icon) to `LINKS`. Did **not** wire a
  live ticker feed for KIS (the original Phase 4 line item) — the ticker
  pulls from `/api/news`, which aggregates match *results*, not simulation
  runs; feeding it KIS chaos-event strings would need `news.py` changes
  outside this spec's scope (news aggregation, not knockout intelligence).
  Flagged, not silently dropped.
- **Browser-verified** (Playwright, real backend, not just typecheck):
  - Desktop (1400px): full KIS Hub render, Argentina vs Switzerland —
    vector grid, pressure gauges, chaos timeline, and the reused knockout
    report all correct, matching the live API response exactly.
  - Mobile (390px, iPhone-class viewport): Brazil vs Germany (a
    **hypothetical, non-scheduled matchup** — the D4 what-if case) —
    no horizontal overflow, cards stack cleanly, extra-time scenario
    renders with correct chaos tagging. Acceptance criterion 7 confirmed,
    not assumed.
  - Zero console errors, zero React warnings in either run.
- `npx tsc --noEmit` clean.

**Phase 5 — what actually shipped:**
- `backend/tests/test_kis_regression.py` (35 tests) — the core Phase 5
  deliverable:
  - **Full regression, not a sample**: all 23 already-played WC2026
    knockout matches (`tournament_form.WC2026_PLAYED_KNOCKOUT` — the exact
    ledger `simulate.py`/`match_flow.py` are keyed on, not a hand-picked
    list) round-tripped through `ml_engine.kis()`, each checked against
    `match_flow`'s output for the same fixture: same `predicted_winner`,
    `win_probability` within simulation noise, valid probability schema.
    Zero divergences across all 23.
  - **Basis-label audit** (acceptance criterion 4): confirmed every
    heuristic/partial field (`tactical_rating`, `pressure_score`,
    `vector_metrics`) carries its label, and an uncurated team's pedigree
    lookup reports `basis: "default"` rather than a silent guess.
  - **Edge cases**: group-stage (`knockout=False`) mode, referee-strictness
    extremes (0.0/1.0), `Extreme_Heat` with no real venue, a real venue
    correctly overriding the weather enum, a team with zero curated
    shootout history, a team entirely absent from every table (Elo-fallback
    degrades gracefully, doesn't throw).
  - **Determinism** (the actual testable half of acceptance criterion 5 —
    see the gap note below): confirmed `kis_engine.compose()` returns
    byte-identical `vector_metrics`/`chaos_events`/`predicted_score` for two
    calls with identical inputs, and a genuinely different input
    (`referee_strictness`) produces a different result — i.e., the
    upsert-on-identical-inputs behavior the DB schema's `UniqueConstraint`
    assumes is actually sound at the compute layer.
  - **Stress/fuzz**: all 48 rostered teams paired against a reference team
    (47 pairings) at full `n=50,000` — zero exceptions. A 20x repeated-call
    stress test through the full route (including the cache layer) —
    single consistent `predicted_winner` across every call, slowest call
    under 500ms (cold + warm combined).
- **Acceptance criterion 5 gap — documented, not silently skipped.** Live
  DB idempotency (`kis_simulations` upserting on
  `(match_id, weather_condition, referee_strictness)`) cannot be exercised
  in this dev environment: `backend/app/models.py`'s declarative mapping
  already fails to import on Python 3.9 for *pre-existing* reasons (the
  `Match`/`ModelRun` classes' `X | None` union-type annotations need 3.10+
  — confirmed via `git stash` in the Phase 3 status note, not something
  this work introduced). What Phase 5 *did* verify is the precondition that
  makes the DB-level guarantee meaningful in the first place: `compose()`'s
  determinism (above). Actually exercising the migration needs either a
  Python 3.10+ environment or a real Postgres instance — recommend doing
  that as a pre-deploy smoke test once `USE_DB=true` is actually turned on
  for this feature, not as a blocking item now.
- Full suite: **116/116 passing** (80 through Phase 4 + 35 new in
  `test_kis_regression.py` + 1 stress test added to the existing
  `test_kis_api.py` = 36 net-new).

---

## 0. Why this doc looks the way it does

The request asked for a from-scratch architecture (new DB, new API, new vector
math, new dashboard). Before writing that, I read the actual repo. Verdict:
**KIS is ~60% built already**, just not named that and not exposing the vector
framing. Building the requested design as if greenfield would mean shipping a
second, parallel prediction engine that disagrees with the one already live —
that's a real failure mode, not a hypothetical one (see `knockout_resolve.py`'s
own docstring, which describes fixing exactly this bug once before: the bracket
view and the tournament sim used to disagree until they were unified onto one
shootout/extra-time model).

So this spec is written as **extend, don't replace**. Every section below
states what's reused, what's extended, and what's net-new.

---

## 1. Current State Audit (verified 2026-07-07)

| KIS requirement | Exists today? | Where |
|---|---|---|
| Per-tie Monte Carlo (90&#8242; → ET → shootout) | ✅ Yes | `backend/ml/match_flow.py::simulate_tie()` (629 lines) |
| Extra-time modeling | ✅ Yes | `match_flow._simulate()`, shared `ET_RATE_FACTOR` from `knockout_resolve.py` |
| Shootout modeling (composure/GK/fatigue-weighted) | ✅ Yes | `knockout_resolve.shootout()`, `match_flow._side_profile()` |
| Key player spotlighting | ✅ Yes | `match_flow._key_players()` |
| Weakness / pain-point detection | ✅ Yes (partial) | `match_flow._pain_points()` — GK, fatigue, cold form, penalty fragility, attack rating gap |
| Risk factors | ✅ Yes | `match_flow._risk_factors()` |
| Explainability / reasoning summary | ✅ Yes | `match_flow._explainability()` |
| Turning-point timeline | ✅ Yes | `match_flow._narrative()` — minute-by-minute events |
| 3-scenario projection (Base/Upside/Downside) | ✅ Yes | `match_flow._scenarios()` |
| Hybrid model weighting (stat/form/tactical/weather/psych) | ✅ Yes | `match_flow.MODEL_WEIGHTS` |
| Manager win-rate signal | ✅ Yes (coarse) | `player_condition.MANAGER_WINRATE`, `models.Team.manager_winrate` |
| Goalkeeper quality tiers | ✅ Yes | `player_condition.GK_QUALITY` |
| In-tournament form tracking | ✅ Yes | `tournament_form.py`, `WC2026_PLAYED` |
| Postgres-backed data model | ✅ Partial | `backend/app/models.py` (Team/Player/Match/Prediction/TeamNews/ModelRun/User), `db.py` (SQLAlchemy, DB optional) |
| Live ticker bar (dark broadcast UI) | ✅ Yes | `frontend/components/nav.tsx` — scrolling ticker + 9-tab nav already live |
| Match-flow report UI component | ✅ Yes | `frontend/components/match-flow.tsx::MatchFlowReport` renders exactly this JSON shape |
| **Skill²+Luck²=Performance² vector formalism** | ❌ No | — |
| **Chaos Event injection (2.5σ threshold)** | ❌ No | — |
| **Pressure Score (0–100, single published number)** | ❌ No (inputs exist, not composited into one score) | — |
| **PPDA / pressing intensity mapping** | ❌ No — no tracking data source | — |
| **Formation pivot history** | ❌ No — no tracking data source | — |
| **xA / goal-creation network** | ❌ No — no event-level data source | — |
| **Fullback exploitation zones, space behind CBs** | ❌ No — needs tracking data | — |
| **Substitution timing curves** | ❌ No | — |
| **50,000 iterations at the per-tie level** | ❌ No — currently `N_SIMS = 6000` per tie (tournament-wide bracket sim is 50,000, but that's a different simulation: ~31 ties per run, thousands of runs — not comparable) | `match_flow.py:60` vs `ml/simulate.py` |
| `/api/v1/predict/kis` endpoint | ❌ No | nearest existing: `GET /api/predict`, `GET /api/knockout` |
| KIS Hub nav tab | ❌ No | `nav.tsx` has 9 tabs, none named KIS |
| Pitch-green accent color | ❌ No — current palette is cyan/gold on charcoal (`ink`) | `globals.css` |

**Read this table as the actual scope of "net-new" work.** Everything marked
✅ is reuse — KIS should call into it, not reimplement it.

---

## 2. Data reality check — the hard constraint

The four categories that most differentiate "KIS" from what exists
(PPDA, formation pivots, xA networks, fullback exploitation zones, substitution
timing curves) all require **event-level or player-tracking data this repo does
not have and has no ingest pipeline for.** Today's data sources are:

- `backend/data/raw/results.csv` — score-only historical results (via
  `martj42/international_results`)
- `backend/data/raw/players_kaggle.csv` — season-aggregate player stats
  (goals/assists/minutes per 90, no per-match event data)
- `backend/app/knockout.json` / `match_events.json` — hand-curated goal
  scorers + minute + assist for *played WC2026 matches only* (see the
  Argentina–Egypt ingest from earlier today for the exact shape)
- No possession chains, no defensive-action coordinates, no passing networks,
  no formation/lineup-shape data anywhere in the repo.

**This is not solvable by writing more code.** It requires either (a) a paid
tracking/event-data provider (Opta, StatsBomb, SkillCorner — all have APIs;
none integrated here), or (b) accepting that these metrics are **heuristic
proxies** derived from what we do have (Elo deltas, goals-for/against,
manager win-rate, squad-condition scores), clearly labeled as such in the UI
so they don't read as measured stats.

**Recommendation:** ship KIS categories [1], [4] (partial), [6], [7], [8] as
real (backed by existing engine outputs), and categories [2], [3], [5] as
**proxy-labeled** ("estimated from form/Elo, not tracking data") rather than
faking precision the platform can't back up. This is a decision point — see §10 D1.

---

## 3. Product Identity & Design System

### 3.1 What stays as-is
- Brand: **CAI (ChrisAI)**. No rename.
- Nav shell, live ticker bar, dark theme — `nav.tsx` already implements the
  "continuous live-scrolling ticker + tab nav" requirement. Do not rebuild it;
  extend the `LINKS` array and feed the ticker new KIS-sourced items (chaos
  warnings, pressure-score deltas) alongside the existing news feed.
- Disclaimer language: the app currently has no standing disclaimer footer.
  **Net-new**: add "This platform is an AI-driven probability simulation built
  for entertainment and analytics purposes. Not betting advice." to
  `frontend/app/layout.tsx` footer, sitewide (not just KIS pages) — the
  request implies platform-wide, and it's one line, so scope it site-wide.

### 3.2 What's net-new
- **KIS Hub tab**: add `["/kis", "KIS", "🧠"]` (or similar) to `nav.tsx` LINKS.
- **Palette extension, not replacement**: the current theme is charcoal (`ink`)
  + cyan/gold (see `globals.css` — `chip-cyan`, `chip-gold`, `btn-cyan`,
  `btn-gold`). The request asks for "pitch-green accents." Recommendation:
  add a `pitch` color token (`#1a9c5c`-ish) used *only* for KIS-specific
  Skill-vector elements, keeping cyan for existing "prediction" UI and gold
  for "featured/premium" — this differentiates KIS visually without a site
  reskin. Flagged as decision D2 (§10) since it's a taste call.

---

## 4. KIS Engine — category-by-category build plan

### [1] Team Strategy Journey — mostly reuse
Group velocity, SoS, form, comeback delta, defensive consistency, mentality.
- **Reuse**: `tournament_form._form_record()`, `_form_deltas()` (form, W-D-L,
  goals-for/against, Elo delta already computed per team).
- **Net-new**: "comeback delta" (rate of overturning a losing scoreline) and
  "defensive consistency index" (variance of goals-against across played
  games) aren't computed anywhere. Both are derivable from
  `tournament_form.WC2026_PLAYED` + `match_events.json` with a new function,
  `tournament_stats.comeback_rate(team)` / `defensive_variance(team)`.
- **Effort**: ~4h (pure aggregation over existing data, no new data source).

### [2] Tactical Identity — proxy-only (see §2)
PPDA, formation pivots, pressing height, counterattack speed, possession
ratios, set-piece variance — **all require tracking/event data not present.**
- **Ship as**: a single derived "playing style" descriptor per team, built
  from goals-for/against ratio + Elo + manager tendency (e.g. "high-tempo
  attacking" vs "compact defensive") — explicitly labeled `"basis": "heuristic"`
  in the API response, not `"basis": "tracking_data"`.
- **Out of scope for v1**: PPDA, formation-pivot history, verified pressing
  height. Revisit only if a tracking-data vendor is contracted (separate,
  much larger scope — flagged, not estimated here).

### [3] Manager Intelligence — partial reuse + proxy
- **Reuse**: `player_condition.MANAGER_WINRATE` (48 web-verified coaches),
  `models.Team.manager_winrate`.
- **Net-new, derivable now**: "risk-tolerance index" as a function of a
  manager's historical goals-scored-when-trailing rate — computable from
  `WC2026_PLAYED` + result deltas, no new data needed. ~1 day.
- **Proxy-only / out of scope**: halftime adjustment vectors and substitution
  timing curves need minute-stamped substitution events per historical match.
  `match_events.json` currently only logs goals for played WC2026 games, no
  subs. Extending the ingest schema to capture subs (see the
  Argentina-Egypt-style ingest commits) is feasible going forward for *future*
  matches, but there's no historical base to train "tendency curves" on.
  Ship a single static field (`sub_aggression: "early" | "average" | "late"`)
  sourced from a small curated table, not a learned curve.

### [4] Key Player Impact & Load — mostly reuse
- **Reuse**: `match_flow._key_players()` (likely scorer, penalty decider,
  watchlist), `player_condition` fitness/condition/GK-quality machinery.
- **Reuse**: GK shot-stopping delta — `GK_QUALITY` table already exists;
  "PSxG vs goals allowed" as literally specified needs shot-level xG per save,
  which isn't in the data. Ship the existing `GK_QUALITY` tier score instead,
  relabeled, not a new PSxG computation.
- **Net-new**: "xA / goal-creation network" — out of scope (needs event data,
  see §2). Ship "top assist producers by season aggregate" from
  `players_kaggle.csv` (`assists_per90`) instead — real data, weaker claim.

### [5] Weakness & Pain Point Detection — mostly reuse
- **Reuse directly**: `match_flow._pain_points()` already computes GK
  weakness, fatigue thinning, cold-form runs, penalty fragility, attack-rating
  gaps.
- **Net-new, feasible**: "late-game breakdown risk (75'-90'+)" — derivable
  from `match_events.json` goal-minute data across played matches (rate of
  conceding after minute 75). Small aggregation function, ~half a day.
- **Out of scope**: fullback exploitation zones, space behind CBs, pressing
  traps collapsed — all need tracking data (§2).

### [6] Knockout Pressure Score — net-new, but inputs mostly exist
This is the one category worth building as genuinely new, because the inputs
are already scattered across the engine and just need compositing into one
published 0–100 number.
```
pressure_score = (
    0.30 * knockout_experience_index   # net-new: # of past WC/continental knockout ties played
  + 0.25 * shootout_record             # net-new: historical shootout win rate, curated table
  + 0.20 * composure                   # REUSE: match_flow._side_profile().composure
  + 0.15 * captain_maturity            # net-new: curated (caps + tournament experience of captain)
  + 0.10 * crowd_factor                # net-new: neutral-venue attendance/vocal-support proxy
)
```
`knockout_experience_index` and `shootout_record` need a small curated
lookup table (similar precedent: `MANAGER_WINRATE`, `GK_QUALITY` are both
hand-curated dicts already in `player_condition.py` — same pattern, new table).
**Effort**: ~1.5 days including the curated data entry for 32 teams.

### [7] Extra Time & Penalty Intelligence — reuse, extend one piece
- **Reuse wholesale**: `match_flow` already computes `p_extra_time`,
  `p_shootout`, per-side `pen_conversion`, shootout winner probability.
- **Net-new**: "ranked top-5 penalty execution order" — `_side_profile()`
  computes one team-level `pen_conversion` scalar, not per-player. Extending
  to a per-player ranked list needs individual penalty-taking data, which
  doesn't exist per-player today (only `player_condition`'s aggregate
  `attack_rating`). Ship a heuristic ranking (by `attack_rating` +
  composure proxy) explicitly labeled as modeled, not historical per-player
  penalty conversion (that data doesn't exist).
- **GK penalty save rate**: `GK_QUALITY` is a general tier score, not
  penalty-specific. Ship as-is with a label change, don't fabricate a
  separate stat.

### [8] Unified KIS Output Payload — net-new composition layer
This is genuinely new: a thin wrapper function that calls
`ml_engine.match_flow()` (existing) and layers the vector/chaos/pressure
fields (§5, §6 above) on top into one response shape. See §6 for the exact
schema. **This is the actual "KIS engine" code** — everything above it is
either reuse or a small new aggregation function feeding into it.

---

## 5. Vector Prediction Formalism

The request's mathematical framing — performance as skill plus stochastic
luck — is a **presentation layer on top of the existing ensemble**, not a
replacement for it. The existing `match_flow` engine already computes a
Poisson-sampled regulation score per side; the vector formalism adds an
explicit decomposition of *why* the sampled outcome deviated from the
model's central estimate, for the UI's chaos-narrative feature.

### 5.1 Core equation (as specified)
```
‖P_t‖² = ‖S_t‖² + ‖L_t‖²
```
Applied post-hoc, not as a new simulation mechanism: `S_t` is the model's
central estimate; `L_t` is the residual between a Monte Carlo draw and that
estimate.

### 5.2 Skill decomposition — maps directly onto `MODEL_WEIGHTS`
```
S_t = w1 * tactical_rating + w2 * (1 - fatigue_score_t) + w3 * (1 - pressure_score_t)
```
`match_flow.MODEL_WEIGHTS` already publishes a 5-way blend
(`statistical_elo: 0.40, player_form: 0.25, tactical_matchup: 0.15,
weather_location: 0.10, psychology_penalty: 0.10`). Recommendation: **do not
introduce a second, conflicting weight scheme.** Reproject the existing
5-weight blend into the requested 3-term `S_t` form:
```
S_t = (w_statistical_elo + w_player_form) * (1 - fatigue_score_t)
    + w_tactical_matchup * tactical_rating
    + w_psychology_penalty * (1 - pressure_score_t)
```
`fatigue_score_t` = `1 - h["fatigue_factor"]` (already computed per side in
`_side_profile()`). `pressure_score_t` = the new §4[6] Pressure Score,
inverted. `tactical_rating` = the §4[2] heuristic style score.

### 5.3 Luck decomposition
```
L_t ~ N(μ_bias, σ²_chaos)
```
- `μ_bias`: **net-new, derivable now** — a team's historical
  goals-scored-minus-xG across played matches (over/under-performance
  bias). Needs xG per match, which the engine already estimates
  (`exp_goals_home/away` in `_simulate()`). Compute as a running mean of
  `actual_goals - exp_goals` per team across `WC2026_PLAYED`.
- `σ²_chaos`: match environmental volatility. The request specifies
  weather + referee strictness + fatigue state. `backend/ml/weather.py`
  already exists (check before building — likely already has a weather
  signal feeding the ensemble). Referee-strictness has no data source
  today; ship as a static neutral multiplier (`1.0`) until/unless a referee
  dataset is sourced, flagged as an explicit gap, not silently defaulted.

### 5.4 Chaos Event injection
When a single Monte Carlo draw's `‖L_t‖` exceeds 2.5σ, tag that simulation
run with a `chaos_event`. This is a **narrative/explainability feature**,
not a probability-altering one — it doesn't change `p_home_win` etc., it
flags *which simulated runs* were driven by tail-luck for the timeline UI
("in 3% of simulations, a deflection off [defender] swung the tie"). Cheap
to compute post-hoc on the existing vectorized Poisson draws (`np.where`
on the residual array), no architecture change needed.

### 5.5 Monte Carlo — reconciling "50,000 iterations, minute-by-minute" with the existing engine
**This is the single biggest design conflict in the request and needs a
decision (§10 D3) before Phase 2 starts:**

The request specifies a minute-by-minute stepped simulation (`t = 1..90`,
resampling every minute). The existing `match_flow._simulate()` is fully
**vectorized**: it draws one Poisson total per side per simulation run (not
per-minute), which is why 6,000 runs complete in milliseconds. A literal
minute-by-minute reimplementation for 50,000 runs — 90 sequential Poisson
draws × 50,000 = 4.5M draws per fixture, in a Python loop — would be
orders of magnitude slower and get **less** accurate full-match goal
totals unless the per-minute rate is carefully calibrated to sum to the
same expected total (a well-known pitfall: naive per-minute Poisson
resampling without a shared random seed/rate-conservation trick can drift
from the calibrated match-level `xG`, which is precisely what
`backend/data/processed/calibrator.json` (see `MODEL_DATABASE.md`) was
built to fix).

**Recommendation**: keep the vectorized whole-match Poisson core (proven,
fast, already calibrated against real WC2026 results), and layer momentum/
chaos as a **post-hoc adjustment to the existing minute-stamped narrative
generator** (`match_flow._narrative()` already produces per-minute events
from the aggregate score — extend it to also tag minutes as skill- or
luck-dominant using the §5.4 chaos flag), rather than rebuilding the
simulation loop from scratch. This delivers the requested UI experience
(a "73' — Chaos Event, Luck Dominant" timeline row) without regressing
simulation speed or calibration accuracy.

Bump `N_SIMS` from 6,000 to 50,000 for the KIS-specific endpoint only
(leave the existing bracket-resolution paths at their current N — changing
those changes every cached prediction sitewide, out of scope here). At
6,000 sims the vectorized engine is sub-50ms; 50,000 should still be
comfortably under the 400ms budget the request specifies, but this needs
a benchmark in Phase 2, not an assumption (see acceptance criteria §11).

---

## 6. System Architecture

### 6.1 Database schema (PostgreSQL) — additive, not a rewrite

The repo already has `backend/app/models.py` (SQLAlchemy) with `Team`,
`Player`, `Match`, `Prediction`, `TeamNews`, `ModelRun`, `User`, wired
through `db.py` (DB is optional — the app runs fine on the JSON/snapshot
path without it; Supabase Postgres is already provisioned for the
`feedback` table per `frontend/lib/supabase.ts`). **Do not create a
parallel `teams`/`matches` table set** — that reintroduces the exact
bracket/tournament-sim disagreement bug `knockout_resolve.py` was written
to eliminate. New tables reference the existing ones by ID.

```sql
-- Net-new: one row per KIS run (audit log + cache of the vector decomposition).
-- References the EXISTING matches table — does not duplicate team/match data.
CREATE TABLE kis_simulations (
    id                  SERIAL PRIMARY KEY,
    match_id            INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    home_team           VARCHAR(64) NOT NULL,
    away_team           VARCHAR(64) NOT NULL,
    sim_runs_executed   INTEGER NOT NULL DEFAULT 50000,
    weather_condition   VARCHAR(32) DEFAULT 'Clear',
    referee_strictness  NUMERIC(3,2) DEFAULT 0.50 CHECK (referee_strictness BETWEEN 0 AND 1),

    -- outcome ladder (mirrors match_flow's existing probabilities block)
    p_home_win          NUMERIC(5,4) NOT NULL,
    p_away_win          NUMERIC(5,4) NOT NULL,
    p_draw_90           NUMERIC(5,4) NOT NULL,
    p_extra_time        NUMERIC(5,4) NOT NULL,
    p_shootout           NUMERIC(5,4) NOT NULL,

    -- vector decomposition (net-new)
    home_skill_score     NUMERIC(5,4) NOT NULL,
    away_skill_score     NUMERIC(5,4) NOT NULL,
    home_luck_mu_bias    NUMERIC(5,4) NOT NULL DEFAULT 0,
    away_luck_mu_bias    NUMERIC(5,4) NOT NULL DEFAULT 0,
    luck_sigma_chaos     NUMERIC(5,4) NOT NULL,

    chaos_events         JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{minute, sigma, description}]
    pressure_score_home  SMALLINT CHECK (pressure_score_home BETWEEN 0 AND 100),
    pressure_score_away  SMALLINT CHECK (pressure_score_away BETWEEN 0 AND 100),

    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (match_id, weather_condition, referee_strictness)
);

CREATE INDEX idx_kis_simulations_match ON kis_simulations(match_id);
CREATE INDEX idx_kis_simulations_created ON kis_simulations(created_at DESC);

-- Net-new: curated per-team pressure/experience inputs (same pattern as
-- the existing MANAGER_WINRATE / GK_QUALITY curated dicts in player_condition.py,
-- moved to a table since KIS needs them queryable + auditable).
CREATE TABLE team_pressure_inputs (
    team_name              VARCHAR(64) PRIMARY KEY REFERENCES teams(name),
    knockout_experience     SMALLINT NOT NULL DEFAULT 0,     -- count of past WC/continental KO ties
    shootout_win_rate       NUMERIC(4,3),                    -- historical, nullable if no record
    captain_caps            SMALLINT,
    captain_tournament_apps SMALLINT,
    sub_aggression           VARCHAR(8) CHECK (sub_aggression IN ('early','average','late')),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Design notes:
- `matches(id)` FK assumes the existing `Match` row already exists for the
  fixture (it does — `fixtures.py` + `knockout.json` populate it). If a KIS
  request comes in for a fixture with no `Match` row yet (e.g. a hypothetical
  "what-if" simulator matchup with no scheduled game), `match_id` is
  nullable — **this needs a decision**, see §10 D4.
- `UNIQUE (match_id, weather_condition, referee_strictness)` makes reruns
  with the same inputs idempotent (upsert), matching the existing cache
  pattern in `ml_engine.match_flow()` (Redis-keyed on the same tuple).
- No new `teams`/`players`/`matches` tables. `team_pressure_inputs` extends
  the existing `teams` table 1:1, doesn't duplicate it.

### 6.2 API — extends the existing FastAPI router set

New file: `backend/app/routers/kis.py`, registered in `main.py` alongside
the existing routers (pattern: `backend/app/routers/predictions.py`,
`simulate.py`).

**This code block is the original design-phase sketch, kept for the
rationale — it does NOT match what shipped.** Two things changed post-v1,
both documented in the status notes above: (1) `base` is built via
`services.predict()`, not `ml_engine.predict_match()` directly (the
confidence bug fix); (2) the route is `GET` with query params, not `POST`
with a JSON body (the snapshot-support fix — POST can never be
pre-snapshotted for the backend-free Vercel demo). See
`backend/app/routers/kis.py` for the actual, current implementation.

```python
"""KIS — Knockout Intelligence System. Vector-decomposed match-flow report."""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Literal

from .. import ml_engine

router = APIRouter(prefix="/api/v1/predict", tags=["kis"])


class KISPredictionRequest(BaseModel):
    home_team: str
    away_team: str
    neutral: bool = True
    weather_condition: Literal["Clear", "Rain", "Extreme_Heat"] = "Clear"
    referee_strictness: float = Field(0.5, ge=0.0, le=1.0)


@router.post("/kis")
def generate_kis_prediction(payload: KISPredictionRequest):
    # Reuses the EXISTING engine — does not reimplement match simulation.
    base = ml_engine.predict_match(payload.home_team, payload.away_team,
                                    payload.neutral)
    flow = ml_engine.match_flow(payload.home_team, payload.away_team, base,
                                 knockout=True, neutral=payload.neutral)
    return kis_engine.compose(flow, base, payload)  # net-new: §4[8] composition layer
```

**Sample response** (fields prefixed `//` are net-new; everything else is
`flow`/`base` passed through from the existing engine, confirming this is
additive, not a rewrite):

```json
{
  "predicted_winner": "Argentina",
  "win_probability": 0.612,
  "predicted_score": "2-1",
  "probabilities": {
    "home_win": 0.612, "away_win": 0.388,
    "regulation": {"home": 0.51, "draw": 0.24, "away": 0.25},
    "extra_time": 0.24, "shootout": 0.11,
    "shootout_winner": {"home": 0.58, "away": 0.42, "predicted": "Argentina"}
  },
  "vector_metrics": {
    "//home_skill_score": 0.71, "//away_skill_score": 0.64,
    "//home_luck_mu_bias": 0.08, "//away_luck_mu_bias": -0.03,
    "//luck_sigma_chaos": 0.22,
    "//basis": "S_t reprojected from MODEL_WEIGHTS; L_t from goals-minus-xG bias"
  },
  "//pressure_score": {"Argentina": 78, "Egypt": 61},
  "//chaos_events": [
    {"minute": 73, "sigma": 2.7, "description": "deflection off a defender swings the sim"}
  ],
  "key_players": {"...": "unchanged — reused from match_flow._key_players()"},
  "pain_points": {"...": "unchanged — reused from match_flow._pain_points()"},
  "match_flow": ["...", "unchanged — reused, with chaos-flagged minutes added"],
  "explainability": {"...": "unchanged — reused from match_flow._explainability()"},
  "disclaimer": "This platform is an AI-driven probability simulation built for entertainment and analytics purposes. Not betting advice."
}
```

### 6.3 ML pipeline
The request asks for a gradient-boosted (XGBoost) foundation split feeding
the Monte Carlo. **Check before building**: `backend/ml/xgb_model.py`
already exists in the repo. Phase 1 of KIS work should start by reading
that file to determine whether it's already wired into `ensemble.py` (the
model blend engine) — if so, KIS reuses it as one of the existing ensemble
members feeding `MODEL_WEIGHTS.statistical_elo`; if not, wiring it in is
prerequisite work with its own scope, not a KIS-specific task. **Flagged,
not assumed** — this file needs to be read before Phase 2 estimates are
finalized.

### 6.4 Frontend component hierarchy

**As actually built** (Phase 4 — see the status note above for the two
deliberate deviations: no deep-link route, no ticker feed):
```
frontend/app/kis/
  page.tsx                    — KIS Hub: team-vs-team picker (two <select>s from /api/teams),
                                 POSTs to /api/v1/predict/kis, composes the result

frontend/components/
  nav.tsx                     — EXTENDED: ["/kis", "KIS", "⚡"] added to LINKS
  kis-vector-grid.tsx          — NET-NEW: side-by-side Skill(S)/Luck(L) cards. Skill reuses the
                                 existing `success` green; Luck uses the one new `chaos` (violet)
                                 token — see D2 resolution above, not a "pitch-green" reskin
  kis-chaos-timeline.tsx       — NET-NEW: extends match-flow's event rendering with
                                 skill-dominant/luck-dominant minute tagging (chaos = violet dot)
  kis-pressure-gauge.tsx       — NET-NEW: 0-100 radial gauge per team, "3/5 inputs" disclosure
  match-flow.tsx               — REUSED AS-IS, confirmed unmodified: MatchFlowReport renders the
                                 probability ladder, scenarios, pain points, key players from
                                 compose()'s output with zero changes to this file
```

Data fetching: reuse the existing `frontend/lib/api.ts` `api()` helper
(SWR-based, already used sitewide) — no new fetch layer needed.

---

## 7. Reconciling the request's exact wording with what ships

| Request said | KIS ships |
|---|---|
| "PostgreSQL... teams, matches, player tracking states" | Extends existing `teams`/`matches`/`players` tables; no player *tracking* states (no tracking data source, §2) |
| "gradient-boosted engine (XGBoost)" | Reuses `xgb_model.py` if already wired to `ensemble.py` (verify in Phase 1); does not stand up a second training pipeline |
| "exactly 50,000 iterations" | 50,000 for the KIS endpoint specifically; existing bracket/tournament paths stay at their current N (changing those is a separate, larger-blast-radius change) |
| "minute-by-minute state space trajectory" | Vectorized whole-match core (as today) + minute-tagged narrative overlay — not a literal per-minute resampled loop (§5.5 explains why) |
| "PPDA, formation pivots, xA networks" | Explicitly out of scope for v1 — no data source exists (§2) |

---

## 8. Effort estimate (per component, not a single total)

| Component | Effort | Status |
|---|---|---|
| §4[1] comeback delta + defensive consistency aggregation | 4h | ✅ Done |
| §6.3 XGBoost wiring verification | 0h (already wired) | ✅ Done |
| §4[6] curated knockout-pedigree data entry (32 teams) | 1.5 days | ✅ Done (partial — captain/sub-aggression deferred) |
| §4[3] risk-tolerance index | 1 day | Not started |
| §4[5] late-game breakdown risk aggregation | 4h | ✅ Done |
| §4[6] Pressure Score composite (partial — captain/crowd_factor still excluded) | — | ✅ Done (partial, `basis: "partial_3_of_5_inputs"`) |
| §5 vector decomposition layer (`S_t`/`L_t` reprojection + chaos-event tagging) | 2 days | ✅ Done |
| §5.5 N_SIMS bump to 50,000 + performance benchmark | 0.5 day | ✅ Done — measured p50=3.66ms, p95=4.01ms (target: <400ms) |
| §5.5 narrative chaos-tagging overlay (`narrate_with_chaos()`) | included above | ✅ Done |
| §6.1 ORM models added (2 new tables) | 0.5 day | ✅ Done (models added; live migration deferred to Phase 5 — no DB to migrate against yet) |
| §6.2 `/api/v1/predict/kis` route + `kis_engine.compose()` | 1 day | ✅ Done |
| §6.4 frontend: nav tab + 3 net-new components + KIS Hub page | 2.5 days | ✅ Done (ticker feed correctly deferred, see Phase 4 note; disclaimer found already done) |
| Edge-case tests (§11) | 1.5 days | ✅ Done — 35-test regression + stress suite, all 23 played matches, 47-team fuzz sweep |
| **Remaining** | **None — v1 complete** | DB idempotency (criterion 5) documented as a known gap, not blocking |

---

## 9. Development Roadmap

**Phase 1 — Data Architecture & Extraction Pipeline** ✅ **DONE** (2026-07-07)
- ✅ Read `xgb_model.py` + `ensemble.py` — resolved: already trained, already
  live in the blend. No new ML pipeline work needed.
- ✅ Built `tournament_stats.comeback_rate()`, `defensive_variance()`,
  `late_game_breakdown_rate()` — pure functions over existing
  `WC2026_PLAYED`/`match_events.json` data, no new ingest needed.
- ✅ Curated `KNOCKOUT_PEDIGREE` (knockout experience + shootout record) for
  all 32 R32 teams in `player_condition.py` — same pattern as
  `MANAGER_WINRATE`/`GK_QUALITY`. `captain_maturity`/`sub_aggression`
  explicitly deferred to Phase 3 (no reliable data source yet — see status
  note above), not fabricated.
- **Not done** (moved to Phase 3, since it's additive to the DB work
  already scoped there): `kis_simulations`, `team_pressure_inputs` tables.
  Phase 1 shipped the curated Python data instead of a DB table — cheaper,
  matches the existing `MANAGER_WINRATE`/`GK_QUALITY` precedent, and the
  DB migration in Phase 3 can absorb this table (or supersede it) once the
  captain/sub-aggression inputs are also resolved, rather than migrating
  twice.

**Phase 2 — Vector Engine & Monte Carlo** ✅ **DONE** (2026-07-07)
- ✅ Implemented `S_t`/`L_t` reprojection from existing `MODEL_WEIGHTS`
  (§5.2-5.3) — `kis_engine.skill_score()` / `luck_bias()` / `chaos_sigma()`.
- ✅ Implemented chaos-event tagging on the existing vectorized Poisson draws
  (§5.4) — `kis_engine._tag_chaos_runs()`, Skellam-sigma based, not a fitted
  parameter.
- ✅ Bumped KIS-path `N_SIMS` to 50,000; benchmarked against the 400ms target
  — **measured p50=3.66ms, p95=4.01ms** (real numbers, not an assumption;
  see the Phase 2 status note above for the full methodology).
- ✅ Added `kis_engine.narrate_with_chaos()`, a non-invasive wrapper around
  `match_flow._narrative()` that tags goal events skill-/luck-dominant
  without modifying `_narrative()` or `_simulate()` themselves — confirmed
  `match_flow.simulate_tie()`'s existing output is unaffected.
- **Not done, correctly deferred**: this module is standalone — nothing
  calls `kis_engine.py` yet (no route, no DB write, no frontend). That's
  Phase 3's job.

**Phase 3 — Backend API Layer** ✅ **DONE** (2026-07-07)
- ✅ `backend/app/routers/kis.py` + `kis_engine.compose()`.
- ✅ Registered in `main.py`; wired Redis caching consistent with
  `ml_engine.match_flow()`'s existing cache-key pattern (via `db.py`'s
  graceful in-process fallback when Redis is unreachable — no live Redis
  dependency added).
- ✅ ORM models added to `models.py` (additive, not yet migrated/populated —
  see the Phase 3 status note above for why that's the right stopping point).
- **Not done, correctly deferred to Phase 5**: actually running a live DB
  migration and backfilling `team_pressure_inputs` from `KNOCKOUT_PEDIGREE`.
  Nothing in the running app needs the DB-backed version yet — `kis_engine.py`
  reads `player_condition.knockout_pedigree()` directly, and doing a real
  migration against a live database is exactly the kind of action that needs
  explicit sign-off, not a default "while I'm here" addition.

**Phase 4 — Dashboard UI Integration** ✅ **DONE** (2026-07-07)
- ✅ `nav.tsx`: added KIS tab. **Not done, correctly deferred**: ticker feed
  — needs `news.py` changes outside this spec's data-aggregation scope, not
  a frontend task (see the Phase 4 status note above).
- ✅ `kis-vector-grid.tsx`, `kis-chaos-timeline.tsx`, `kis-pressure-gauge.tsx`.
- ✅ `frontend/app/kis/page.tsx`, composing the net-new components with the
  reused `MatchFlowReport` (unmodified). No separate deep-link route
  (`/kis/[home]/[away]`) — the team-picker IS the entry point; a deep-link
  route can be added later if sharing a specific matchup's URL becomes a
  real request, not speculatively now.
- ✅ Disclaimer: found already done sitewide in `layout.tsx` (see status
  note) — no new footer added.
- ✅ Browser-verified end to end (Playwright, real backend): desktop +
  mobile, a real fixture (Argentina/Switzerland) and a hypothetical D4
  what-if fixture (Brazil/Germany), zero console errors.

**Phase 5 — Edge-Case Validation & Stress Testing** ✅ **DONE** (2026-07-07)
- ✅ Regression run against all 23 already-played WC2026 knockout matches
  (sourced from `tournament_form.WC2026_PLAYED_KNOCKOUT`, not hand-picked)
  — zero divergences from `match_flow`'s output for the same fixture, the
  `knockout_resolve.py`-style consistency check called out in §0.
- ✅ Acceptance criteria 1/2/4/6/7 confirmed. Criterion 3 (400ms budget)
  re-confirmed implicitly — 35 tests including ~70 full-N compose() calls
  run in under 4 seconds total.
- ✅ Edge cases: group-stage mode, referee-strictness extremes, weather
  enum vs. real-venue precedence, zero-pedigree and entirely-unknown teams.
- ✅ Stress: 47-team fuzz sweep at full N (zero exceptions), 20x repeated
  API calls through the cache layer (consistent winner, <500ms worst case).
- **Criterion 5 (DB idempotency) — documented gap, not silently skipped.**
  See the Phase 5 status note above: can't be exercised in this Python 3.9
  dev environment for reasons that predate this work. Determinism at the
  compute layer (the precondition an upsert relies on) IS verified.

---

## 10. Open decisions (D2 still needs a call before Phase 4; D1/D3/D4 resolved)

**D1 — Proxy-labeled metrics.** ✅ **Resolved: ship labeled.** Every
heuristic field in `kis_engine.py` (`tactical_rating`, partial
`pressure_score`) carries an explicit `"basis"` field
(`"heuristic"`/`"partial_3_of_5_inputs"`/etc.) — implemented, not just
recommended.

**D2 — Palette.** ✅ **Resolved: KIS-scoped, and reused what already
existed.** Rather than a new generic `pitch`-green token, Skill (S_t) reuses
the site's existing `success` grass-green (already means "on-model/correct"
sitewide) and only ONE genuinely new token was added — `chaos` (violet,
`#B14EFF`) for Luck. Scoped to the three `kis-*.tsx` components only; no
sitewide reskin, confirmed by screenshot (every other page's palette
unchanged).

**D3 — Simulation architecture.** ✅ **Resolved: vectorized core.**
Implemented and empirically validated — see the Phase 2 status note above
for the measured p50=3.66ms/p95=4.01ms benchmark (100× under the 400ms
target), confirming the vectorized whole-match core was the right call over
a literal per-minute resampled loop.

**D4 — What-if fixtures with no scheduled `Match` row.** ✅ **Resolved by
precedent, not a guess.** `services.predict()` (the existing `/api/predict`)
has zero fixture-scheduling validation — any two team names work. KIS
follows the same pattern: `kis_simulations.match_id` is nullable, and
`POST /api/v1/predict/kis` accepts any two valid (existing) team names,
confirmed via `test_kis_hypothetical_matchup_not_scheduled_still_works`
(Brazil vs Germany, not currently drawn together, returns 200). This means
a future "what-if" simulator (Phase 4+) is possible without a schema change;
whether to actually build that UI is still a product call, separate from
this (now-settled) data-model question.

---

## 11. Acceptance Criteria — final status (2026-07-07)

1. ✅ **Confirmed.** `POST /api/v1/predict/kis` returns a 200 with the
   §6.2 schema for any two valid team names — verified across all 23 played
   knockout matches plus a 47-team fuzz sweep, zero failures.
2. ✅ **Confirmed — with a real fix along the way.** All 23 already-played
   knockout matches checked against `match_flow`'s output: same
   `predicted_winner`, `win_probability` within simulation noise every time.
   BUT the original Phase 3/5 checks compared `kis` against `match_flow`
   using the same (as it turned out, incompletely-built) `base` on both
   sides — internally consistent, not verified against the bracket's own
   prediction path. Checking the actual HTTP route against
   `resolve_bracket()`'s real numbers surfaced a genuine bug (confidence
   deltas up to 22 points — see the "Post-v1 follow-up" status note above),
   now fixed and locked in by
   `test_kis_route_confidence_and_win_prob_match_bracket_within_tolerance`.
   Confidence now matches exactly (0 delta); win_probability within 1.23pp
   (Monte Carlo noise, N=6k vs N=50k).
3. ✅ **Confirmed, measured.** 50,000-iteration KIS simulation: p50=3.66ms,
   p95=4.01ms (Phase 2 benchmark), re-validated implicitly by Phase 5's ~70
   full-N calls completing in under 4 seconds total.
4. ✅ **Confirmed.** Audited in `test_every_heuristic_field_carries_a_basis_label`
   — every heuristic/partial field carries its label; unlisted teams report
   `basis: "default"` rather than a silent guess.
5. ⚠️ **Not verifiable in this environment — documented, not silently
   skipped.** `models.py`'s declarative mapping requires Python 3.10+ for
   reasons that predate this work (see the Phase 3/5 status notes). What
   IS verified: `compose()`'s determinism for identical inputs, and that a
   genuinely different input produces a genuinely different result — the
   precondition the DB-level upsert guarantee depends on. Recommend
   re-testing this specific criterion once `USE_DB=true` is turned on in a
   real (3.10+) environment, before relying on it in production.
6. ✅ **Confirmed, all 23 matches, not spot-checked.** Every already-played
   WC2026 knockout match generates a plausible KIS report (valid
   probability schema, correct team attribution, sane regulation-probability
   sum) — see `test_kis_regression_all_played_knockout_matches`.
7. ✅ **Confirmed, browser-verified.** Playwright screenshot at 390px
   (iPhone-class viewport), a hypothetical Brazil vs Germany matchup — no
   horizontal overflow, cards stack cleanly, zero console errors (Phase 4).

## 12. Testing Plan

| Layer | What | Count |
|---|---|---|
| Unit | `S_t`/`L_t` reprojection math, chaos-event threshold logic, Pressure Score composite | +6 |
| Unit | `tournament_stats.comeback_rate/defensive_variance/late_game_breakdown_rate` | +3 |
| Integration | `POST /api/v1/predict/kis` end-to-end against a live fixture | +2 |
| Integration | Consistency check vs. existing `/api/predict` + `/api/knockout` (acceptance criterion 2) | +2 |
| Regression | All completed WC2026 knockout matches through KIS, spot-checked | +1 (parameterized over the match list) |
| E2E | Navigate to `/kis`, run a simulation, verify vector grid + chaos timeline render | +1 |

## 13. Rollback Plan
- DB: both new tables are purely additive (no FK from existing tables
  pointing *into* them) — drop `kis_simulations` and `team_pressure_inputs`
  to fully revert with zero impact on existing tables.
- API: new router file, additive registration in `main.py` — remove the
  one `include_router` line to fully revert.
- Frontend: new route + new nav entry — remove the `LINKS` entry and the
  `/kis` route to fully revert; `match-flow.tsx` is unmodified (reused,
  not edited), so no risk to the existing knockout/analytics pages.

## 14. Out of Scope (this spec, v1)
- Real player/ball tracking data ingestion (PPDA, formation shapes, xA
  networks) — needs a vendor contract, separate scope entirely.
- Referee-strictness dataset — shipped as a static neutral default (§5.3)
  until a real data source is identified.
- Rebuilding `match_flow.py`'s simulation core — reused as-is.
- Sitewide accent-color reskin (D2) — KIS-scoped palette addition only.
- Per-player historical penalty conversion data — heuristic ranking only (§4[7]).

---

## Files Reference

| File | Change | Status |
|---|---|---|
| `backend/ml/tournament_stats.py` | Added `comeback_rate()`, `defensive_variance()`, `late_game_breakdown_rate()`, `_load_events()` | ✅ Done |
| `backend/ml/player_condition.py` | Added `KNOCKOUT_PEDIGREE`, `KNOCKOUT_PEDIGREE_DEFAULT`, `knockout_pedigree()` | ✅ Done |
| `backend/ml/tests/test_tournament_stats_kis.py` | New — 7 tests | ✅ Done |
| `backend/ml/tests/test_knockout_pedigree_kis.py` | New — 5 tests | ✅ Done |
| `backend/ml/kis_engine.py` | New — §5 vector math (`skill_score`/`luck_bias`/`chaos_sigma`/`_tag_chaos_runs`/`simulate_kis`), §4[2] `tactical_rating`, §4[6] partial `pressure_score`, §5.5 `narrate_with_chaos` (Phase 2); §4[8] `compose()`, `DISCLAIMER`, `WEATHER_CONDITION_SEVERITY` fallback (Phase 3) | ✅ Done — now wired into the live route |
| `backend/ml/tests/test_kis_engine.py` | New — 20 tests, incl. the 50k-run performance regression guard | ✅ Done |
| `backend/app/routers/kis.py` | New — `POST /api/v1/predict/kis`, team-name validation, delegates to `ml_engine.kis()` | ✅ Done |
| `backend/app/ml_engine.py` | Added `kis()` bridge — same Redis-cache pattern as `match_flow()` | ✅ Done |
| `backend/app/models.py` | Added `KISSimulation`, `TeamPressureInput` ORM models (additive, not yet migrated) | ✅ Done |
| `backend/app/main.py` | Registered `kis` router | ✅ Done |
| `backend/tests/test_kis_api.py` | New — 9 integration tests via FastAPI `TestClient`, +1 stress test (Phase 5) = 10 | ✅ Done |
| `backend/tests/test_kis_regression.py` | New (Phase 5) — 35 tests: full 23-match regression, basis audit, edge cases, determinism, 47-team fuzz sweep | ✅ Done |
| `frontend/app/kis/page.tsx` | New — KIS Hub, team picker + result composition | ✅ Done |
| `frontend/components/kis-vector-grid.tsx` | New | ✅ Done |
| `frontend/components/kis-chaos-timeline.tsx` | New | ✅ Done |
| `frontend/components/kis-pressure-gauge.tsx` | New | ✅ Done |
| `frontend/components/nav.tsx` | Extended `LINKS` | ✅ Done (ticker feed deferred — see Phase 4 note) |
| `frontend/tailwind.config.ts` | Added `chaos` color token (D2) | ✅ Done |
| `frontend/app/layout.tsx` | Sitewide disclaimer | Already existed — no change needed |
| `frontend/app/globals.css` | Add `pitch` color token (pending D2) | Not started |

## Related
- `MODEL_DATABASE.md` — canonical doc for the existing ensemble/calibration
  this spec extends
- `HANDOVER.md` §3 (Knockout projection) — the existing bracket-resolution
  engine KIS must stay consistent with
