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

### 1a. Rotate admin credentials — do this before the service is reachable

`backend/app/config.py` defaults to `admin_username=admin`, `admin_password=admin`,
and a hardcoded `jwt_secret`. The admin API (`backend/app/routers/admin.py`) is
**not** read-only — it can trigger a retrain, refresh odds/injuries/weather, and
upload data. `render.yaml` intentionally does NOT commit real values for these
(`JWT_SECRET` auto-generates via `generateValue: true`; `ADMIN_USERNAME` /
`ADMIN_PASSWORD` are `sync: false`), so you must set the latter two yourself:

1. Render dashboard → `wc2026-api` → **Environment**.
2. Set `ADMIN_USERNAME` to something other than `admin`.
3. Set `ADMIN_PASSWORD` to a real generated password (not `admin`).
4. Save (auto-redeploys). Verify: `curl -X POST https://wc2026-api.onrender.com/api/admin/login -d "username=admin&password=admin"` must return `401`, not a token.

Do this in the same session as provisioning — the window between "API is
reachable" and "credentials are rotated" is exposure time.

## 2. Frontend → Vercel

1. Go to <https://vercel.com/new> → import the same GitHub repo.
2. **Root Directory:** `frontend`. Framework preset: **Next.js** (auto).
3. **Environment Variable:**
   `NEXT_PUBLIC_API_URL = https://wc2026-api.onrender.com` (your Render URL).
4. **If `NEXT_PUBLIC_STATIC_ONLY=1` is already set on this project** (it is, as
   of this writing — added to serve the demo from snapshots only while there was
   no live backend): **remove it**, or the frontend will never call the Render
   API at all. `frontend/lib/api.ts`'s `api()` short-circuits to
   `fromSnapshot()` before constructing any request when this flag is set —
   every step above will look successful (health check green, no errors) while
   the frontend silently keeps serving only snapshots. Vercel → project →
   **Settings ▸ Environment Variables** → remove `NEXT_PUBLIC_STATIC_ONLY`
   from Production → redeploy.
5. Deploy. Vercel gives you a URL like
   `https://wc2026-prediction-platform.vercel.app`.

## 3. Wire CORS

Back in Render → `wc2026-api` → **Environment** → set `CORS_ORIGINS` to your
real Vercel domain(s), comma-separated, no trailing slash. Don't trust the
value committed in `render.yaml` without checking — verify first:

```bash
npx vercel project ls          # confirms the current Production URL
npx vercel alias ls | grep chris-fifaworldcup26   # confirms the custom alias is live
```

Include **both** the auto-generated project domain (`frontend-five-iota-33.vercel.app`)
and the custom alias (`chris-fifaworldcup26-prediction.vercel.app`) — e.g.
`https://chris-fifaworldcup26-prediction.vercel.app,https://frontend-five-iota-33.vercel.app,http://localhost:3000`,
then **Save** (auto-redeploys).

A wrong value here fails silently: a CORS-blocked fetch is caught by
`api.ts`'s generic `catch` and degrades to the snapshot fallback with no visible
error, so a misconfigured `CORS_ORIGINS` looks identical to success. See
**Troubleshooting** below for how to actually verify this.

## 4. Verify

Open the Vercel URL → `/knockout`. Bracket, podium, title-% and the analysis
modal should all load from the live backend — **check the Network tab** (not
just page content), since identical content can come from either the live API
or the snapshot fallback.

Confirm CORS actually rejects the wrong origin (proves it isn't wide open):

```bash
curl -H "Origin: https://not-the-real-domain.example" \
  https://wc2026-api.onrender.com/api/health -v 2>&1 | grep -i "access-control"
# Expect: no Access-Control-Allow-Origin header for this origin
```

Confirm cold-start behavior degrades gracefully: wait >15 min idle, then load a
page and watch the Network tab — the live request should time out around 2.5s
and fall back to the snapshot, not hang the page for the full ~30-60s wake.

## Troubleshooting

**Page loads but always shows snapshot data, never live data:**
- Check `NEXT_PUBLIC_STATIC_ONLY` isn't still set on Vercel (§2.4 above) — this
  is the #1 cause and produces no visible error anywhere.
- Open browser DevTools → Network tab → reload → look for a request to
  `wc2026-api.onrender.com`. If there's no request at all, it's `STATIC_ONLY`.
  If there's a request that fails, read on.

**Network tab shows a failed/red request to the Render API:**
- **CORS error** (console shows `has been blocked by CORS policy`): the
  `Origin` header of your Vercel domain isn't in Render's `CORS_ORIGINS`. Re-run
  the `vercel alias ls` check in §3 and re-set the env var — a stale or
  incomplete list is the most common cause, and it's silent from the frontend's
  perspective (falls back to snapshot, no user-visible error).
- **CORS negative test passes but real requests still fail:** check for a
  trailing slash or `http` vs `https` mismatch in `CORS_ORIGINS` — FastAPI's
  CORS middleware matches origins exactly.
- **Request just hangs then times out (~2.5s) every time, even when not cold:**
  Render service may be down/crashed — check the Render dashboard's Logs tab
  for a build or runtime error, most commonly a `requirements.txt` install
  failure (check the build log for a package that failed to compile) or an
  import error in `app/main.py`.

**Render build fails:**
- Read the actual build log in the Render dashboard (Render → `wc2026-api` →
  **Logs**, filter to the latest deploy) — the failure is almost always a
  specific `pip install` line; the top-level "Deploy failed" message alone
  won't tell you which package.
- Confirm `PYTHON_VERSION` in `render.yaml` matches a version Render actually
  offers; check Render's current supported versions if the build fails at the
  Python setup step (before any pip install even starts).

**Admin login unexpectedly succeeds with `admin`/`admin`:**
- You skipped §1a. Rotate `ADMIN_USERNAME`/`ADMIN_PASSWORD` in the Render
  dashboard immediately — this means the admin API (retrain, refresh, upload)
  is currently open to anyone who finds the URL.

## Auto-deploy

Both platforms **build** on every push to `main` once connected.

## Production alias ⚠️ (root cause + permanent fix)

**Symptom:** a push to `main` builds successfully (green "Vercel" check on the
commit) and the deploy is marked Production, yet
`chris-fifaworldcup26-prediction.vercel.app` keeps serving the *previous* build.

**Root cause:** the custom alias `chris-fifaworldcup26-prediction.vercel.app` is
**not in the Vercel project's Domains list**. Production deploys auto-assign only
the domains the project owns — here that's the auto-generated
`frontend-five-iota-33.vercel.app` (the project's Root Directory is `frontend`,
hence the `frontend-*` name). The custom alias was attached manually once and is
**not** updated by subsequent deploys, so it stays pinned to whatever deployment
it was last set to.

**Permanent fix (do once):** Vercel → project `chris-fifaworldcup26-prediction` →
**Settings ▸ Domains ▸ Add** `chris-fifaworldcup26-prediction.vercel.app`. After
that it follows every production deploy automatically and the steps below are no
longer needed.

**Manual fix (until the domain is added):** deploy, then re-point the alias.
The CLI is linked to this project; **run from the repo root**, not from
`frontend/` (the project already applies Root Directory `frontend`, so running
inside it makes Vercel look for `frontend/frontend` and fail):

```bash
# from the repo ROOT, logged in to the Vercel CLI:
npx vercel --prod --yes                  # prints a Production URL: chris-...-<hash>.vercel.app
npx vercel alias set <that-hash-url> chris-fifaworldcup26-prediction.vercel.app
```

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
