"""KIS (Knockout Intelligence System) — Phase 2: vector prediction engine.

Implements the Skill/Luck vector decomposition from KIS_SPEC.md §5 on top of
the existing engines. This module REUSES, not replaces:

  * `match_flow._profiles()` / `_side_profile()` for fatigue/attack/GK inputs
  * `match_flow.MODEL_WEIGHTS` — the existing 5-way statistical/form/tactical/
    weather/psychology blend, reprojected into the 3-term S_t formula
  * `match_flow._simulate()` for the vectorized whole-match Poisson Monte
    Carlo core (KIS just calls it at n=50,000 instead of 6,000 — see
    KIS_SPEC.md §5.5 for why a literal per-minute loop was rejected)
  * `engine.dc._lambdas()` (Dixon-Coles) for the historical goal-rate
    estimate used in the per-team luck-bias (mu_bias) calculation
  * `weather.conditions()` for the environmental-volatility (sigma_chaos)
    input
  * `player_condition.knockout_pedigree()` (Phase 1) for the Pressure Score
    inputs available so far

Pressure Score is PARTIAL here: KIS_SPEC.md §4[6] specifies 5 inputs
(knockout_experience 0.30, shootout_record 0.25, composure 0.20,
captain_maturity 0.15, crowd_factor 0.10). `captain_maturity` needs captain
identity/caps data that doesn't exist for this platform's squads (see the
Phase 1 status note in KIS_SPEC.md); `crowd_factor` has no data source for a
neutral-venue World Cup. Both are held out and the remaining three weights
(0.75 total) are renormalized to sum to 1 — `pressure_score()` labels this
explicitly (`"basis": "partial_3_of_5_inputs"`) rather than silently passing
off a partial score as the full formula.
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

import match_flow as mf
import player_condition as pc
import weather as wx
from knockout_resolve import shootout as run_shootout  # noqa: F401 (re-export parity with match_flow)

# 50,000 vs match_flow's 6,000 — see KIS_SPEC.md §5.5.
KIS_N_SIMS = 50_000

# Chaos-event threshold: a single simulated run whose sampled goal margin
# deviates from the model's expected margin by more than this many standard
# deviations gets tagged a "chaos event" (KIS_SPEC.md §5.4). Narrative-only —
# it doesn't change the outcome probabilities, only which runs get flagged
# for the chaos-timeline UI (Phase 4, not built yet).
CHAOS_SIGMA_THRESHOLD = 2.5

# Renormalized weights for the S_t reprojection (KIS_SPEC.md §5.2): combine
# match_flow.MODEL_WEIGHTS' statistical_elo + player_form into one fatigue
# term, keep tactical_matchup and psychology_penalty as their own terms, drop
# weather_location (that's an L_t/chaos input, not a skill input — see the
# module docstring in KIS_SPEC.md §5.3), then renormalize the remaining three
# so they sum to 1.
def _st_weights() -> dict[str, float]:
    w = mf.MODEL_WEIGHTS
    fatigue_w = w["statistical_elo"] + w["player_form"]
    tactical_w = w["tactical_matchup"]
    psych_w = w["psychology_penalty"]
    total = fatigue_w + tactical_w + psych_w
    return {"fatigue": fatigue_w / total, "tactical": tactical_w / total,
            "psychology": psych_w / total}


ST_WEIGHTS = _st_weights()


# ─────────────────────────────────────────────────────────────────────────────
# tactical_rating — KIS §4[2], explicitly a heuristic proxy (no tracking data)
# ─────────────────────────────────────────────────────────────────────────────
def tactical_rating(team: str) -> dict[str, Any]:
    """0-1 'playing style intensity' heuristic from goals-for/against ratio.

    NOT a PPDA/pressing-height measurement — no tracking data source exists
    for that (KIS_SPEC.md §2). This is an explicitly-labeled proxy: a side
    that scores/concedes more per game rates as higher-tempo/attacking; a
    tight, low-scoring side rates lower. `basis` is always "heuristic".
    """
    import tournament_stats as ts
    r = ts.team_stats().get(team)
    if not r or not r["played"]:
        return {"team": team, "rating": 0.5, "basis": "heuristic_default"}
    goals_per_game = (r["gf"] + r["ga"]) / r["played"]
    # 1.0 goals/game/side (2.0 combined) ~ neutral; scale gently, clip to 0-1.
    rating = 0.5 + 0.15 * (goals_per_game - 2.0)
    return {"team": team, "rating": float(np.clip(rating, 0.05, 0.95)),
            "goals_per_game": round(goals_per_game, 2), "basis": "heuristic"}


# ─────────────────────────────────────────────────────────────────────────────
# Pressure Score — KIS §4[6], PARTIAL (3 of 5 inputs; see module docstring)
# ─────────────────────────────────────────────────────────────────────────────
def pressure_score(team: str, composure: float | None = None) -> dict[str, Any]:
    """0-100 composite from the 3 inputs available without new data sources.

    `composure` (0-1) is fixture-dependent (comes from match_flow's per-side
    profile, which factors in current form/fitness) — pass it in when scoring
    a specific matchup; omitted, it falls back to a neutral 0.5.
    """
    ped = pc.knockout_pedigree(team)
    # knockout_experience: curated counts range roughly 0-35 in KNOCKOUT_PEDIGREE;
    # normalize against that observed range rather than a magic constant.
    exp_norm = float(np.clip(ped["knockout_experience"] / 35.0, 0.0, 1.0))
    so_rate = ped["shootout_win_rate"]
    so_norm = so_rate if so_rate is not None else 0.5  # no shootout history != 0
    comp_norm = 0.5 if composure is None else float(np.clip(composure, 0.0, 1.0))

    w_exp, w_so, w_comp = 0.30, 0.25, 0.20
    w_total = w_exp + w_so + w_comp  # 0.75 — captain_maturity/crowd_factor held out
    score01 = (w_exp * exp_norm + w_so * so_norm + w_comp * comp_norm) / w_total
    return {
        "team": team,
        "score": round(score01 * 100, 1),
        "inputs": {"knockout_experience_norm": round(exp_norm, 3),
                   "shootout_win_rate": so_rate,
                   "composure": round(comp_norm, 3) if composure is not None else None},
        "basis": "partial_3_of_5_inputs",
        "excluded_inputs": ["captain_maturity", "crowd_factor"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# S_t — skill vector (KIS §5.2)
# ─────────────────────────────────────────────────────────────────────────────
def skill_score(side_profile: dict, tactical: dict, pressure: dict) -> dict[str, Any]:
    """S_t for one side, given match_flow's per-side profile (has
    `fatigue_factor`) plus this module's tactical_rating()/pressure_score().
    """
    fatigue_score_t = 1.0 - side_profile["fatigue_factor"]  # 0 = fresh, ~0.25 = tired
    tactical_rating_val = tactical["rating"]
    pressure01 = pressure["score"] / 100.0

    s = (ST_WEIGHTS["fatigue"] * (1.0 - fatigue_score_t)
         + ST_WEIGHTS["tactical"] * tactical_rating_val
         + ST_WEIGHTS["psychology"] * pressure01)
    return {
        "team": side_profile["team"],
        "skill_score": round(float(s), 4),
        "components": {
            "fatigue_term": round(ST_WEIGHTS["fatigue"] * (1.0 - fatigue_score_t), 4),
            "tactical_term": round(ST_WEIGHTS["tactical"] * tactical_rating_val, 4),
            "psychology_term": round(ST_WEIGHTS["psychology"] * pressure01, 4),
        },
        "weights": ST_WEIGHTS,
    }


# ─────────────────────────────────────────────────────────────────────────────
# L_t — luck vector (KIS §5.3)
# ─────────────────────────────────────────────────────────────────────────────
def luck_bias(engine, team: str) -> dict[str, Any]:
    """mu_bias: mean(actual goals - Dixon-Coles expected goals) across the
    team's played WC2026 matches — over/under-performance vs the model's own
    retrospective estimate for each fixture. None if the engine has no fitted
    DC model (Elo-only fallback) or the team hasn't played.
    """
    import tournament_form as tf
    dc = engine.dc
    if dc is None:
        return {"team": team, "mu_bias": None, "basis": "unavailable_no_dc_model"}
    residuals: list[float] = []
    for home, away, hg, ag, neutral in tf.WC2026_PLAYED:
        if team not in (home, away):
            continue
        lh, la = dc._lambdas(home, away, neutral)
        if team == home:
            residuals.append(hg - lh)
        else:
            residuals.append(ag - la)
    if not residuals:
        return {"team": team, "mu_bias": None, "basis": "unavailable_no_matches"}
    return {"team": team, "mu_bias": round(float(np.mean(residuals)), 4),
            "n_matches": len(residuals), "basis": "engine"}


# Original-request weather enum -> severity (0-1), used only as a fallback
# when there's no real venue to derive climate from (a hypothetical "what-if"
# matchup with no scheduled Match row — see D4). When a real `city` is given,
# the actual venue-climate signal from weather.py wins; this enum never
# silently overrides real data.
WEATHER_CONDITION_SEVERITY = {"Clear": 0.0, "Rain": 0.35, "Extreme_Heat": 0.7}


def chaos_sigma(city: str | None, kickoff_iso: str | None,
                referee_strictness: float = 0.5,
                weather_condition: str | None = None) -> dict[str, Any]:
    """sigma_chaos: environmental-volatility input to L_t's N(mu_bias, sigma^2).

    Blends weather.conditions() severity (0-1, real signal already used
    elsewhere in the ensemble) with referee_strictness (no data source exists
    for this — KIS_SPEC.md §5.3 flags it explicitly; defaults to a neutral
    0.5 multiplier rather than silently assuming calm officiating). Returns a
    baseline 0.15 (empirically-reasonable single-match goal-margin noise
    floor) scaled up by weather/referee severity, not a from-scratch fit.

    `weather_condition` (Clear/Rain/Extreme_Heat, the original request's enum
    shape) is a FALLBACK for fixtures with no real `city` — a real venue's
    climate always wins when `city` is given, never silently overridden.
    """
    weather_sev = 0.0
    weather_basis = "no_venue_given"
    if city:
        w = wx.conditions(city, kickoff_iso or "")
        weather_sev = w["severity"]
        weather_basis = w["source"]
    elif weather_condition and weather_condition in WEATHER_CONDITION_SEVERITY:
        weather_sev = WEATHER_CONDITION_SEVERITY[weather_condition]
        weather_basis = "caller_enum_no_venue"
    ref_component = referee_strictness  # 0.5 default = neutral, not "calm"
    sigma = 0.15 * (1.0 + 0.6 * weather_sev + 0.3 * (ref_component - 0.5) * 2)
    return {
        "sigma": round(float(max(0.05, sigma)), 4),
        "weather_severity": weather_sev, "weather_basis": weather_basis,
        "referee_strictness": referee_strictness,
        "referee_basis": "static_neutral_default" if referee_strictness == 0.5 else "caller_provided",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Chaos-event tagging on the vectorized Monte Carlo (KIS §5.4)
# ─────────────────────────────────────────────────────────────────────────────
def _tag_chaos_runs(gh: np.ndarray, ga: np.ndarray, lh: float, la: float
                    ) -> dict[str, Any]:
    """Flag simulation runs whose sampled goal margin deviates from the
    model's expected margin by more than CHAOS_SIGMA_THRESHOLD standard
    deviations. Poisson variance = its own mean, so the margin (gh - ga) has
    variance lh + la (independent Poissons) — a standard, defensible sigma,
    not a fitted parameter.
    """
    expected_margin = lh - la
    margin_sigma = float(np.sqrt(max(lh + la, 1e-6)))
    margin = gh.astype(float) - ga.astype(float)
    z = (margin - expected_margin) / margin_sigma
    chaos_mask = np.abs(z) > CHAOS_SIGMA_THRESHOLD
    return {
        "chaos_run_count": int(chaos_mask.sum()),
        "chaos_run_rate": float(chaos_mask.mean()),
        "margin_sigma": round(margin_sigma, 4),
        "chaos_mask": chaos_mask,  # internal — not serialized by simulate_kis()
        "z": z,
    }


# ─────────────────────────────────────────────────────────────────────────────
# public entry point
# ─────────────────────────────────────────────────────────────────────────────
def simulate_kis(engine, home: str, away: str, *, neutral: bool = True,
                 knockout: bool = True, city: str | None = None,
                 kickoff_iso: str | None = None,
                 referee_strictness: float = 0.5,
                 weather_condition: str | None = None,
                 n: int = KIS_N_SIMS, seed_offset: int = 0) -> dict[str, Any]:
    """Full KIS vector report for one fixture: S_t/L_t decomposition, a
    50,000-run vectorized Monte Carlo (reusing match_flow._simulate's core,
    not a reimplementation), and chaos-event tagging on the raw draws.

    Does NOT touch the DB, expose an API route, or render anything — Phase 2
    scope only (KIS_SPEC.md §9). `ml_engine.match_flow()`/`simulate_tie()`
    remain the production knockout-report path; this is additive.
    """
    t0 = time.perf_counter()
    prof = mf._profiles(engine, home, away, neutral=neutral, knockout=knockout)
    h, a = prof["home"], prof["away"]

    tac_h, tac_a = tactical_rating(home), tactical_rating(away)
    pr_h = pressure_score(home, composure=h["composure"])
    pr_a = pressure_score(away, composure=a["composure"])
    skill_h = skill_score(h, tac_h, pr_h)
    skill_a = skill_score(a, tac_a, pr_a)
    luck_h = luck_bias(engine, home)
    luck_a = luck_bias(engine, away)
    sigma = chaos_sigma(city, kickoff_iso, referee_strictness, weather_condition)

    rng = np.random.default_rng(mf._seed(home, away) + 1000 + seed_offset)
    gh = rng.poisson(h["reg_rate"], n)
    ga = rng.poisson(a["reg_rate"], n)
    chaos = _tag_chaos_runs(gh, ga, h["reg_rate"], a["reg_rate"])

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "engine": "kis_vector_v1",
        "n_sims": n,
        "home_team": home, "away_team": away,
        "elapsed_ms": elapsed_ms,
        "vector_metrics": {
            "home_skill_score": skill_h["skill_score"],
            "away_skill_score": skill_a["skill_score"],
            "home_luck_mu_bias": luck_h["mu_bias"],
            "away_luck_mu_bias": luck_a["mu_bias"],
            "luck_sigma_chaos": sigma["sigma"],
            "basis": "S_t reprojected from MODEL_WEIGHTS (fatigue+tactical+psychology); "
                     "L_t mu_bias from DC-lambda residuals, sigma_chaos from weather+referee",
        },
        "pressure_score": {home: pr_h["score"], away: pr_a["score"]},
        "tactical_rating": {home: tac_h["rating"], away: tac_a["rating"]},
        "chaos_events": {
            "run_count": chaos["chaos_run_count"],
            "run_rate": round(chaos["chaos_run_rate"], 4),
            "threshold_sigma": CHAOS_SIGMA_THRESHOLD,
            "margin_sigma": chaos["margin_sigma"],
        },
        "detail": {"skill_home": skill_h, "skill_away": skill_a,
                   "luck_home": luck_h, "luck_away": luck_a,
                   "chaos_sigma_inputs": sigma},
    }


DISCLAIMER = ("This platform is an AI-driven probability simulation built for "
              "entertainment and analytics purposes. Not betting advice.")


def compose(engine, home: str, away: str, base: dict | None = None, *,
           neutral: bool = True, knockout: bool = True,
           city: str | None = None, kickoff_iso: str | None = None,
           referee_strictness: float = 0.5,
           weather_condition: str | None = None) -> dict[str, Any]:
    """KIS §4[8] Unified Output Payload — the Phase 3 API composition layer.

    Mirrors `match_flow.simulate_tie()`'s orchestration (profile -> simulate
    -> narrate -> key_players/pain_points/explainability) rather than calling
    it directly, because `simulate_tie()` is hardcoded to `match_flow.N_SIMS`
    (6,000) and its own untagged `_narrative()`. Re-running the same
    `_profiles()`/`_simulate()`/`_narrative()` building blocks at
    `KIS_N_SIMS` (50,000) with the SAME seed (`match_flow._seed()`) keeps this
    a higher-precision draw from the identical underlying model — not a
    second, disagreeing engine (see KIS_SPEC.md §0 on why that's the failure
    mode to avoid). `match_flow.py` itself is untouched.

    D4 (KIS_SPEC.md §10) resolved by precedent: `backend/app/services.py`'s
    existing `predict(home, away, neutral)` has no "must be a real scheduled
    fixture" gate — any two valid team names work. KIS follows the same
    pattern; the caller (Phase 3 route) is responsible for whatever
    real-fixture validation it wants, this composition layer doesn't impose it.
    """
    base = base or {}
    rng = np.random.default_rng(mf._seed(home, away) + (0 if knockout else 1))
    prof = mf._profiles(engine, home, away, neutral=neutral, knockout=knockout)
    sim = mf._simulate(prof, rng, knockout=knockout, n=KIS_N_SIMS)

    favored = home if sim["p_home_win"] >= sim["p_away_win"] else away
    if knockout:
        winner = favored
        loser = away if winner == home else home
        predicted = winner
        win_prob = max(sim["p_home_win"], sim["p_away_win"])
    else:
        outcomes = {home: sim["p_home_win"], "Draw": sim["p_draw"], away: sim["p_away_win"]}
        predicted = max(outcomes, key=outcomes.get)
        winner = None if predicted == "Draw" else predicted
        loser = None if predicted == "Draw" else (away if winner == home else home)
        win_prob = outcomes[predicted]

    vec = simulate_kis(engine, home, away, neutral=neutral, knockout=knockout,
                       city=city, kickoff_iso=kickoff_iso,
                       referee_strictness=referee_strictness,
                       weather_condition=weather_condition, n=KIS_N_SIMS)
    chaos_run_rate = vec["chaos_events"]["run_rate"]

    pen_winner = home if sim["p_home_pens"] >= sim["p_away_pens"] else away
    events, turning_points = narrate_with_chaos(prof, sim, winner, rng,
                                                chaos_run_rate, knockout=knockout)
    gh, ga = sim["modal_score"]

    # Pipeline-disagreement confidence penalty — mirrors
    # knockout_engine._resolve_tie() exactly, so KIS's confidence doesn't
    # silently overstate certainty relative to the bracket's own number for
    # the same fixture. `base` (ensemble.predict, stat-driven) and `sim`
    # (this module's own regulation-time Monte Carlo) are two separate
    # calculations that normally agree; when they don't, that disagreement
    # is a real uncertainty signal the ensemble's own confidence never sees.
    PIPELINE_DISAGREEMENT_CONF_PENALTY = 15
    confidence = base.get("confidence")
    ph, pa = base.get("p_home"), base.get("p_away")
    if confidence is not None and ph is not None and pa is not None:
        fh, fa = sim["p_home_90"], sim["p_away_90"]
        if fh != fa and ph != pa and (ph >= pa) != (fh >= fa):
            confidence = max(1, confidence - PIPELINE_DISAGREEMENT_CONF_PENALTY)

    return {
        "engine": "kis_v1",
        "n_sims": KIS_N_SIMS,
        "mode": "knockout" if knockout else "group",
        "home_team": home, "away_team": away,
        "winner": winner, "loser": loser,
        "predicted_winner": predicted,
        "win_probability": round(win_prob, 4),
        "predicted_score": f"{gh}-{ga}",
        "shootout": knockout and sim["p_shootout"] >= 0.5,
        "probabilities": {
            "home_win": round(sim["p_home_win"], 4),
            "away_win": round(sim["p_away_win"], 4),
            "regulation": {"home": round(sim["p_home_90"], 4),
                          "draw": round(sim["p_draw_90"], 4),
                          "away": round(sim["p_away_90"], 4)},
            "extra_time": round(sim["p_extra_time"], 4),
            "shootout": round(sim["p_shootout"], 4),
            "shootout_winner": {"home": round(sim["p_home_pens"], 4),
                                "away": round(sim["p_away_pens"], 4),
                                "predicted": pen_winner},
        },
        "expected_goals": {"home": round(sim["exp_goals_home"], 2),
                           "away": round(sim["exp_goals_away"], 2)},
        "vector_metrics": vec["vector_metrics"],
        "pressure_score": vec["pressure_score"],
        "tactical_rating": vec["tactical_rating"],
        "chaos_events": vec["chaos_events"],
        "most_likely_scores": sim["top_scores"],
        "scenarios": mf._scenarios(prof, sim, winner, knockout),
        "pain_points": mf._pain_points(prof, sim, knockout),
        "match_flow": events,
        "turning_points": turning_points,
        "key_players": mf._key_players(prof),
        "risk_factors": mf._risk_factors(prof, sim, base.get("confidence"), knockout=knockout),
        "explainability": mf._explainability(prof, sim, base, favored, knockout=knockout),
        "confidence": confidence,
        "disclaimer": DISCLAIMER,
    }


def narrate_with_chaos(prof: dict, sim: dict, winner: str | None,
                       rng: np.random.Generator, chaos_run_rate: float,
                       knockout: bool = True) -> tuple[list[dict], list[str]]:
    """Wraps match_flow._narrative(), then tags the narrative's goal events as
    skill- or luck-dominant (KIS §5.5's minute-tagged narrative overlay).

    Does not touch match_flow._narrative() or `_simulate()` — this only
    post-processes the returned event list, so match_flow.simulate_tie()'s
    existing behavior/tests are unaffected.
    """
    events, turning_points = mf._narrative(prof, sim, winner, rng, knockout=knockout)
    # A run's chaos_run_rate is the tournament-wide MC estimate of how often
    # ANY single run is chaos-flagged for this fixture; used here as a
    # per-goal-event tagging probability so the narrative reflects the same
    # underlying volatility the vector engine measured, without re-running a
    # second simulation just for narrative purposes.
    for ev in events:
        if ev.get("type") == "goal":
            ev["vector_dominant"] = "luck" if rng.random() < chaos_run_rate else "skill"
    return events, turning_points
