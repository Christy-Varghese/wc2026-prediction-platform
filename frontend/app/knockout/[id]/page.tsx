"use client";
import useSWR from "swr";
import Link from "next/link";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Flag, LowConfidenceTag, isLowConfidence } from "@/components/ui";
import { MatchFlowReport } from "@/components/match-flow";

const fetcher = (p: string) => api(p);
const ET = "America/New_York";
const fmt = (iso: string) =>
  new Date(iso).toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", timeZone: ET,
  });
const pctStr = (x?: number) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

export default function KnockoutMatchPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data, error } = useSWR("/api/knockout", fetcher);

  if (error) return <Shell><div className="card text-live">Knockout data offline.</div></Shell>;
  if (!data) return <Shell><div className="h-80 animate-pulse rounded-2xl bg-white/5" /></Shell>;

  const m = data.matches?.find((x: any) => String(x.id) === String(id));
  if (!m || !m.resolved)
    return <Shell><div className="card">This tie isn't resolved yet — slots fill once the group stage completes.</div></Shell>;

  const journeys = data.journeys ?? {};
  const homeWin = m.predicted_winner === m.home_team;
  const a = m.analysis ?? {};

  return (
    <Shell>
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
        {/* header */}
        <div className="card overflow-hidden p-0">
          <div className="flex items-center justify-between bg-white/[0.04] px-4 py-2 text-[11px] text-muted">
            <span className="chip">{m.round} · Match {m.id}</span>
            <span>{fmt(m.kickoff)} · 📍 {m.venue}, {m.city}</span>
          </div>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 p-5">
            <TeamHead name={m.home_team} flag={m.home_flag} win={homeWin}
              title={m.home_title_pct} />
            <div className="text-center">
              <div className="font-display text-3xl font-bold text-gold">
                {m.predicted_score}
              </div>
              <div className="text-[10px] uppercase tracking-widest text-muted">
                {m.shootout ? "after pens" : "predicted"}
              </div>
            </div>
            <TeamHead name={m.away_team} flag={m.away_flag} win={!homeWin}
              title={m.away_title_pct} right />
          </div>
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-t border-white/10 px-4 py-3 text-sm">
            <span><span className="font-bold text-gold">{m.predicted_winner}</span> advances</span>
            <span className="text-muted">·</span>
            <span>win prob <span className="font-bold text-stadium">{Math.round((m.win_probability ?? 0) * 100)}%</span></span>
            {m.confidence != null && <><span className="text-muted">·</span><span>conf <span className="font-bold">{m.confidence}</span></span></>}
            {isLowConfidence(m) && <LowConfidenceTag confidence={m.confidence} />}
          </div>
          {m.survival?.advance_stage && (
            <div className="flex justify-center gap-6 border-t border-white/10 px-4 py-2 text-[11px] text-muted">
              <span>↗ reach {m.survival.advance_stage}:</span>
              <span>{m.home_team} <b className="text-stadium">{pctStr(m.survival.home?.advance)}</b></span>
              <span>{m.away_team} <b className="text-stadium">{pctStr(m.survival.away?.advance)}</b></span>
            </div>
          )}
        </div>

        {/* road to here — both teams' journeys */}
        <section>
          <h2 className="mb-3 font-display text-lg font-bold">Road to this tie</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <JourneyColumn team={m.home_team} flag={m.home_flag} games={journeys[m.home_team]} />
            <JourneyColumn team={m.away_team} flag={m.away_flag} games={journeys[m.away_team]} />
          </div>
        </section>

        {/* CAI three-way scenario projection */}
        {m.flow?.scenarios?.length > 0 && (
          <section>
            <div className="mb-1 flex items-center gap-2">
              <h2 className="font-display text-lg font-bold">CAI runs it three ways</h2>
              <span className="chip text-[10px]">form-led · xG</span>
            </div>
            <p className="mb-3 text-[12px] text-muted">
              CAI weights this year's matches, the group stage and live momentum over pre-tournament data,
              then projects the goal flow under three outcomes.
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              {m.flow.scenarios.map((s: any) => <ScenarioCard key={s.key} s={s} />)}
            </div>
          </section>
        )}

        {/* pain points */}
        {m.flow?.pain_points && (
          <section className="card p-5">
            <h2 className="mb-3 font-display text-lg font-bold">Pain points — where it could swing</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {[m.home_team, m.away_team].map((t: string) => (
                <div key={t}>
                  <h3 className="mb-1.5 font-display text-sm font-bold text-gold">{t}</h3>
                  <ul className="space-y-1 text-[13px] leading-snug text-stadium">
                    {(m.flow.pain_points[t] ?? []).map((p: string, k: number) => (
                      <li key={k} className="flex gap-2"><span className="text-live">⚠</span><span>{p}</span></li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* why the projected winner advances */}
        <section className="card p-5">
          <h2 className="mb-3 font-display text-lg font-bold">Why {m.predicted_winner} advances</h2>
          <div className="space-y-2">
            <CompareBar label="Player condition" h={a.home_condition} a={a.away_condition} fmt={pctStr} />
            <CompareBar label="Manager track record" h={a.home_manager_wr} a={a.away_manager_wr} fmt={pctStr} />
            {a.home_gk_quality != null &&
              <CompareBar label="Goalkeeper" h={a.home_gk_quality} a={a.away_gk_quality} fmt={pctStr} />}
            {a.expected_goals && (
              <div className="flex justify-between pt-1 text-[12px] text-muted">
                <span>Expected goals</span>
                <span className="font-semibold text-stadium">
                  {a.expected_goals.home?.toFixed(2)} – {a.expected_goals.away?.toFixed(2)}
                </span>
              </div>
            )}
          </div>
          {m.reasons?.length > 0 && (
            <ul className="mt-4 space-y-1.5 text-[13px] leading-snug text-stadium">
              {m.reasons.map((rs: string, k: number) => (
                <li key={k} className="flex gap-2"><span className="text-gold">›</span><span>{rs}</span></li>
              ))}
            </ul>
          )}
        </section>

        {/* projected game flow */}
        {m.flow && (
          <section className="card p-5">
            <h2 className="mb-3 font-display text-lg font-bold">How the tie plays out</h2>
            <MatchFlowReport flow={m.flow} />
          </section>
        )}
      </motion.div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <Link href="/knockout" className="inline-flex items-center gap-1 text-[13px] text-muted hover:text-gold">
        ← All knockout ties
      </Link>
      {children}
    </div>
  );
}

function TeamHead({ name, flag, win, title, right }:
  { name: string; flag?: string; win: boolean; title?: number; right?: boolean }) {
  return (
    <div className={`flex flex-col items-center gap-2 ${right ? "md:items-center" : ""}`}>
      <Flag url={flag} name={name} size={52} />
      <div className={`text-center font-display leading-tight ${win ? "text-base font-bold text-gold" : "text-sm font-semibold text-stadium"}`}>
        {name}
      </div>
      {title != null && <div className="text-[10px] text-muted">🏆 {pctStr(title)} title</div>}
    </div>
  );
}

/* ── a team's group-stage path: each game + key moment ───────────────────── */
function JourneyColumn({ team, flag, games }:
  { team: string; flag?: string; games?: any[] }) {
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center gap-2">
        <Flag url={flag} name={team} size={24} />
        <h3 className="font-display text-sm font-bold">{team}</h3>
        {games && games.length > 0 && (
          <span className="ml-auto flex gap-1">
            {games.map((g, i) => <ResultDot key={i} r={g.result} />)}
          </span>
        )}
      </div>
      {!games || games.length === 0 ? (
        <p className="text-[12px] text-muted">No group-stage games on record.</p>
      ) : (
        <ol className="space-y-3">
          {games.map((g, i) => <JourneyGame key={i} g={g} />)}
        </ol>
      )}
    </div>
  );
}

function JourneyGame({ g }: { g: any }) {
  const scorers = (g.team_scorers ?? []).map((s: any) =>
    `${s.player} ${s.minute}'${s.type && s.type !== "goal" ? " (" + (s.type === "own goal" ? "OG" : "P") + ")" : ""}`);
  return (
    <li className="border-l-2 border-white/10 pl-3">
      <div className="flex items-center gap-2 text-sm">
        <ResultDot r={g.result} />
        <span className="font-display font-bold tabular-nums text-stadium">{g.score}</span>
        <span className="text-muted">vs</span>
        <Flag url={g.opp_flag} name={g.opponent} size={16} />
        <span className="font-medium">{g.opponent}</span>
      </div>
      {scorers.length > 0 && (
        <div className="mt-0.5 text-[11px] text-gold/80">⚽ {scorers.join(" · ")}</div>
      )}
      {(g.turning_point || g.headline) && (
        <div className="mt-0.5 text-[11px] leading-snug text-muted">
          {g.turning_point || g.headline}
        </div>
      )}
    </li>
  );
}

function ScenarioCard({ s }: { s: any }) {
  const accent = s.key === "upside" ? "border-stadium/40" : s.key === "downside" ? "border-live/40" : "border-gold/40";
  const tag = s.result === "penalties" ? "→ pens" : s.result === "draw" ? "draw" : "in 90'";
  return (
    <div className={`card border ${accent} p-3`}>
      <div className="mb-1 flex items-center justify-between">
        <span className="font-display text-[12px] font-bold">{s.label}</span>
        {s.likelihood != null && <span className="text-[10px] text-muted">{Math.round(s.likelihood * 100)}%</span>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-display text-2xl font-bold text-gold tabular-nums">{s.score}</span>
        <span className="text-[10px] uppercase tracking-widest text-muted">{tag}</span>
      </div>
      <div className="mt-0.5 text-[11px] text-muted">
        xG {s.xg?.home}–{s.xg?.away}
      </div>
      <p className="mt-1.5 text-[12px] leading-snug text-stadium">{s.note}</p>
    </div>
  );
}

function ResultDot({ r }: { r: string }) {
  const cls = r === "W" ? "bg-stadium text-black" : r === "D" ? "bg-white/30 text-white" : "bg-live text-white";
  return (
    <span className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${cls}`}>
      {r}
    </span>
  );
}

function CompareBar({ label, h, a, fmt }:
  { label: string; h?: number; a?: number; fmt: (v?: number) => string }) {
  const hv = h ?? 0, av = a ?? 0;
  const hLead = hv >= av;
  const max = 1;
  return (
    <div>
      <div className="mb-0.5 flex justify-between text-[11px]">
        <span className={hLead ? "font-bold text-gold" : "text-muted"}>{fmt(h)}</span>
        <span className="text-muted">{label}</span>
        <span className={!hLead ? "font-bold text-gold" : "text-muted"}>{fmt(a)}</span>
      </div>
      <div className="flex h-2 gap-1">
        <div className="flex flex-1 justify-end">
          <div className={`h-full rounded-l-full ${hLead ? "bg-gold/80" : "bg-white/20"}`}
            style={{ width: `${Math.min(100, (hv / max) * 100)}%` }} />
        </div>
        <div className="flex flex-1 justify-start">
          <div className={`h-full rounded-r-full ${!hLead ? "bg-gold/80" : "bg-white/20"}`}
            style={{ width: `${Math.min(100, (av / max) * 100)}%` }} />
        </div>
      </div>
    </div>
  );
}
