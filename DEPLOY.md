# Deploy — Vercel (frontend) + Render (backend)

The app is full-stack: a **Next.js** frontend and a **FastAPI** backend with
pre-built ML artifacts (committed under `backend/data/`, so no retrain is needed
to boot). Deploy the backend first, then point the frontend at it.

## 1. Backend → Render

1. Go to <https://dashboard.render.com> → **New ▸ Blueprint**.
2. Connect GitHub and pick `Christy-Varghese/wc2026-prediction-platform`.
   Render reads `render.yaml` and provisions the `wc2026-api` web service
   (free plan, root `backend/`, no database).
3. Deploy. Wait for it to go live, then confirm:
   `https://wc2026-api.onrender.com/api/health` → `{"ok": true, ...}`.
   (Your URL may differ — copy the real one from the Render dashboard.)

> Free Render services sleep after ~15 min idle; the first request then takes
> ~30–60 s to wake. Fine for a demo.

## 2. Frontend → Vercel

1. Go to <https://vercel.com/new> → import the same GitHub repo.
2. **Root Directory:** `frontend`. Framework preset: **Next.js** (auto).
3. **Environment Variable:**
   `NEXT_PUBLIC_API_URL = https://wc2026-api.onrender.com` (your Render URL).
4. Deploy. Vercel gives you a URL like
   `https://wc2026-prediction-platform.vercel.app`.

## 3. Wire CORS

Back in Render → `wc2026-api` → **Environment** → set
`CORS_ORIGINS` to your real Vercel domain (comma-separated, no trailing slash),
e.g. `https://wc2026-prediction-platform.vercel.app,http://localhost:3000`,
then **Save** (auto-redeploys).

## 4. Verify

Open the Vercel URL → `/knockout`. Bracket, podium, title-% and the analysis
modal should all load from the live backend.

## Auto-deploy

Both platforms **build** on every push to `main` once connected.

## Production alias / promotion ⚠️

A push to `main` triggers a Vercel build (visible as a green "Vercel" check on the
commit), but that build does **not** always take over the custom production alias
`chris-fifaworldcup26-prediction.vercel.app` automatically — new deploys can land
without the alias following, so the live URL keeps serving the previous build.

If the live site is stale after a successful push, promote the latest deploy:

```bash
# from the repo root, logged in to the Vercel CLI:
cd frontend && npx vercel --prod        # deploys + assigns the production alias
# — or in the dashboard: Deployments → latest → ⋯ → "Promote to Production"
```

To confirm `main` auto-promotes in future, set **Settings ▸ Git ▸ Production
Branch = `main`** on the Vercel project.

## Verify the live data

The frontend falls back to static snapshots in `frontend/public/snapshot/` when
the backend is unreachable, so the fastest way to confirm a deploy actually
shipped new results is to read a snapshot off the live host:

```bash
curl -s https://chris-fifaworldcup26-prediction.vercel.app/snapshot/api_matches.json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); \
print([f\"{m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']}\" \
for m in d if m['played']][-5:])"
```

Stale tells: response header `age` is large (hours) and `last-modified` predates
your push — the alias is still on an old deployment (see promotion step above).
