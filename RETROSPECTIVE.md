# WC2026 Platform — Tournament Retrospective

Internal engineering + model retrospective, written at tournament close
(2026-07-19/20). Deliberately **not** linked from or surfaced on the live
site — this is for whoever works on this codebase next, not site visitors.
The goal is an honest account, not a highlight reel: where the system held
up, where it didn't, and what to actually change next time.

---

## 1. How the model actually did

Final tournament-wide numbers (`/api/tournament-summary`, computed from the
real 3-points-per-match ladder in `app/services.py::prediction_points`):

| Stage | Points | Max | Accuracy | Matches |
|---|---|---|---|---|
| Group | 149 | 216 | **69%** | 72 |
| Knockout | 81 | 96 | **84%** | 32 |
| **Overall** | **230** | **312** | **74%** | 104 |

Plus 15 exact scorelines called across the whole tournament, and the Golden
Boot leaderboard (fully live-computed, not curated) correctly had the
outright winner (Mbappé, 10 goals) throughout the run-in.

**The headline miss was the Final itself.** CAI backed Argentina at 58.6%
pre-match — but flagged it at only **11/100 confidence**, deep in toss-up
territory, at the time, not in hindsight. Spain won 1-0 in extra time. Two
honest ways to read this:

- The confidence system did what it was built to do: it did not present a
  coin-flip as a strong call. Nobody reading the pre-match page was told
  this was safe.
- It was still wrong on the single match that mattered most to the widest
  audience. A "we told you it was uncertain" defense is true but will not
  land with anyone who just wanted the champion picked correctly.

Worth sitting with rather than explaining away: Spain out-shot Argentina
20-2, out-xG'd them 1.94-0.17, and held 65% possession — a statistically
dominant performance that still needed extra time and an opponent down to
10 men to produce a single goal. Emiliano Martínez's 11 saves were the
entire reason it wasn't a rout. That's real single-match variance a
pre-match model has no way to see coming, and it cuts in both directions —
it's also exactly why a 58.6%/11-confidence read was arguably the *right*
amount of uncertainty to express, even though the pick landed wrong.

**Open question, not yet investigated:** why did group-stage accuracy (69%)
trail knockout-stage accuracy (84%) by 15 points? Plausible explanations —
dead-rubber matches with squad rotation, group stage's larger sample simply
regressing harder to the mean, knockout ties benefiting from more real
in-tournament form data by the time they're played — but none of these are
verified. Worth a dedicated pass next time: break group-stage misses down
by matchday and see if MD1 (least in-tournament data available) is dragging
the average down disproportionately.

## 2. Engineering downfalls — what actually went wrong this session

Being specific on purpose, not vague:

**Supabase project auto-paused mid-session, and diagnosing it wasted real
time.** The free-tier project paused from inactivity; requests came back as
Cloudflare `521`s that were genuinely hard to distinguish from a sandboxed
dev environment's own network restrictions at first glance. Multiple rounds
of "check now" / "still not there" followed before it was root-caused.
**Compounding issue:** the Supabase **Table Editor UI said the `votes` table
existed** when it did not — `information_schema.tables` queried directly
showed 0 rows. The dashboard UI was not a trustworthy source of truth here.
Lesson: for any "does this exist / did this write land" question against
Supabase, query `information_schema`/`pg_policies` directly — don't trust
what the dashboard renders, and after any project pause/restore, expect a
PostgREST schema-cache lag even once the underlying table genuinely exists.

**A real, reproducible Framer Motion bug sat undetected in production for an
unknown period.** Animating an SVG `r`/`cx`/`cy` attribute via `animate={{}}`
silently fails with a console error ("Expected length, undefined") unless a
matching `initial` is also supplied. This wasn't introduced this session —
it was already present on the bracket page's center pulsing-aura circle,
confirmed by testing the untouched file directly. It only got caught because
new confetti work happened to touch the same file and the console was
actually being checked. **This means browser console errors were not being
routinely monitored during earlier development** — a real gap, not a one-off.

**The exact same "doesn't handle the terminal state" bug class was hit
three separate times in this session, and each was found reactively, not
proactively:**
1. The homepage's "Final Countdown" promo showed a stale "kickoff" countdown
   and an open vote for a match that had already been played.
2. The homepage's main hero fell back to displaying the *already-played*
   Final as a "NEXT MATCH / KICKOFF" card with pre-match odds.
3. The nav bar's "LIVE" pill and per-link live-dot were permanently on,
   regardless of whether anything was actually live.

