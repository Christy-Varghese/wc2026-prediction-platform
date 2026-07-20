# WC2026 — CAI (ChrisAI) Prediction Platform — Session Handover

Date: 2026-07-19 (originally 2026-06-21; updated in place each session — see
§15 for the latest)
Branch: `main` · all work committed + pushed to
`github.com/Christy-Varghese/wc2026-prediction-platform`.

🌐 Live: https://chris-fifaworldcup26-prediction.vercel.app

---

## 1. ML ensemble + calibration — DONE
- Priority reweight: squad form/condition up, location (travel/weather) down.
- Reliability-aware confidence + temperature/vector calibration (identity
  fallback), dynamic inverse-log-loss member weights, synthetic-market de-trust.
  Artifacts in `backend/data/processed/`: `calibrator.json`, `member_metrics.json`,
  `reliability.json`, `feature_coverage.json`.
- **Draw-aware pick:** `predicted_winner` now returns `"Draw"` when draw prob is
  competitive and sides are level (`DRAW_PROB_MIN`/`DRAW_BALANCE` in `ensemble.py`);
  the leaning side is kept as `favored_team`.
- Tests: `backend/tests/` + `backend/ml/tests/` — all pass.

## 2. Manager + goalkeeper signals — DONE
- `MANAGER_WINRATE` (in `ml/player_condition.py`) + `fixtures.MANAGERS` expanded
  to **all 48 web-verified head coaches** (Brazil = Ancelotti, Morocco = Ouahbi).
  Applied as a 0.20 logit term.
- `GK_QUALITY` table (curated keeper-strength tiers, fitness-adjusted) applied as
  a dedicated `GK_COEF = 0.25 × gk_delta` logit term. Surfaced in the knockout
  analysis modal. Weight order: player form 0.55 > GK 0.25 > manager 0.20.
  Direction verified empirically (strong keeper → side harder to beat).

## 3. Knockout projection — DONE (`app/knockout_engine.py`)
- Projects final group standings (real results + predicted remaining games),
  best-8 third-place teams via backtracking slot assignment, resolves R32→Final
  through the predictor (higher win-prob advances). Memoized; `invalidate()` after
  ingest. `/api/knockout` returns resolved teams, per-tie prediction, sim title-%,
  player/manager/GK analysis, and a podium (champion / runner-up / 3rd).
- **Scoreline-consistency fix:** `predicted_score` never shows a loser-win; level
  ties resolve to a draw + `shootout` flag (pens). Frontend: fixed-width columns
  (no name cutoff), title-% chips, podium, click-a-tie analysis modal.

## 4. Post-match analysis (news) — DONE
- `app/match_analytics.py` `post_match_report()` serves curated, news-sourced
  write-ups (`data/raw/post_match.json`: headline, summary, star man, turning
  point, what was missing; sourced ESPN + others) with an auto-generated factual
  fallback for any not-yet-curated completed match.
- Frontend: completed matches show a 📰 Post-Match Analysis card; the old
  "BROADCAST WIDGETS / Activate at kickoff" stubs render only for unplayed games.

## 5. Results ingested (MD1 + MD2 through Jun 21)
- Jun 19: Scotland 0-1 Morocco, Brazil 3-0 Haiti, Paraguay 1-0 Turkey.
- Jun 20: Netherlands 5-1 Sweden, Germany 2-1 Ivory Coast, Ecuador 0-0 Curaçao,
  Tunisia 0-4 Japan.
- Jun 21: Spain 4-0 Saudi Arabia, Belgium 0-0 Iran (Belgium red card 2H),
  Uruguay 2-2 Cape Verde (Araújo 44', Canobbio 45+6' / Pina 21', Varela 61').
  All with web-verified scorers in `match_events.json` + curated `post_match.json`.
  **NZ vs Egypt left unplayed** (`None`) — was still live (NZ 1-0) at ingest time;
  ingest it once final.
- Updated via `fixtures.py` schedule + `data/raw/results.csv` (Python, not sed) +
  `ml/tournament_form.py` `WC2026_PLAYED` (kept in lock-step with fixtures).
- Monte Carlo re-run (`python ml/simulate.py`, N=50000, ~25s). **Projected
  champion unchanged: Argentina ≈31.0%** (Spain 11.0%, England 8.0%, France 7.6%).
  The two Jun 21 draws shift Group G/H standings, not the title favorite.
  Tests pass (calibration 7/7, ensemble 14/14); knockout/services engines verified.
