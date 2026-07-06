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
4. **Current live state (as of 2026-07-06): `NEXT_PUBLIC_STATIC_ONLY=1` IS set**
   on Vercel Production — deliberately, because Render (§1) has never actually
   been provisioned. `frontend/lib/api.ts`'s `api()` short-circuits to
   `fromSnapshot()` for every GET before constructing any request when this
   flag is set, so the frontend serves only snapshots with no live-backend
   traffic at all — no request, successful or failed, ever reaches
   `NEXT_PUBLIC_API_URL`. (Previously this var was believed to already be
   set but actually wasn't; see "Stale ticker" below for what that caused
   and how it was found.) **Once you provision Render (§1) and set
   `NEXT_PUBLIC_API_URL` to its real URL, remove `NEXT_PUBLIC_STATIC_ONLY`**:
   Vercel → project → **Settings ▸ Environment Variables** → remove it from
   Production, **then redeploy** — `vercel redeploy <deployment-url-or-alias>
   --target production` (required: `NEXT_PUBLIC_*` vars are inlined into the
   JS bundle at build time, so editing the env var alone does not change an
   already-built deployment) — or the frontend will keep serving only
   snapshots even though a live backend now exists.
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
- **Expected right now** — `NEXT_PUBLIC_STATIC_ONLY=1` is deliberately set
  because Render isn't provisioned (§2.4). Nothing to fix unless you've
  already provisioned Render and set `NEXT_PUBLIC_API_URL`.
- If you *have* set up Render and it's still snapshot-only: check
  `NEXT_PUBLIC_STATIC_ONLY` wasn't left set on Vercel (§2.4) — this is the #1
  cause and produces no visible error anywhere.
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

## Stale ticker / wasted localhost round-trip ⚠️ (root cause + fix, 2026-07-06)

**Symptom:** the live site's nav ticker (and any page reading `/api/news`)
showed weeks-old content — "Round of 32 underway", "outcome accuracy: 51/77
(66%)", "Argentina champions (26.7%)" — while every other check (latest commit
deployed, alias pointed at the right deployment, static snapshot JSON fetched
directly) showed the correct, current data. Looked exactly like a stale CDN
cache (`x-vercel-cache: HIT`, growing `age` header) but wasn't.

**Root cause:** neither `NEXT_PUBLIC_API_URL` nor `NEXT_PUBLIC_STATIC_ONLY` was
actually set on Vercel Production (§2.4 had documented `STATIC_ONLY` as already
set — it wasn't). With both unset, `API` in `lib/api.ts` defaulted to
`http://localhost:8000`, so every page load attempted — and failed — a request
to that dead address before falling back to `fromSnapshot()`. During that
window, and in the server-rendered pre-hydration HTML (which is *all* `curl` or
a fast page-read ever sees, since these pages are Client Components — the
`useSWR` data is `undefined` until client JS runs), the UI showed
`components/nav.tsx`'s hardcoded `NEWS_FALLBACK` array — a snapshot frozen from
an old tournament state, never updated since. So `curl`-based "is the deploy
stale?" checks were misleading here: they weren't seeing a caching bug, they
were seeing the intended fallback UI, made unusually visible/persistent by the
localhost round-trip.

**Fix:** set `NEXT_PUBLIC_STATIC_ONLY=1` on Vercel Production
(`vercel env add NEXT_PUBLIC_STATIC_ONLY production`), then rebuild —
`vercel redeploy chris-fifaworldcup26-prediction.vercel.app --target
production` (editing the env var alone does nothing until the next build,
since `NEXT_PUBLIC_*` vars are inlined at build time). This makes `api()` skip
straight to the snapshot with no localhost attempt at all.

**How to actually verify this class of issue:** don't rely on `curl` or a
one-shot page fetch — check the browser Network tab (or a scripted headless
browser with JS execution) after the page has hydrated, and confirm there's no
request to `localhost:8000` (or your Render URL, per the alias troubleshooting
above) and that the ticker text matches `/snapshot/api_news.json`'s current
content. Also watch for a **stale cached JS bundle in whatever browser/tool
you're testing with** — Next.js fingerprints chunk filenames by content hash,
so if a re-check still shows the old hash (visible in the Network tab / page
source), the browser session itself is serving cached JS from before your fix,
not the live deployment; hard-refresh or use a fresh session before concluding
a fix didn't work.

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
