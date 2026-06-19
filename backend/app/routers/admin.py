"""Admin: login, retrain trigger, model status/freshness, dataset upload."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from fastapi import (APIRouter, BackgroundTasks, Depends, File, HTTPException,
                     UploadFile)
from fastapi.security import OAuth2PasswordRequestForm

from .. import auth, cache, ml_engine

router = APIRouter(prefix="/api/admin", tags=["admin"])

ML_DIR = Path(__file__).resolve().parent.parent.parent / "ml"
RAW = ML_DIR.parent / "data" / "raw"


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    if not auth.authenticate(form.username, form.password):
        raise HTTPException(401, "bad credentials")
    return {"access_token": auth.create_token(form.username),
            "token_type": "bearer"}


def _retrain_job():
    sys.path.insert(0, str(ML_DIR))
    import retrain
    retrain.run(force_download=True)
    cache.clear("pred:")        # invalidate cached predictions
    ml_engine.reload_engine()


@router.post("/retrain")
def retrain(bg: BackgroundTasks, user: str = Depends(auth.require_admin)):
    bg.add_task(_retrain_job)
    return {"status": "retraining started", "by": user}


@router.post("/refresh-odds")
def refresh_odds(user: str = Depends(auth.require_admin)):
    sys.path.insert(0, str(ML_DIR))
    import odds
    n = odds.fetch_the_odds_api()
    odds.reload_book()
    cache.clear("pred:")
    ml_engine.reload_engine()
    return {"fixtures_updated": n,
            "source": "the-odds-api" if n else "no ODDS_API_KEY (cache unchanged)"}


@router.post("/refresh-injuries")
def refresh_injuries(user: str = Depends(auth.require_admin)):
    n = ml_engine.refresh_injuries()
    return {"injury_rows": n,
            "source": "api-football" if n else "no INJURY_API_KEY (cache unchanged)"}


@router.post("/refresh-weather")
def refresh_weather(user: str = Depends(auth.require_admin)):
    sys.path.insert(0, str(ML_DIR))
    import weather
    from .. import fixtures
    seen, updated = set(), 0
    for m in fixtures.schedule():
        key = (m["city"], m["kickoff"][:10])
        if key in seen:
            continue
        seen.add(key)
        if weather.fetch_open_meteo(m["city"], m["kickoff"]):
            updated += 1
    cache.clear("pred:")
    ml_engine.reload_engine()
    return {"venues_checked": len(seen), "updated": updated,
            "note": "Open-Meteo only covers ~16 days ahead; future fixtures use climatology"}


@router.get("/status")
def status(user: str = Depends(auth.require_admin)):
    meta = ml_engine.meta()
    proc = ML_DIR.parent / "data" / "processed"
    artifacts = {p.name: round(p.stat().st_size / 1024, 1)
                 for p in proc.glob("*") if p.is_file()}
    return {"freshness": meta, "artifacts_kb": artifacts}


@router.post("/upload")
async def upload(file: UploadFile = File(...),
                 user: str = Depends(auth.require_admin)):
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"saved": str(dest.name), "bytes": dest.stat().st_size}
