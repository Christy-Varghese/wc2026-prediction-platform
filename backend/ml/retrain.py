"""Model retraining pipeline.

Idempotent, safe to run on a schedule (cron / Celery beat / Admin button):
  1. ingest latest international results
  2. recompute Elo
  3. refit Dixon-Coles
  4. train XGBoost  (skipped if xgboost missing)
  5. train Neural Net (skipped if torch missing)
  6. run Monte Carlo tournament sim
  7. write freshness + accuracy metadata (data/processed/meta.json)

Each step is wrapped so one optional failure (e.g. no torch) doesn't abort
the run. Returns a summary dict the Admin API surfaces.
"""
from __future__ import annotations

import os

# Single-thread the math libraries for the whole retrain process. MUST run
# before numpy/pandas/xgboost import — their OpenMP/BLAS thread pools size at
# import. retrain.run() executes several OpenMP steps (Dixon-Coles scipy refit,
# XGBoost, the sim/backtest subprocesses) back-to-back in one process; on this
# macOS + Python 3.14 box that deadlocks in libomp's join barrier
# (__kmpc_fork_call -> __kmp_join_call -> _pthread_cond_wait, 0% CPU, hung 12h+).
# Capping to 1 thread removes the oversubscription and the deadlock; standalone
# steps run fine single-threaded (DC fit ~3min, sim ~1min). Use setdefault so a
# caller can still override per-launch.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import pickle
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import PROC
import ingest, elo as elo_mod, model as model_mod, xgb_model, nn_model

META = PROC / "meta.json"


def _step(name, fn, log):
    t0 = time.time()
    try:
        fn()
        log[name] = {"ok": True, "secs": round(time.time() - t0, 1)}
    except Exception as e:  # optional members may legitimately fail
        log[name] = {"ok": False, "error": f"{type(e).__name__}: {e}",
                     "secs": round(time.time() - t0, 1)}
        traceback.print_exc()


def run(force_download: bool = True) -> dict:
    log: dict = {"started": datetime.now(timezone.utc).isoformat()}
    state: dict = {}

    def _ingest():
        df = ingest.clean(ingest.download_results(force=force_download))
        df.to_parquet(PROC / "results_clean.parquet")
        state["df"] = df
        log["n_matches"] = len(df)
        log["latest_match"] = str(df["date"].max().date())

    def _players():
        # Non-fatal enrichment: uses cached Kaggle data when available and
        # keeps retrain deterministic if Kaggle/network is unavailable.
        players = ingest.sync_players_dataset(force=False)
        log["n_players"] = int(len(players))

    def _elo():
        ratings, enriched = elo_mod.compute(state["df"])
        enriched.to_parquet(PROC / "results_elo.parquet")
        pd.Series(ratings).sort_values(ascending=False).to_frame("elo") \
            .to_parquet(PROC / "elo_ratings.parquet")
        state["ratings"] = ratings
        state["enriched"] = enriched

    def _dc():
        modern = state["enriched"][state["enriched"].date >= "2010-01-01"]
        m = model_mod.fit(modern, elo=state["ratings"])
        with open(PROC / "dc_model.pkl", "wb") as f:
            pickle.dump(m, f)

    def _xgb():
        xgb_model.train(state["enriched"])

    def _nn():
        nn_model.train(state["enriched"])

    def _sim():
        # Run the Monte Carlo in a *fresh subprocess* (simulate.py __main__).
        # Two reasons: (1) a clean process avoids any BLAS/threadpool state left
        # by the Dixon-Coles scipy.optimize refit + XGBoost OpenMP earlier in
        # this same process; (2) CRITICAL — its stdout must NOT inherit the
        # parent's stdout pipe. simulate.py prints progress hundreds of times;
        # if that inherited pipe's buffer fills while the parent is blocked in
        # wait(), the child blocks on write() and the whole run deadlocks at 0%
        # CPU (observed hanging for hours). Redirect child output to a log file
        # so the pipe can never fill. simulate.main() also applies the
        # tournament-form Elo patch + archives the prior sim_results.
        import subprocess
        import sys
        sim_py = Path(__file__).resolve().parent / "simulate.py"
        sim_log = PROC / "sim_run.log"
        with open(sim_log, "w") as out:
            subprocess.run([sys.executable, "-u", str(sim_py)],
                           cwd=sim_py.parent, check=True, timeout=900,
                           stdout=out, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL)

    def _calibrate():
        # Walk-forward backtest -> per-member metrics + fit calibrator + dynamic
        # weights. Writes member_metrics.json / reliability.json / calibrator.json.
        #
        # Runs backtest.py in a *fresh subprocess*, same rationale as _sim: the
        # walk-forward does 3x Elo compute + 3x Dixon-Coles scipy.optimize refits,
        # whose BLAS calls DEADLOCK at 0% CPU when run in-process after the earlier
        # DC fit + XGBoost (OpenMP) here — observed hanging the whole retrain for
        # ~12h. Single-thread the math libs (kills the oversubscription deadlock;
        # standalone runs at 100% CPU and finishes in minutes) and redirect stdout
        # to a log so the inherited pipe can't fill. backtest.run() writes
        # member_metrics/reliability/calibrator/backtest_summary .json to PROC.
        import os
        import subprocess
        import sys
        bt_py = Path(__file__).resolve().parent / "backtest.py"
        calib_log = PROC / "calib_run.log"
        env = {**os.environ,
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
               "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
               "NUMEXPR_NUM_THREADS": "1"}
        with open(calib_log, "w") as out:
            subprocess.run([sys.executable, "-u", str(bt_py)],
                           cwd=bt_py.parent, check=True, timeout=1200,
                           stdout=out, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, env=env)
        summ = PROC / "backtest_summary.json"
        if summ.exists():
            log["calibration"] = json.loads(summ.read_text())

    _step("ingest", _ingest, log)
    _step("players", _players, log)
    _step("elo", _elo, log)
    _step("dixon_coles", _dc, log)
    _step("xgboost", _xgb, log)
    _step("neural_net", _nn, log)
    _step("simulate", _sim, log)
    _step("calibrate", _calibrate, log)

    log["finished"] = datetime.now(timezone.utc).isoformat()
    META.write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))
    return log


if __name__ == "__main__":
    run()
