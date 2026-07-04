"""Monte Carlo simulation of the 2026 World Cup (48-team format).

The group stage is 100% complete and most of the R32 knockout round has
already been played (real results live in app/knockout.json). This sim
resolves the REAL, fixed 32-team bracket ONCE (real_bracket.resolve_r32) —
no group stage is re-simulated — then Monte Carlos only the ties that are
genuinely still undecided: an already-played tie always resolves to its real
winner, an undecided tie is resolved via knockout_resolve.resolve_ko (shared
with the displayed bracket, so title/survival odds agree with the bracket UI
renders). Aggregates per-team probabilities of reaching each stage over
N_SIMS runs.
"""
from __future__ import annotations

import math
import pickle
import shutil
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from config import N_SIMS, PROC, PROJECTED_FIELD
import knockout_resolve
import real_bracket
from model import DCModel
from tournament_form import get_adjusted_elo

try:
    from player_condition import TeamConditionEngine
except Exception:        # optional dependency — sim still runs without it
    TeamConditionEngine = None

# Squad-condition strength in the sim. Matches ensemble.CONDITION_COEF so a
# match sampled here tilts the same way the match-level prediction does.
# Momentum is excluded from the tilt (model.elo is already tournament-patched).
CONDITION_COEF = 1.35


def _condition_tilt(mat: np.ndarray, shift: float) -> np.ndarray:
    """Tilt a score matrix toward the squad-condition favourite.

    Reweights home-win cells (i>j) by e^shift and away-win cells (i<j) by
    e^-shift, leaving draws (i==j) untouched, then renormalizes. This shifts the
    win/draw/loss outcome mass exactly like ensemble._condition_shift while
    preserving the conditional scoreline shape within each outcome.

    (Called from knockout_resolve.build_ko_params, not from this file's own
    run() anymore — kept here since knockout_resolve imports it from us.)
    """
    if abs(shift) < 1e-9:
        return mat
    n, m = mat.shape
    i = np.arange(n)[:, None]
    j = np.arange(m)[None, :]
    w = np.ones_like(mat)
    w[i > j] = math.exp(shift)
    w[i < j] = math.exp(-shift)
    out = mat * w
    return out / out.sum()


_ORDER = ["group", "R32", "R16", "QF", "SF", "Final", "Champion"]


def run(model: DCModel, n_sims: int = N_SIMS, seed: int = 42,
        use_condition: bool = True) -> pd.DataFrame:
    """Run Monte Carlo simulation of the real, partially-decided bracket.

    use_condition: tilt each pairing by squad form/fitness/availability
    (player_condition.py). Defaults on; no-ops if the engine is unavailable.
    """
    r32_pairs, field32 = real_bracket.resolve_r32()
    rows_by_id = {r["id"]: r for r in real_bracket.load_bracket_rows()}

    cond = (TeamConditionEngine() if use_condition and TeamConditionEngine
            else None)
    tag = "with squad condition" if cond else "Elo+DC only"
    print(f"[sim] Pre-computing knockout score grids for the real 32-team "
          f"field ({tag}) ... ", end="", flush=True)
    # Shared knockout-resolution params (KO-suppressed 90' grids + penalty model)
    # so the MC advances undecided ties exactly like the displayed bracket.
    ko_params = knockout_resolve.build_ko_params(model, field32, cond=cond)
    print("done.")

    rng = np.random.default_rng(seed)
    reached = {t: defaultdict(int) for t in field32}

    for i in range(n_sims):
        res = real_bracket.walk_bracket_once(rng, ko_params, r32_pairs, rows_by_id)
        for t, st in res.items():
            hi = _ORDER.index(st)
            for k in range(hi + 1):
                reached[t][_ORDER[k]] += 1
        if (i + 1) % 10000 == 0:
            print(f"[sim] {i+1}/{n_sims} completed ...", flush=True)

    rows = []
    for t in field32:
        row = {"team": t}
        for st in _ORDER:
            row[st] = reached[t][st] / n_sims
        rows.append(row)
    # Teams already eliminated in the real group stage never entered the
    # bracket walk at all — record them explicitly (0% from R32 on) so every
    # PROJECTED_FIELD team still gets a row, matching what every sim_table()
    # consumer already expects.
    field32_set = set(field32)
    for t in PROJECTED_FIELD:
        if t not in field32_set:
            rows.append({"team": t, "group": 1.0, "R32": 0.0, "R16": 0.0,
                        "QF": 0.0, "SF": 0.0, "Final": 0.0, "Champion": 0.0})
    out = pd.DataFrame(rows).sort_values("Champion", ascending=False)
    return out.reset_index(drop=True)


def save_results(table: pd.DataFrame) -> None:
    """Archive the previous sim_results before overwriting (so champion-odds
    impact can be diffed across re-sims), then write the new parquet + json."""
    prev = PROC / "sim_results.json"
    if prev.exists():
        arch = PROC / "sim_archive"
        arch.mkdir(exist_ok=True)
        ts = datetime.fromtimestamp(
            prev.stat().st_mtime, timezone.utc).strftime("%Y%m%dT%H%M%S")
        shutil.copy2(prev, arch / f"sim_results_{ts}.json")
    table.to_parquet(PROC / "sim_results.parquet")
    table.to_json(PROC / "sim_results.json", orient="records")


def main() -> None:
    with open(PROC / "dc_model.pkl", "rb") as f:
        model: DCModel = pickle.load(f)

    # Patch Elo with live WC2026 results (group stage + played knockout ties)
    model.elo = get_adjusted_elo(model.elo)
    print(f"[sim] Elo patched with WC2026 results played so far")

    table = run(model)
    save_results(table)
    print(f"[sim] {N_SIMS} tournaments complete. Title odds (top 15):")
    show = table[["team", "Champion", "Final", "SF"]].head(15).copy()
    show[["Champion", "Final", "SF"]] = (show[["Champion", "Final", "SF"]] * 100).round(1)
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()