All three are the same root cause — code written under the assumption "there
is always a next match" — and all three were only found by manually clicking
through the live site after ingesting the Final, not by any systematic
check. Having found #1, the same pattern should have been actively searched
for elsewhere immediately, rather than waiting to trip over #2 and #3
separately. **This is the single clearest process lesson from this session.**

**A hardcoded test assertion broke on three consecutive data-ingestion
commits before being fixed properly.** `test_defensive_variance_sane_for_
played_team` asserted Argentina's played-match count as a literal integer
(6, then 7, then 8) instead of deriving it from `WC2026_PLAYED` like its
sibling test already did in the same file. Bumping a magic number three
times before generalizing it is three times too many — the sibling test
sitting right below it was the tell the first time.

**Manual result ingestion is inherently slow and needs cross-verification.**
Every real-world result (Third place, Final, award winners) required a web
search, then a follow-up fetch for full match detail, then in most cases a
second independent source to cross-check specific numbers before writing
anything into `knockout.json`. This is the *correct* amount of care for
data that becomes a permanent public record, but it is not fast, and it's
easy to see how a rushed version of this workflow could ship an unverified
or half-sourced number. Advanced match stats (xG/possession/shots split)
were genuinely unavailable for the Third place match after real effort to
find them — left unset rather than guessed, which was the right call but
means that record has a real gap.

## 3. What actually worked well

Worth naming, not just failures:

- The **honesty conventions already built into this codebase** (toss-up
  confidence flagging, `model_predicted_winner` preserved separately from
  the post-hoc-overwritten `predicted_winner`, the "don't fabricate stats
  you can't source" pattern already established in `kis-powered-card.tsx`
  and extended this session to `actual_stats`) made every judgment call in
  this session easier and more consistent. New code had a clear existing
  standard to match rather than needing one invented from scratch.
- The **snapshot-fallback architecture** (`gen_snapshots.py` /
  `frontend/lib/api.ts`) meant every single data change this session —
  Third place, Final, awards, the new `/api/tournament-summary` endpoint —
  flowed through to the backend-free Vercel deploy with one `make
  ingest-scores` / `make snapshots` run and zero frontend-specific
  data-plumbing work.
- **Shared computation, not duplicated computation**, held up under
  pressure: extracting `news.compute_accuracy()` out of the ticker-string
  logic so `/champions` and the ticker read from one function, and
  `lib/team-attributes.ts` out of the teams page for the head-to-head
  component, meant there was never a moment of "which of these two numbers
  is right" — a single source, used twice.
- The **existing test suite caught every regression immediately** — the
  stale match-count assertion, the two "assumes an unresolved tie exists"
  KIS tests — nothing shipped broken because `pytest` was run after every
  change, not just at the end.

## 4. Concrete recommendations for next time

1. **Add a "terminal state" checklist item to feature work.** Any component
   that reasons about "the next match" or "what's upcoming" should be
   explicitly tested against "what does this look like once nothing is
   upcoming" before being considered done — not discovered after the fact.
   Worth a one-line note in `CLAUDE.md` to make this a standing habit.
2. **Grep for the hardcoded-assertion pattern repo-wide, once, rather than
   fixing instances as they break.** `test_defensive_variance_sane_for_
   played_team` was fixed generically this session; there may be siblings
   elsewhere in `backend/ml/tests/` and `backend/tests/` with the same
   "hardcoded count tied to a match total" shape that haven't broken yet
   simply because nothing's touched them recently.
3. **Don't trust the Supabase dashboard UI as a source of truth for schema
   state.** Query `information_schema.tables` / `pg_policies` directly for
   any "does X exist" question. Consider a `make check-supabase` script
   (mirroring `validate_api.py`) that checks table existence + RLS policies
   programmatically after any Supabase-touching change.
4. **Run a console-error smoke check as part of verification, not just
   `tsc`/`pytest`.** A clean typecheck and a clean test suite both passed
   this whole session while a real, reproducible Framer Motion bug sat in
   the shipped bracket page. A quick headless-browser console check (the
   `browse` skill already used ad hoc this session) catches a category of
   bug the other two checks structurally cannot.
5. **Investigate the group-vs-knockout accuracy gap (69% vs 84%)** as a
   dedicated task, not a passing note — break it down by matchday and see
   whether it's a real calibration issue or an artifact of dead-rubber
   games and squad rotation.
6. **If this pattern (a live tournament, hand-ingested as it happens)
   repeats for a future event,** the manual search → fetch → cross-verify →
   write workflow used for every result this session is sound but slow;
   worth deciding upfront whether a scheduled/automated results feed is
   worth building, rather than defaulting to manual ingestion for the
   entire run out of inertia.
