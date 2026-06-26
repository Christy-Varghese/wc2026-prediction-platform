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

## Workflow: ingesting new match scores

1. Edit `backend/app/fixtures.py` — change `None, None` to `home_score, away_score` for completed matches
2. Add goal scorers to `backend/data/raw/match_events.json`
3. Add a match report to `backend/data/raw/post_match.json`
4. Run `make ingest-scores` (sim + snapshots)
5. Commit:
   ```
   git add backend/app/fixtures.py backend/data/raw/match_events.json \
           backend/data/raw/post_match.json backend/data/processed/ \
           frontend/public/snapshot/
   git commit -m "data: ingest <date> MD3 results (<groups>)"
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
