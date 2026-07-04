# WC2026 Platform — Command Reference

Run all commands from the **project root** (`wc2026-prediction-platform/`).

---

## Quick reference

| What you want to do | Command |
|---|---|
| Open website in browser | `make open-site` |
| Start frontend dev server | `make dev-frontend` |
| Start backend API server | `make dev-backend` |
| Start both servers | `make dev` |
| Add new scores → update sim + snapshots | `make ingest-scores` |
| Re-run simulation only | `make sim` |
| Regenerate snapshots only | `make snapshots` |
| Run all tests | `make test` |
| Validate live API | `make validate` |
| Install all deps | `make install` |

---

## Workflow: ingesting new group-stage match scores

1. Edit `backend/app/fixtures.py` — change `None, None` to `home_score, away_score` for completed matches
2. Add the same `(home, away, hs, as, neutral)` row to `WC2026_PLAYED` in
   `backend/ml/tournament_form.py` — **do not skip this.** It's what patches
   the Elo used to predict every remaining match; skipping it silently lets
   the model fall behind reality (this happened for 10 R32 results before
   being caught and backfilled).
3. Add goal scorers to `backend/data/raw/match_events.json`
4. Add a match report to `backend/data/raw/post_match.json`
5. Run `make ingest-scores` (sim + snapshots)
6. Commit:
   ```
   git add backend/app/fixtures.py backend/ml/tournament_form.py \
           backend/data/raw/match_events.json backend/data/raw/post_match.json \
           backend/data/processed/ frontend/public/snapshot/
   git commit -m "data: ingest <date> MD3 results (<groups>)"
   ```

---

## Workflow: ingesting new knockout-stage results

1. Edit `backend/app/knockout.json` — fill in `home_score`/`away_score`
   (+ `pen_home`/`pen_away` on a shootout) and `actual_events`/`actual_stats`
   for the played match id.
2. Add the same `(home, away, hs, as, neutral)` row to `WC2026_PLAYED` in
   `backend/ml/tournament_form.py` (a shootout is recorded as its 90'/ET
   score, i.e. a draw — the shootout itself isn't modeled in Elo). This
   feeds both the retrospective Elo patch AND `backend/ml/real_bracket.py`'s
   real-bracket resolution, so the simulator/knockout pages both reflect the
   result immediately.
3. Add the scorer(s) to `backend/data/raw/match_events.json` (own goals go
   under the *benefiting* team's array, `"type": "own goal"`, `player` =
   the scorer).
4. Run `make ingest-scores` (sim + snapshots).
5. Commit:
   ```
   git add backend/app/knockout.json backend/ml/tournament_form.py \
           backend/data/raw/match_events.json backend/data/processed/ \
           frontend/public/snapshot/
   git commit -m "data: ingest <team> <score> <team> (<round>, <date>)"
   ```

---

## Individual commands (without Make)

### Frontend
```bash
cd frontend && npm run dev          # dev server on :3000
cd frontend && npm run build        # production build
cd frontend && npm run lint         # lint
```

### Backend API
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

### Simulation
```bash
cd backend/ml && python3 simulate.py
```

### Snapshot generation
```bash
cd backend && python3 gen_snapshots.py
```

### Tests
```bash
cd backend && python3 -m pytest tests/ -q
cd backend/ml && python3 -m pytest tests/ -q
```

### API validation (backend must be running on :8000)
```bash
cd backend && python3 validate_api.py
```

---

## Useful one-liners

```bash
# Check current champion probabilities
python3 -c "
import json
data = json.load(open('backend/data/processed/sim_results.json'))
for r in sorted(data, key=lambda x: x['Champion'], reverse=True)[:10]:
    print(f\"{r['team']:20s} {r['Champion']*100:.1f}%\")
"

# Check which matches still have None scores
python3 -c "
import sys; sys.path.insert(0, 'backend')
from app.fixtures import MD23
for m in MD23:
    if m[5] is None:
        print(m)
"

# Kill any process on port 3000 or 8000
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:8000 | xargs kill -9 2>/dev/null
```
