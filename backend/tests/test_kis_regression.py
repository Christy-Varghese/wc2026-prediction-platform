"""Phase 5 — KIS regression + stress testing (KIS_SPEC.md §9/§11/§12).

Covers:
  * Acceptance criterion 2/6: every already-played WC2026 knockout match
    (tournament_form.WC2026_PLAYED_KNOCKOUT — the same ledger `simulate.py`
    and `match_flow.py` are keyed on) round-tripped through KIS, spot-checked
    against the existing match_flow engine for consistency, not identity.
  * Acceptance criterion 4: every KIS response carries `basis` labels on its
    heuristic/partial fields — no proxy silently presented as measured data.
  * Acceptance criterion 1: schema shape holds for arbitrary valid team pairs.
  * Edge cases the earlier phases didn't exercise: group-stage (knockout=False)
    mode, extreme referee_strictness, a team with zero curated pedigree, and a
    light fuzz sweep across the full 48-team roster for "does it ever throw".

Runnable via pytest or standalone:
    python backend/tests/test_kis_regression.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))

from app import ml_engine  # noqa: E402
from tournament_form import WC2026_PLAYED_KNOCKOUT  # noqa: E402

PLAYED_PAIRS = [(h, a) for h, a, *_ in WC2026_PLAYED_KNOCKOUT]


# ─────────────────────────────────────────────────────────────────────────────
# Regression: every already-played knockout match, via the real API bridge
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("home,away", PLAYED_PAIRS,
                         ids=[f"{h}-v-{a}" for h, a in PLAYED_PAIRS])
def test_kis_regression_all_played_knockout_matches(home, away):
    base = ml_engine.predict_match(home, away, True)
    flow = ml_engine.match_flow(home, away, base, knockout=True, neutral=True)
    kis = ml_engine.kis(home, away, base, knockout=True, neutral=True)

    # Schema (acceptance criterion 1)
    for key in ("predicted_winner", "win_probability", "probabilities",
               "vector_metrics", "pressure_score", "chaos_events",
               "key_players", "match_flow", "disclaimer"):
        assert key in kis, f"{home} v {away}: missing {key}"

    # Consistency, not identity (acceptance criterion 2) — same predicted
    # winner, probability within Monte Carlo noise (N=6k vs N=50k).
    assert kis["predicted_winner"] == flow["predicted_winner"], \
        f"{home} v {away}: KIS picked {kis['predicted_winner']}, match_flow picked {flow['predicted_winner']}"
    assert abs(kis["win_probability"] - flow["win_probability"]) < 0.05, \
        f"{home} v {away}: win_probability diverged beyond simulation noise"

    # Plausibility, not accuracy (acceptance criterion 6 — retrospective, not
    # held-out): probabilities are valid, teams are the ones asked for.
    assert kis["home_team"] == home and kis["away_team"] == away
    assert 0.0 <= kis["win_probability"] <= 1.0
    pr = kis["probabilities"]
    reg_sum = pr["regulation"]["home"] + pr["regulation"]["draw"] + pr["regulation"]["away"]
    assert abs(reg_sum - 1.0) < 0.01, f"{home} v {away}: regulation probs don't sum to 1 ({reg_sum})"


def test_kis_regression_covers_at_least_all_currently_played_matches():
    # Guards against the parametrized test silently shrinking if
    # WC2026_PLAYED_KNOCKOUT's shape changes — >= (not ==) so ingesting a new
    # result doesn't require bumping a hardcoded count here every time.
    # 24 as of 2026-07-08 (Switzerland-Colombia R16, pens).
    assert len(PLAYED_PAIRS) >= 24


# ─────────────────────────────────────────────────────────────────────────────
# Consistency on UPCOMING (unresolved) bracket ties — "does KIS change any
# results?" This is the answer to that question, enforced as a regression
# test rather than a one-off manual check: knockout_engine.resolve_bracket()
# already cascades the existing engine's predicted winners through every
# remaining round (R16 -> QF -> SF -> 3rd place -> Final), so this compares
# KIS against that live, currently-projected bracket path — not a frozen
# snapshot — and will keep validating as results come in and the bracket
# path shifts.
# ─────────────────────────────────────────────────────────────────────────────
def _upcoming_bracket_ties():
    from app import knockout_engine
    d = knockout_engine.resolve_bracket()
    return [m for m in d["matches"]
            if m.get("home_score") is None and m.get("home_team") and m.get("away_team")]


def test_kis_agrees_with_bracket_on_every_upcoming_tie():
    upcoming = _upcoming_bracket_ties()
    if not upcoming:
        pytest.skip("tournament complete — no unresolved bracket ties left to check")
    disagreements = []
    for m in upcoming:
        h, a = m["home_team"], m["away_team"]
        base = ml_engine.predict_match(h, a, True)
        kis = ml_engine.kis(h, a, base, knockout=True, neutral=True)
        if kis["predicted_winner"] != m["predicted_winner"]:
            disagreements.append(
                f"{m['round']} {h} v {a}: bracket picks {m['predicted_winner']}, "
                f"KIS picks {kis['predicted_winner']}")
    assert not disagreements, "KIS diverges from the projected bracket:\n" + "\n".join(disagreements)


# ─────────────────────────────────────────────────────────────────────────────
# Basis-label audit (acceptance criterion 4)
# ─────────────────────────────────────────────────────────────────────────────
def test_every_heuristic_field_carries_a_basis_label():
    r = ml_engine.kis("Argentina", "Switzerland", None, knockout=True, neutral=True)
    assert "basis" in r["vector_metrics"] and r["vector_metrics"]["basis"]

    from kis_engine import tactical_rating, pressure_score
    tac = tactical_rating("Argentina")
    assert tac["basis"] in ("heuristic", "heuristic_default")
    pr = pressure_score("Argentina", composure=0.5)
    assert pr["basis"] == "partial_3_of_5_inputs"
    assert set(pr["excluded_inputs"]) == {"captain_maturity", "crowd_factor"}


def test_unknown_team_pressure_score_labeled_default_not_a_guess():
    from kis_engine import pressure_score
    r = pressure_score("Definitely Not A Real Team", composure=0.5)
    # score is still computable (renormalized formula degrades gracefully),
    # but the underlying pedigree lookup must be flagged, not silently 0.
    import player_condition as pc
    assert pc.knockout_pedigree("Definitely Not A Real Team")["basis"] == "default"


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────
def test_kis_group_stage_mode_knockout_false():
    # KIS supports non-knockout fixtures too (compose()'s knockout=False path)
    # — a draw is a valid result, no extra-time/shootout section.
    r = ml_engine.kis("Argentina", "Switzerland", None, knockout=False, neutral=True)
    assert r["mode"] == "group"
    assert r["probabilities"]["extra_time"] == 0.0
    assert r["probabilities"]["shootout"] == 0.0
    assert r["predicted_winner"] in ("Argentina", "Switzerland", "Draw")


def test_kis_extreme_referee_strictness_bounds():
    lo = ml_engine.kis("Argentina", "Switzerland", None, referee_strictness=0.0)
    hi = ml_engine.kis("Argentina", "Switzerland", None, referee_strictness=1.0)
    assert lo["vector_metrics"]["luck_sigma_chaos"] < hi["vector_metrics"]["luck_sigma_chaos"]


def test_kis_extreme_heat_no_venue_still_shifts_sigma():
    clear = ml_engine.kis("Argentina", "Switzerland", None, weather_condition="Clear")
    heat = ml_engine.kis("Argentina", "Switzerland", None, weather_condition="Extreme_Heat")
    assert heat["vector_metrics"]["luck_sigma_chaos"] > clear["vector_metrics"]["luck_sigma_chaos"]


def test_kis_real_venue_overrides_weather_enum():
    # A real city's climate signal should win over the weather_condition enum
    # fallback (kis_engine.chaos_sigma()'s documented precedence).
    from kis_engine import chaos_sigma
    r = chaos_sigma("Atlanta", "2026-07-09", weather_condition="Extreme_Heat")
    assert r["weather_basis"] != "caller_enum_no_venue"


def test_kis_compose_deterministic_for_identical_inputs():
    # Underpins acceptance criterion 5 (kis_simulations idempotent on
    # (match_id, weather_condition, referee_strictness)) at the level that's
    # actually testable without a live DB (see the Phase 5 status note in
    # KIS_SPEC.md for why the DB itself can't be exercised here): an upsert
    # only makes sense if identical inputs deterministically produce the same
    # result. Calls kis_engine.compose() directly (bypassing ml_engine's
    # cache) so this proves the underlying seeded RNG is deterministic, not
    # just that the cache returns its own prior value.
    import ensemble
    import kis_engine as kis_mod
    engine = ensemble.get_engine()
    r1 = kis_mod.compose(engine, "France", "Morocco", None, neutral=True, knockout=True,
                         referee_strictness=0.5)
    r2 = kis_mod.compose(engine, "France", "Morocco", None, neutral=True, knockout=True,
                         referee_strictness=0.5)
    assert r1["predicted_score"] == r2["predicted_score"]
    assert r1["win_probability"] == r2["win_probability"]
    assert r1["vector_metrics"] == r2["vector_metrics"]
    assert r1["chaos_events"] == r2["chaos_events"]


def test_kis_compose_different_referee_strictness_is_a_different_input():
    # The other half of the idempotency key: DIFFERENT inputs should be free
    # to produce a different row (not force-collide on the unique constraint).
    import ensemble
    import kis_engine as kis_mod
    engine = ensemble.get_engine()
    lo = kis_mod.compose(engine, "France", "Morocco", None, referee_strictness=0.0)
    hi = kis_mod.compose(engine, "France", "Morocco", None, referee_strictness=1.0)
    assert lo["vector_metrics"]["luck_sigma_chaos"] != hi["vector_metrics"]["luck_sigma_chaos"]


def test_kis_nonexistent_team_full_pipeline_no_crash():
    # Full compose() pipeline (not just the individual helper functions
    # already covered in Phase 2/3) with a team absent from every curated
    # table and the Elo fit — must degrade gracefully via the Elo-fallback
    # default (1500), not throw.
    r = ml_engine.kis("Argentina", "Definitely Not A Real Team XYZ", None, knockout=True)
    assert r["away_team"] == "Definitely Not A Real Team XYZ"
    assert r["vector_metrics"]["away_luck_mu_bias"] is None


def test_kis_team_with_zero_curated_pedigree_does_not_crash():
    # Cape Verde is in KNOCKOUT_PEDIGREE (2, 0, 0) — a real "low but present"
    # curated entry, distinct from a team missing entirely.
    r = ml_engine.kis("Cape Verde", "Argentina", None, knockout=True)
    assert r["pressure_score"]["Cape Verde"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Stress: fuzz sweep across the full 48-team roster — "does it ever throw"
# ─────────────────────────────────────────────────────────────────────────────
def test_kis_fuzz_sweep_all_48_teams_paired_with_reference_no_exceptions():
    from app import fixtures
    all_teams = [t["name"] for t in fixtures.teams()]
    assert len(all_teams) >= 40  # sanity: the full roster loaded
    reference = "Argentina"
    failures = []
    for team in all_teams:
        if team == reference:
            continue
        try:
            r = ml_engine.kis(reference, team, None, knockout=True)
            assert r["home_team"] == reference and r["away_team"] == team
        except Exception as e:  # noqa: BLE001 — collect all failures, not just the first
            failures.append((team, repr(e)))
    assert not failures, f"KIS threw for {len(failures)}/{len(all_teams)-1} pairings: {failures[:5]}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
