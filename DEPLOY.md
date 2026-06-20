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

Both platforms redeploy on every push to `main` once connected.