- Jun 22: **Argentina 2-0 Austria** (MD2, Group J) — Messi 38' + 90+5' (now WC
  all-time top scorer; missed a 9th-min penalty). Model had Argentina favoured
  (p_home 0.57, predicted 1-0) — correct winner. Ingested via fixtures.py +
  `WC2026_PLAYED` + `match_events.json`, re-sim + snapshots regenerated. Messi → 5
  tournament goals (Golden Boot leader); Argentina → 2 clean sheets.

## 6. Branding — DONE
- Rebranded all user-facing "AI" → **CAI (ChrisAI)** (nav, titles, "CAI picks",
  "CAI INSIGHTS", "CAI Pre-Match Analysis", layout metadata). Admin page + nav
  button removed (public showcase site).

## 7. Deployment — DONE
- **Frontend → Vercel**, git-integrated (auto-deploys from `main`, root `frontend`),
  custom alias `chris-fifaworldcup26-prediction.vercel.app`, SSO protection off.
- **Backend → Render** ready via `render.yaml` (not yet provisioned — needs the
  owner's dashboard login; see `DEPLOY.md`).
- **Backend-free demo:** `backend/gen_snapshots.py` → static JSON in
  `frontend/public/snapshot/`; `lib/api.ts` falls back to snapshots when the live
  backend is unreachable (uses `no-cache` so new deploys aren't served stale).

---

## 8. Scoreline calibration — DONE
Scorelines ran ~13% low on goals (modeled 2.60 vs actual 3.00 g/match over 39
played games) and clustered too low for blowouts. Fixed:
- **`config.GOAL_SCALE = 1.15`** — multiplicative calibration on Dixon-Coles
  lambdas (`model.py._lambdas`). Implied scale now **1.005** (modeled total/match
  2.98 vs actual 3.00). Re-tune from `backtest.scoreline_calibration()`'s
  `implied_scale` if a future slice drifts.
- **Poisson member de-flattened** (`poisson.py`): supremacy + total now scale with
  the Elo gap (`POISSON_SUP_K`, `POISSON_TOT_GAMMA`) — even 3.10, mismatch 5.45,
  huge 6.09. Was locked at 2.70 total / per-team ≤1.89 (couldn't blow out).
- **rho bounded** (`DC_RHO_BOUNDS`) so an odd training slice can't over-damp high
  scores; DC refit (rho=−0.080, in range).
- Predictions now carry **`total_goals` + `over_2_5`**; list cards expose
  `top_scores` (detail page already rendered the top-3). `backtest.py` gains
  `scoreline_calibration()` (modeled vs actual totals, goal MAE, O/U-2.5 acc).
- Re-sim: champion stable (Argentina 32.3%). O/U-2.5 acc 0.72, goal MAE 0.86.
- **⚠️ Refit DC only via module import** (`import model; model.fit(...)`), never
  `python ml/model.py` directly — the latter pickles the class as
  `__main__.DCModel`, which `ensemble.py` (`from model import DCModel`) can't load.
  `retrain.py` already does it the right way.
- **Bigger accuracy levers still need new data** (not done): real shot-level xG
  feed, confirmed kickoff lineups, real over/under + handicap odds, match-event
  (red cards/pens) data. See the chat analysis for the ranked list.

## 9. Confidence rescale + toss-up flag — DONE (commits a198450, c3d27cd)
- **Why:** raw ensemble confidence (`ensemble._confidence`, 4 ingredients:
  agreement / decisiveness / coverage / reliability) is calibrated but, for
  football's 3-way W/D/L outcome (draws cap a single-match favourite near ~70%),
  realistically lands in a compressed **~27..58** band. The bar never looked
  "full" — a 76%-favourite (Jordan v Argentina) read only 45/100, and group
  coin-flips clustered 31–34. NOT a bug: per-match confidence ≠ tournament
  champion %. Argentina is the sim favourite *and* faces coin-flippy group games.
- **Display rescale** (`ensemble.py`): `CONF_DISPLAY_LO=27 / CONF_DISPLAY_HI=58`
  + `_display_confidence()` — a **monotonic** stretch of `[27,58] → 1..100`,
  applied in `predict()` AFTER the synthetic-market penalty. Order-preserving;
  the underlying probabilities and calibration are UNTOUCHED (presentation only).
  Live range is now 13..61 (e.g. Argentina v Austria 35→26, Norway v France
  31→13, Jordan v Argentina 45→58). Blowouts (host vs minnow) will climb to
  90–99 as they enter the slate.
- **Explanation tone cutoffs** (`ensemble._explain`) re-scaled: High ≥55,
  Moderate ≥26, Low <26 — Low now aligns with the UI toss-up flag.
- **Toss-up flag** (`frontend/components/ui.tsx`): `LOW_CONFIDENCE = 26`
  (= `stretch(35)`), `isLowConfidence()` + `<LowConfidenceTag>` (neutral chip,
  not alarmist). Wired into matches grid + table, knockout bracket + detail, and
  the match-detail prediction engine. Flags any unplayed match below 26 (8 games
  currently). `match_flow.py`'s `conf < 55` "modest confidence" risk still valid
  (= "not High" in the new scale).
- **If you re-tune the spread:** change only `CONF_DISPLAY_LO/HI` in `ensemble.py`,
  move `LOW_CONFIDENCE` (ui.tsx) and the `_explain` cutoffs to match, then
  regenerate snapshots. Stays a pure display transform — never feed the stretched
  value back into calibration/backtest.

## 10. Awards tab — DONE (commits 8ce7c9e + 7636947)
- New `/awards` page + `GET /api/awards` (`app/routers/awards.py` → `ml/awards.py`).
  Nav has a 🏆 Awards tab.
- **Golden Boot** — LIVE/real: `tournament_stats.player_goals()` from the ESPN
  scorer feed; country from `match_events.json`; tiebreak goals→assists→name.
  Auto-updates whenever a result is ingested (e.g. Messi → 5).
- **Golden Glove** — NO per-keeper save feed exists (Sofascore/FotMob bot-blocked).
  Curated web contender list ranked by the app's live team clean sheets + GA.
  Clearly labeled in the UI as clean-sheet based.
- **Golden Ball** — curated media power ranking, enriched with each player's real
  tournament goals. Labeled "media power ranking".
- **Curated source:** `data/raw/awards.json` (web-sourced; git-tracked via a
  `.gitignore` whitelist like `match_events.json`). Holds `golden_glove` +
  `golden_ball` lists, `golden_boot_assists`, `as_of`, `sources`. **Refresh it by
  hand from the web** (same cadence as `post_match.json`); bump `as_of`. The
  Golden Boot needs no manual edit. `ml/awards.py` is presentation-agnostic; the
  router decorates rows with flag + headshot URLs from `fixtures`.

## 11. Knockout prediction strategy overhaul — DONE (Jun 24)
- **Unified resolver** `ml/knockout_resolve.py` — single source of truth for who
  advances a knockout tie (90' → extra time → GK/composure-weighted shootout).
  Both the displayed bracket (`match_flow.simulate_tie`) and the Monte-Carlo
  (`simulate._knockout_winner` → `resolve_ko`) now share its `shootout()` +
  `ET_RATE_FACTOR`. **Before:** the sim flipped an Elo-only coin on a draw, so
  title/survival % disagreed with the bracket's full sim. Fixed by construction.
- **Knockout realism:** `config.KO_GOAL_SCALE = 0.92` suppresses goal rates in
  the knockout path only (via a new `goal_scale` arg on `model._lambdas` /
  `score_matrix`); host-nation home edge restored — `fixtures.host_at_home()` +
  `CITY_COUNTRY` flag a tie non-neutral when USA/Canada/Mexico play in-country
  (`knockout_engine._resolve_tie`, also passed to `match_flow`). NOTE simplification:
  only the HOME-seeded host gets the edge (away-host tie stays neutral to avoid
  re-orienting the bracket).
- **Probabilistic bracket:** `resolve_bracket()` attaches per-tie `survival`
  (each side's MC reach/advance %) + `modal_path: true` + a top-level
  `modal_path_note`. Frontend knockout page shows an "↗ reach <stage> %" line and
  the disclaimer. The modal (deterministic max-prob) bracket can crown a champion
  different from the MC title favourite — that's the modal-path bias, now disclosed.
- **Suspensions/fatigue scaffold (data-gated, no-op):** `ml/availability.py` +
  curated `data/raw/cards.json` (gitignore-whitelisted). 2 yellows ⇒ ban, red ⇒
  ban, yellow slate wiped after QF; `fatigue_factor()` per KO round. **Empty feed
  ⇒ no effect.** To activate: hand-fill `cards.json` from the web once knockout
  games are played, then flip the listed player's squad `status` to `"suspended"`
  in the `player_condition` loader (status already understood by the engine).
- Impact: champion odds spread (Argentina 32.3% → **27.0%** — favourites compress
  in single-elimination, as expected). Tests: `ml/tests/test_knockout_resolve.py`
  11/11; ensemble 14/14, calibration 7/7 still green.
- **Re-tune later** from `backtest.scoreline_calibration()` once real WC2026
  knockout games land (KO_GOAL_SCALE, host edge, fatigue coefficient).

## 12. CAI prediction model — form-led retune + knockout layout (Jun 25)
CAI (ChrisAI) is now an explicit **form-leads** methodology, not just the old
ensemble blend. Thesis: how a team is playing *now* (this year's games + the
group stage, key moments, fitness, momentum, squad/manager/GK) leads the static
pre-WC Elo/DC prior — "there's no going back". Implemented by reweighting the
existing engine (one engine, no parallel model):
- **`ensemble.CONDITION_COEF` 1.75 → 2.45** and `predict()` now applies the
  squad-condition shift with **`include_momentum=True`** — current momentum is in
  the pick, not just the Elo patch.
- **`player_condition.match_condition_adjustment`:** player-form term
  `0.55 → 0.70 * cond_delta`; momentum term `+0.35 * mom_delta` now active in the
  applied shift.
- **`match_flow`:** `FORM_COEF 0.55 → 0.85`, `COND_TILT 0.9 → 1.15` so the
  knockout goal rates lean on current form.
- **Tuning guard:** momentum at 0.35 (not 0.55) — the sweep showed 0.55 flipped one
  played-game pick. **Group-stage success rate held at 39/54 (72%)** under the
  form-led config (baseline was also 39/54); it did not regress. Re-check via the
  one-off loop in `app/news.py`'s accuracy block (re-predicts every played match).
- **CAI 3-scenario knockout projection** (`match_flow._scenarios`): every knockout
  tie now reports **Base / Upside / Downside** with per-scenario xG + result type
  (regulation / pens). Plus **pain points** (`match_flow._pain_points`): each
  side's exploitable weaknesses (keeper, fitness, cold form, penalty fragility,
  blunt attack). Both ride inside the node's `flow` object.
- **Website:** knockout section redesigned — round-sectioned overview
  (`/knockout`, R32→Final) replacing the horizontal bracket; each tie links to a
  dedicated **`/knockout/[id]`** page (new route) showing both teams' road here
  (group games + real scorers + key moments via `knockout_engine.team_journey()`,
  exposed as the payload's top-level `journeys` map), the **CAI 3 scenarios**,
  **pain points**, why-the-winner bars, and the projected game flow. News ticker
  rebranded: "🤖 CAI: current form + momentum led · 3-scenario knockout xG" and
  "🎯 CAI outcome accuracy: 39/54".
- **Re-tune from real KO data:** revisit the form/momentum coefficients +
  `KO_GOAL_SCALE` once knockout games land (first KO Jun 28) via
  `backtest.scoreline_calibration()`.

## 13. R16 results (Jul 4-5) + knockout-stage Elo K-bump + full-ensemble Monte Carlo (Jul 6)
- **Results ingested:** Canada 0-3 Morocco, Paraguay 0-1 France (R16, Jul 4);
  **Brazil 1-2 Norway, Mexico 2-3 England (R16, Jul 5)**. Haaland's late brace
  (79', 90' — both set up by half-time sub Schjelderup) ends Brazil's
  tournament (earliest exit since 1990; Neymar's stoppage-time penalty was
  academic and marked his final Brazil appearance). Bellingham's 98-second
  brace + a Kane penalty — scored minutes after Quansah's 54th-minute red
  card — see 10-man England hold off a Mexico fightback (Quiñones, Jiménez
  pen) to win 3-2 at the Azteca, Mexico's first-ever World Cup loss there.
  Standard ingest workflow each time (`COMMANDS.md`): `knockout.json` +
  `WC2026_PLAYED_KNOCKOUT` (see below) + `match_events.json` +
  `post_match.json`, then re-sim + regenerate snapshots.
- **Knockout-stage Elo K-factor bump** (`ml/tournament_form.py`): single-
  elimination results are higher-signal than group-stage games (no dead
  rubbers, full effort every match), so they should move a team's
  in-tournament rating faster than a group game did. `WC2026_PLAYED` is now
  split into `WC2026_PLAYED_GROUP` (frozen now the group stage is complete;
  `TOURNEY_K = 20`) and `WC2026_PLAYED_KNOCKOUT` (grows as results land;
  `TOURNEY_K_KNOCKOUT = 30`) — `WC2026_PLAYED` itself stays their
  concatenation so every other consumer (`knockout_engine`, `real_bracket`,
  `tournament_stats`, `match_flow`, `backtest`, `tune_condition_coef`) needs
  no change. **New knockout results go in `WC2026_PLAYED_KNOCKOUT`, not
  `WC2026_PLAYED`** — `COMMANDS.md`'s knockout-ingest workflow is updated to
  match. Net effect: Norway's tournament-form Elo bump grows from +23 to
  +33, England's from +15 to +21, Brazil's from +2 to ~0 — flows through
  `ensemble.py`'s Elo member into every live match/knockout prediction.
- **Tournament Monte Carlo now routes through the full ensemble**
  (`ml/simulate.py` + `ml/knockout_resolve.py`). Previously the 50k-run
  title-odds sim scored every knockout pairing with `DCModel.score_matrix`
  directly (Dixon-Coles lambdas + squad-condition tilt only) — Elo, XGBoost,
  market odds, and calibration never entered it, so the K-factor bump above
  (and any future model improvement) moved live match/knockout-page
  predictions but left the Champion/Final/SF percentages completely
  untouched — confirmed byte-for-byte identical `sim_results.json` before
  and after the K-bump alone. Fix: `knockout_resolve.build_ko_params` now
  accepts an `ensemble_engine`; each pairing's DC-generated scoreline grid
  (still `KO_GOAL_SCALE`-suppressed, for a realistic knockout scoreline
  shape/xG) has its aggregate win/draw/loss mass retargeted
  (`_retarget_outcome`, a generalization of the existing `_condition_tilt`
  trick to an arbitrary W/D/L target instead of just a home/away
  exponential tilt) to match `ensemble.predict()`'s full blend.
  `simulate.run()` builds the ensemble once per run and reuses its
  `TeamConditionEngine` for the shootout `pen` inputs instead of
  constructing a second one. Falls back to the old condition-only tilt if
  the ensemble can't load. **Net effect on the current bracket: Argentina
  30.4% → 26.2%, France 15.5% → 23.4%** (market/XGBoost rate France's
  remaining path more favourably than raw DC did), **Morocco 10.2% →
  6.1%**. One-time setup cost of ~992 `ensemble.predict()` calls (every
  possible pairing among the 32-team field, built once, not per
  Monte-Carlo iteration) adds ~1-2s to the ~10s run. All 39 backend/ml
  tests pass throughout.
- **Re-tune later:** revisit `TOURNEY_K_KNOCKOUT` and whether the ensemble
  retarget should also account for `KO_GOAL_SCALE`'s effect on draw
  likelihood (currently `ensemble.predict()` doesn't know a tie is a
  knockout match) once more knockout-stage results land.

## 14. R16 near-complete (Jul 7) + points-based accuracy scoring + doc audit

- **Results ingested:** Portugal 0-1 Spain, United States 1-4 Belgium (R16,
  Jul 6); **Argentina 3-2 Egypt** (R16, Jul 7). R16 now 7 of 8 played —
  only Switzerland vs Colombia (match 96) remains. Re-sim + snapshots
  regenerated after each; podium currently **Argentina champion (28.2%),
  Spain runner-up, France third** (Argentina vs Spain in the projected
  final).
- **Points-based prediction scoring** (commit `dc942e3`): replaced the old
  binary hit/miss accuracy tally with a 5/3/1/0 points ladder (exact score /
  correct winner / draw hit / miss) in `app/services.py::prediction_points`,
  mirrored in `frontend/components/ui.tsx`. Applied everywhere accuracy is
  shown (news ticker, `/matches` panels, knockout-tie verdicts). Current:
  **241/475 pts overall (51%), 71/115 pts knockout (62%)**. Same commit fixed
  a data bug where match 91's (Brazil v Norway) result note credited
  Schjelderup with assisting both Haaland goals but the structured event data
  only had him on one — corrected to match.
- **Doc audit** (this session): refactored file structure to dedupe Elo math
  and stale calibration outcomes (commit `a523d17`); removed `match1-check.md`
  (a stray browser accessibility-tree debug dump, not documentation);
  `MODEL_DATABASE.md` refreshed — added a per-model breakdown (§1.1–1.10, one
  subsection per ensemble member + supporting system), replaced the stale
  R32/R16 tables (previously only 5 of 16 R32 results filled in, no R16 at
  all) with real current results pulled from `tournament_form.WC2026_PLAYED_KNOCKOUT`
  and the `api_knockout.json` snapshot, updated the Golden Boot table and
  accuracy log to the new points system, and fixed a stale `condition_coef`
  in Appendix A (said 2.45, code has 2.0).
- **Scoring revised again, same day — now out of 3, exact-score is a separate
  bonus.** The 5/3/1/0 ladder above lasted a few hours: rebuilt to **3 pts**
  correct winner, **1 pt** actual draw (flat — correctly calling "Draw"
  itself doesn't lift it to 3), **0 pts** wrong winner. Exact-scoreline is no
  longer a scoring tier — it's `prediction_exact_bonus()`, a separate +1
  tally shown alongside the 0-3 score, never summed into it. Caught and fixed
  an ordering bug in first draft of both `services.prediction_points()` and
  `ui.tsx`'s mirror: checking "predicted winner correct" before "actual is a
  draw" let a correctly-called "Draw" prediction score 3 instead of the
  intended flat 1 — the draw check must run first. Updated everywhere:
  backend `news.py` ticker (now `MAX_PTS=3` + a bonus count in the message),
  `/matches` page (dot-chart legend, per-round panels, a new combined
  "Exact score bonus" stat replacing the old group-only one), and
  `/knockout/[id]`'s verdict card. Current: **215/285 pts overall (75%), 15
  exact-score bonuses, 63/69 pts knockout (91%)** — jumped from the 5-point
  system's 51%/62% purely from the rescale (draws no longer eat a full 0-4
  point swing) and from the flat-draw floor.

## 15. Tournament complete — final-stretch interactive experience, Final ingested, Champions page

- **Interactive final-stretch match center** (commit `a37e069` + follow-ups
  `ce5f6bb`/`26532d2`/`d62452f`/`0e02272`): for the tournament's last two
  fixtures only (Third place, Final — gated on `round` + `!played`), added an
  animated `MatchHero` scoreboard, a `ScorePredictor` (user pick vs CAI's,
  localStorage-only), a `HeadToHead` radar comparison (attack/midfield/defence
  derived from squad `impact` scores — extracted the calc out of
  `teams/[name]/page.tsx` into shared `lib/team-attributes.ts`), a Supabase-
  backed `FanVote` (one vote per browser via localStorage; `votes` table,
  RLS: anon can insert+select, not delete/update), curated `AIInsights` cards
  (deliberately **excluding** "expected possession" — no real pre-match
  possession data exists anywhere in this codebase, wasn't worth fabricating),
  and `SharePrediction` (share-intent links + a `next/og`-rendered downloadable
  PNG, no new screenshot dependency). Homepage got a matching "Final Countdown"
  promo with the same live vote widgets embedded.
- **Bracket page animation** (`d62452f`, `0e02272`): confetti burst at the
  center Final node (brighter once actually played vs. still-projected),
  travelling sparks along every connector line once a winner's known/projected
  (extended from R32→R16 only to every round), continuous pulse on winner/gold
  rings. Found and fixed a real Framer Motion bug along the way: animating an
  SVG `r`/`cx`/`cy` attribute via `animate={{...}}` silently fails
  ("Expected length, undefined" in console) unless you also pass a matching
  `initial` — true for a **pre-existing** instance too (the center pulsing
  aura), not just the new code. Fix is just adding the missing `initial`.
- **Supabase project was paused** (free-tier auto-pause) when the `votes`
  feature was first wired up — surfaced as Cloudflare `521`s indistinguishable
  at first glance from a sandbox network issue. Restoring the project +
  re-running the `CREATE TABLE` (the first attempt silently hadn't landed —
  confirmed via `information_schema.tables`, not the Table Editor UI, which
  was misleading) fixed it. **Takeaway:** don't trust "it shows in the Table
  Editor" as confirmation — query `information_schema.tables` directly, and
  after any pause/restore expect a PostgREST schema-cache lag before a
  genuinely-existing table starts resolving via the REST API.
- **Third place ingested:** England 6-4 France (Miami, Jul 18) — Rice/Konsa/
  Saka-brace had England 4-0 up at the break, Mbappé (×2, second his
  record-breaking 22nd World Cup goal) + Barcola dragged France to 4-3, Saka's
  87th-minute penalty completed his hat-trick, Dembélé replied in stoppage
  time, sub Bellingham sealed it 6-4 (commit `c790081`). Advanced stats
  (xG/possession/shots split) weren't confidently sourceable — left unset in
  `actual_stats` rather than estimated, matching this repo's existing honesty
  convention.
- **Final ingested:** Spain 1-0 Argentina (AET, MetLife Stadium, Jul 19) —
  Ferran Torres 106' (Porro → Nico Williams → Torres), Enzo Fernández red
  card 93' (second yellow), Emiliano Martínez 11 saves, Spain 65% possession /
  1.94 xG to 0.17. CAI backed Argentina pre-match at 58.6% but only 11/100
  confidence (toss-up territory, flagged as such at the time) — a genuine
  miss, disclosed honestly on `/champions` rather than glossed over.
- **Every knockout-ingest hardcoded test-count assertion is now dynamic.**
  `test_defensive_variance_sane_for_played_team` (Argentina played-match
  count) broke on *three consecutive* result ingests (6→7→8) before finally
  being rewritten to derive the expected count from `WC2026_PLAYED` itself,
  same pattern its sibling test already used. Also added `pytest.skip` (not a
  failing `assert`) to the two KIS tests that assume "at least one unresolved
  bracket tie exists" — genuinely false now that the tournament's over.
- **Awards refreshed to real FIFA results** (`backend/data/raw/awards.json`):
  Golden Ball — Rodri (1st), Messi (2nd), Mbappé (3rd), replacing a stale
  mid-tournament "power rankings" snapshot that didn't even include Rodri.
  Golden Glove — Unai Simón (live-recomputed from real clean-sheet counts,
  already correctly floats to #1 once the curated note is refreshed, no
  ranking-logic change needed). Added a **new** award category, Best Young
  Player (Pau Cubarsí) — `backend/ml/awards.py::build()`,
  `app/routers/awards.py`, and the frontend `AwardSection` (already generic,
  zero new component code) all extended with one new `best_young_player` key.
  Golden Boot was already correct (Mbappé, 10) — it's fully live-computed from
  `match_events.json`, no manual update needed all tournament.
- **New `/champions` page + `/api/tournament-summary`:** the tournament
  wrap-up capstone — champion celebration hero, final standings podium, all
  four award-winner cards, and CAI's full-tournament accuracy retrospective
  (group vs. knockout breakdown, exact-scoreline count, an explicit honest
  disclosure of the Final miss). The accuracy math itself was refactored out
  of `app/news.py`'s ticker-string logic into a reusable
  `news.compute_accuracy()` so the ticker and the new endpoint share one
  source of truth instead of two computations that could drift.
- **Homepage/nav accuracy pass, once there was truly nothing left "live"
  about:** the homepage's main hero fell back to showing the *already-played*
  Final as a "NEXT MATCH / KICKOFF" card with stale pre-match odds (the
  `nextKo` fallback logic was never written with "tournament over" in mind) —
  now swaps to a champion banner once `round === "Final" && played`. The nav's
  permanently-glowing red "LIVE" pill and per-link live-dot are gated on the
  same `tournamentOver` check now (swaps to a gold "🏆 Champions: Spain" pill
  linking to `/champions`). `/live` already handled this gracefully
  ("All Final ties completed") — no change needed there.
- See `RETROSPECTIVE.md` for an honest end-of-tournament assessment of what
  worked, what didn't, and concrete process/engineering improvements — kept
  separate from this changelog and deliberately not surfaced anywhere on the
  live site.

## Known issues / watch-outs
- **Production `NEXT_PUBLIC_STATIC_ONLY` gap — FIXED Jul 6.** Neither
  `NEXT_PUBLIC_API_URL` nor `NEXT_PUBLIC_STATIC_ONLY` was actually set on
  Vercel Production (despite `DEPLOY.md` documenting `STATIC_ONLY` as
  already set — it wasn't). With both unset, `frontend/lib/api.ts`'s `API`
  defaulted to `http://localhost:8000`, so every page load wasted a failed
  request to that dead address before falling back to the snapshot; during
  that window (and in the pre-hydration SSR shell, which is all a
  `curl`/fast page-read ever sees since these are Client Components) the UI
  showed `components/nav.tsx`'s hardcoded `NEWS_FALLBACK` ticker — content
  frozen from the Round-of-32 era, which made a perfectly correct, correctly
  -aliased deploy look exactly like a stale CDN cache. Fixed: `vercel env
  add NEXT_PUBLIC_STATIC_ONLY production` (value `1`) then `vercel redeploy
  chris-fifaworldcup26-prediction.vercel.app --target production` (editing
  the env var alone does nothing until the next build — `NEXT_PUBLIC_*` is
  inlined at build time). Verified via a clean headless-browser session
  (not `curl` — see below): zero requests to `localhost:8000`, ticker
  matches `/snapshot/api_news.json` immediately. Stays this way until
  Render is actually provisioned (§1 backend deployment below) — full
  root-cause writeup in `DEPLOY.md` → "Stale ticker / wasted localhost
  round-trip".
  **Verifying this class of bug:** don't trust `curl`/a one-shot fetch — it
  will always show the Client Component's pre-hydration fallback text on
  this app. Use a real browser (or headless-browser-with-JS) and wait for
  network-idle before reading page content. Also watch for a stale cached
  JS bundle in whatever browser/tool you're testing with (compare the
  `_next/static/chunks/*` hash in the page source against a fresh `curl` of
  the same page) — a persistent test-browser session can serve cached JS
  from before your fix and make a working fix look broken.
- **`match_flow` regression — FIXED Jun 25.** After §11's unify work, the
  `from knockout_resolve import shootout` collided with a local boolean-mask named
  `shootout` in `_simulate`, so `match_flow` raised on every knockout tie and the
  bracket silently used the no-flow fallback (all nodes had `flow=None`). Aliased
  the import to `run_shootout`; all 32 nodes carry real game-flow again. If flow
  ever goes empty across the board, suspect a name shadow there first.
- **Custom alias auto-follows deploys — FIXED Jun 24.** Permanent fix applied:
  `npx vercel domains add chris-fifaworldcup26-prediction.vercel.app` from repo
  ROOT registered the domain on the project. Verified: a fresh `npx vercel --prod`
  now lists `chris-fifaworldcup26-prediction.vercel.app` in the deploy's alias set
  automatically — no manual `alias set` step anymore. Plain `git push` (Vercel
  git-integration auto-deploy) should now move the live URL too.
  Root cause (was diagnosed Jun 21): the domain was **not in the project's Domains
  list**, so prod deploys only auto-aliased project-owned domains
  (`frontend-five-iota-33.vercel.app`) and the custom alias stayed pinned to an old
  deploy, serving stale data while repo + build were correct.
  **Verify after a deploy:** compare live content vs local, e.g.
  `curl …/snapshot/api_news.json` first item against
  `frontend/public/snapshot/api_news.json`. NOTE: `last-modified`/`age` headers are
  NOT a reliable stale tell — Vercel returns `age 0` even when serving old. Compare
  content, not headers.
  **Fallback (if it ever regresses):** from repo ROOT (not `frontend/`),
  `npx vercel --prod --yes` then
  `npx vercel alias set <printed-hash-url> chris-fifaworldcup26-prediction.vercel.app`.
- **`retrain.py` OpenMP deadlock — FIXED Jun 22 (commit 7df34f4).** Full
  `retrain.run()` used to hang ~12h: running several OpenMP/BLAS steps (Dixon-Coles
  scipy refit, XGBoost, sim, walk-forward backtest) back-to-back in one process
  deadlocked in libomp's join barrier (`__kmpc_fork_call → __kmp_join_call →
  _pthread_cond_wait`, 0% CPU) on this macOS/Python 3.14 box, so the `calibrate`
  step never ran. Fix: cap math-lib threads to 1 for the whole process
  (`OMP/OPENBLAS/MKL/VECLIB/NUMEXPR_NUM_THREADS`, set via `os.environ.setdefault`
  at the TOP of `retrain.py` BEFORE numpy/pandas/xgboost import); `_sim` and
  `_calibrate` also run their heavy scripts in fresh subprocesses (own thread caps,
  stdout→logfile, timeouts). Full run now completes ~14 min, every step ok incl
  calibrate (~476s). If a new heavy step ever re-hangs at 0% CPU, `sample <pid>`
  for `__kmp_join_call` and isolate it in a subprocess.
- `torch` now installed → NN member trains in retrain (was off when absent).
  XGBoost member active.
- `results.csv` is git-ignored (large); the prebuilt artifacts in
  `data/processed/` are committed so the API/snapshots work without a retrain.

## Refresh after new matches
```bash
cd backend && source ../.venv/bin/activate
# 1. add results to fixtures.py + data/raw/results.csv + match_events.json
#    + a post_match.json entry (news analysis)
# 2. rebuild models (or just re-sim if Elo/DC are current):
python ml/simulate.py                 # reliable standalone sim
# 3. regenerate static snapshots + push (Vercel auto-deploys):
python gen_snapshots.py
cd .. && git add -A && git commit -m "data: <date> results" && git push
```

## Environment / repro
```bash
cd /Users/christyvarghese/Documents/ObsidianVault/SecondBrain/wc2026-prediction-platform
source .venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000   # API → :8000/docs
cd ../frontend && npm run dev                              # UI → :3000
# tests:
python backend/tests/test_calibration_engine.py
python backend/ml/tests/test_ensemble_confidence.py
```
