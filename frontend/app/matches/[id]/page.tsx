"use client";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api, pct, pct0 } from "@/lib/api";
import {
  Flag, ProbBar, Countdown, LiveBadge, SectionHeader, StatRow,
  LowConfidenceTag, isLowConfidence, PredictionBadge,
} from "@/components/ui";
import { MatchAnalytics } from "@/components/match-analytics";
import { MatchFlowReport } from "@/components/match-flow";
import {
  CaiScenarios, CaiPainPoints, CaiCompareBar, KeyPlayersToNote, CaiVerdict,
} from "@/components/cai-blocks";

const fetcher = (p: string) => api(p);

export default function MatchCenter({ params }: { params: { id: string } }) {
  const { data, error } = useSWR(`/api/matches/${params.id}`, fetcher);
  if (error) return (
    <div className="card-broadcast flex items-center gap-3 text-danger">
      <span className="text-2xl">⚡</span> Match feed unavailable.
    </div>
  );
  if (!data) return <MatchSkeleton />;

  const { match: m, prediction: p, key_players, tactical, injuries,
    availability, conditions, team_comparison } = data;
  const home = m.home_team, away = m.away_team;
  const tc = team_comparison || {};
  const wx = conditions?.weather;
  const xg = p.expected_goals;
  const actualWinner = m.played
    ? (m.home_score > m.away_score ? home : m.away_score > m.home_score ? away : "Draw")
    : undefined;
  const flags = { [home]: tc[home]?.flag_url, [away]: tc[away]?.flag_url };

  return (
    <div className="space-y-8">

      {/* ════════════ SCOREBOARD HERO ════════════ */}
      <motion.section
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        className="relative overflow-hidden rounded-3xl border border-cyan/20 bg-gradient-to-br from-ink-2 via-ink-3/90 to-ink p-7 shadow-[0_0_80px_rgba(0,212,255,0.07)] sm:p-10"
      >
        {/* beam decorations */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 left-1/3 h-[500px] w-px bg-gradient-to-b from-cyan/15 to-transparent" />
          <div className="absolute -top-40 right-1/3 h-[500px] w-px bg-gradient-to-b from-gold/10 to-transparent" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_50%_-10%,rgba(0,212,255,0.06),transparent)]" />
        </div>

        <div className="relative z-10">
          {/* meta row */}
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 text-[11px] text-muted">
            <div className="flex items-center gap-3">
              {m.played ? <LiveBadge label="FULL TIME" color="cyan" /> : <LiveBadge label="MATCH CENTER" color="cyan" />}
              <span className="chip-cyan font-display uppercase tracking-widest">
                GROUP {m.group} · {m.matchday}
              </span>
            </div>
            <span className="font-display uppercase tracking-[0.2em]">
              🏟 {m.venue} · {new Date(m.kickoff).toLocaleString(undefined,
                { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>

          {/* teams */}
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-6">
            <ScoreTeam name={home} flag={tc[home]?.flag_url} prob={p.p_home}
              side="home" isLeading={p.p_home >= p.p_away} />

            <div className="flex flex-col items-center gap-3 sm:gap-4">
              <div className={`font-display text-3xl sm:text-5xl font-extrabold tracking-widest tabnum ${m.played ? "text-stadium" : "text-white/20"}`}>
                {m.played ? `${m.home_score} – ${m.away_score}` : "VS"}
              </div>
              {m.played
                ? <span className="chip-gold text-xs">FULL TIME</span>
                : <Countdown to={m.kickoff} />}
              {m.played && (
                <PredictionBadge m={{
                  played: true, home_team: m.home_team, away_team: m.away_team,
                  home_score: m.home_score, away_score: m.away_score,
                  predicted_winner: p.predicted_winner,
                }} />
              )}
              <span className="chip text-xs">Draw {pct0(p.p_draw)}</span>
            </div>

            <ScoreTeam name={away} flag={tc[away]?.flag_url} prob={p.p_away}
              side="away" isLeading={p.p_away > p.p_home} />
          </div>

          {/* prob bar */}
          <div className="mt-8">
            <ProbBar home={p.p_home} draw={p.p_draw} away={p.p_away} height={10} />
            <div className="mt-2 grid grid-cols-3 items-start gap-2 text-xs tabnum sm:text-sm">
              <div className="min-w-0 text-success font-bold">
                <span className="block break-words leading-tight">{home}</span>
                <span className="block">{pct0(p.p_home)}</span>
              </div>
              <div className="text-center text-muted">
                <span className="block leading-tight">DRAW</span>
                <span className="block">{pct0(p.p_draw)}</span>
              </div>
              <div className="min-w-0 text-right text-cyan font-bold">
                <span className="block break-words leading-tight">{away}</span>
                <span className="block">{pct0(p.p_away)}</span>
              </div>
            </div>
          </div>
        </div>
      </motion.section>

      {/* ════════════ POST-MATCH ANALYTICS (played only) ════════════ */}
      {m.played && <MatchAnalytics matchId={m.id} />}

      {/* ════════════ CAI PREDICTION ════════════ */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-display text-lg font-bold">CAI prediction</h2>
          <span className="chip text-[10px]">form-led model</span>
          {m.played && <span className="text-[11px] text-muted">· what CAI called pre-match</span>}
        </div>

        <CaiVerdict predictedWinner={p.predicted_winner} home={home} away={away}
          played={m.played} actualWinner={actualWinner} />

        <div className="card p-4">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
            <span className="font-bold text-success">{home} {pct0(p.p_home)}</span>
            <span className="text-muted">Draw {pct0(p.p_draw)}</span>
            <span className="font-bold text-cyan">{away} {pct0(p.p_away)}</span>
            <span className="text-[12px] text-muted">xG {xg.home}–{xg.away}</span>
            <span className="ml-auto text-[12px] text-gold">{p.confidence} conf</span>
            {isLowConfidence({ confidence: p.confidence, played: m.played }) &&
              <LowConfidenceTag confidence={p.confidence} />}
          </div>
          <div className="mt-3"><ProbBar home={p.p_home} draw={p.p_draw} away={p.p_away} height={8} /></div>
          <div className="mt-4">
            <div className="mb-2 text-[11px] uppercase tracking-widest text-muted">Most likely scorelines</div>
            {p.top_scores.map((s: any) => (
              <div key={s.score} className="flex items-center gap-3 py-1">
                <span className="w-12 font-display font-bold text-stadium">{s.score}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                  <div className="h-2 rounded-full bg-gradient-to-r from-gold to-gold/40"
                    style={{ width: `${(s.prob / p.top_scores[0].prob) * 100}%` }} />
                </div>
                <span className="w-12 text-right text-xs tabnum text-muted">{pct(s.prob)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CAI 3-scenario projection */}
      <CaiScenarios scenarios={data.flow?.scenarios} />

      {/* pain points */}
      <CaiPainPoints home={home} away={away} painPoints={data.flow?.pain_points} />

      {/* why the favoured side comes out on top */}
      {p.condition && (
        <section className="card p-5">
          <h2 className="mb-3 font-display text-lg font-bold">
            {p.predicted_winner === "Draw"
              ? "Why CAI sees it level"
              : `Why ${p.predicted_winner} ${m.played ? "was favoured" : "is favoured"}`}
          </h2>
          <div className="space-y-2">
            <CaiCompareBar label="Player condition" h={p.condition.home_cond} a={p.condition.away_cond} />
            <CaiCompareBar label="Manager track record" h={p.condition.home_manager_wr} a={p.condition.away_manager_wr} />
            {p.condition.home_gk_quality != null &&
              <CaiCompareBar label="Goalkeeper" h={p.condition.home_gk_quality} a={p.condition.away_gk_quality} />}
            <div className="flex justify-between pt-1 text-[12px] text-muted">
              <span>Expected goals</span>
              <span className="font-semibold text-stadium">{xg.home} – {xg.away}</span>
            </div>
          </div>
          {p.win_reasons?.length > 0 && (
            <ul className="mt-4 space-y-1.5 text-[13px] leading-snug text-stadium">
              {p.win_reasons.map((rs: string, k: number) => (
                <li key={k} className="flex gap-2"><span className="text-gold">›</span><span>{rs}</span></li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* best-condition simulation + predicted key moments */}
      {data.flow && (
        <section className="card p-5">
          <h2 className="mb-3 font-display text-lg font-bold">
            How CAI sees it play out
            <span className="ml-2 text-[11px] font-normal text-muted">
              {data.flow.n_sims?.toLocaleString()}-run simulation
            </span>
          </h2>
          <MatchFlowReport flow={data.flow} />
        </section>
      )}

      {/* ════════════ KEY PLAYERS (3 to note, with images) ════════════ */}
      <KeyPlayersToNote home={home} away={away} keyPlayers={key_players} flags={flags} />

      {/* ════════════ INJURIES & SUSPENSIONS (full width) ════════════ */}
      <section className="card-broadcast">
        <SectionHeader title="INJURIES & SUSPENSIONS" sub="availability hits CAI factors in" />
        <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
          {[home, away].map((t) => {
            const list = injuries[t] ?? [];
            return (
              <div key={t}>
                <div className="mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-2 font-display text-sm font-semibold text-stadium">
                    <Flag url={tc[t]?.flag_url} name={t} size={20} /> {t}
                  </span>
                  {availability?.[t] != null && (
                    <span className="text-[11px] text-muted">
                      avail{" "}
                      <b className={availability[t] >= 0.95 ? "text-success"
                        : availability[t] >= 0.85 ? "text-gold" : "text-danger"}>
                        {Math.round(availability[t] * 100)}%
                      </b>
                    </span>
                  )}
                </div>
                {list.length === 0 ? (
                  <p className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-[12px] text-muted">
                    ✅ Full squad available — no reported injuries or suspensions.
                  </p>
                ) : (
                  <ul className="divide-y divide-white/5 rounded-lg border border-white/5 bg-white/[0.02]">
                    {list.map((inj: any) => (
                      <li key={inj.name} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
                        <span className="flex items-center gap-2">
                          <span className={inj.fitness === "out" ? "text-danger" : "text-gold"}>
                            {inj.fitness === "out" ? "⛔" : "⚠"}
                          </span>
                          <span className="font-semibold text-stadium">{inj.name}</span>
                          <span className={`rounded px-1.5 text-[10px] ${
                            inj.fitness === "out" ? "bg-danger/15 text-danger" : "bg-gold/15 text-gold"}`}>
                            {inj.fitness}
                          </span>
                        </span>
                        <span className="text-right text-muted">
                          {inj.news}{inj.return_date ? ` · ~${inj.return_date}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* ════════════ CONDITIONS + MODEL ENSEMBLE ════════════ */}
      <div className="grid gap-6 md:grid-cols-2">
        {conditions && (
          <section className="card-broadcast">
            <SectionHeader title="MATCH CONDITIONS" sub="Environmental & logistical factors" />
            <div className="space-y-1">
              <StatRow label={`Weather${wx?.source === "live" ? " 🔴" : ""}`}
                value={<span className="text-stadium">{wx?.summary}</span>} />
              <StatRow label="Temperature" value={`${wx?.temp_c}°C · ${wx?.humidity}% RH`} />
              {(wx?.altitude_m ?? 0) >= 1000 && (
                <StatRow label="Altitude" value={`${wx?.altitude_m} m`} />
              )}
              <StatRow label="Weather severity"
                value={
                  <span className={wx?.severity >= 0.6 ? "text-danger" : wx?.severity >= 0.3 ? "text-gold" : "text-success"}>
                    {Math.round((wx?.severity ?? 0) * 100)}%
                  </span>
                } />
              <StatRow label="Rest days"
                value={`${home} ${conditions.rest_days?.[home]}d · ${away} ${conditions.rest_days?.[away]}d`} />
              <StatRow label="Travel to venue"
                value={`${home} ${Math.round(conditions.travel_km?.[home] ?? 0)} km · ${away} ${Math.round(conditions.travel_km?.[away] ?? 0)} km`} />
            </div>
          </section>
        )}

        <section className="card-broadcast">
          <SectionHeader title="CAI SIGNAL MIX" sub="how the inputs voted (form-led)" />
          <div className="mb-3 flex justify-end gap-4 text-[10px] uppercase tracking-widest text-muted">
            <span className="text-success">Home</span>
            <span>Draw</span>
            <span className="text-cyan">Away</span>
          </div>
          <div className="space-y-2">
            {Object.entries(p.members).map(([name, v]: any) => (
              <div key={name} className="flex items-center gap-2 rounded-lg bg-white/[0.02] px-3 py-2 text-xs">
                <span className="w-20 font-display uppercase tracking-wide text-muted">{name}</span>
                <div className="flex-1">
                  <ProbBar home={v[0]} draw={v[1]} away={v[2]} height={4} />
                </div>
                <span className="w-10 text-right tabnum text-success">{pct0(v[0])}</span>
                <span className="w-10 text-right tabnum text-muted">{pct0(v[1])}</span>
                <span className="w-10 text-right tabnum text-cyan">{pct0(v[2])}</span>
              </div>
            ))}
          </div>
          {tactical?.summary && (
            <p className="mt-4 text-[12px] text-muted leading-relaxed">{tactical.summary}</p>
          )}
        </section>
      </div>

    </div>
  );
}

/* ── Score team column ── */
function ScoreTeam({ name, flag, prob, isLeading }:
  { name: string; flag?: string; prob: number; side: "home" | "away"; isLeading: boolean }) {
  return (
    <div className={`flex w-full min-w-0 flex-col items-center gap-3 text-center`}>
      <div className="relative">
        <Flag url={flag} name={name} size={64} />
        {isLeading && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-gold text-[10px] font-bold text-ink">★</span>
        )}
      </div>
      <div className="w-full break-words font-display text-base font-bold text-stadium leading-tight sm:text-xl">{name}</div>
      <div className={`font-display text-3xl font-extrabold tabnum ${isLeading ? "text-gold" : "text-cyan"}`}>
        {pct0(prob)}
      </div>
    </div>
  );
}

/* ── Probability row ── */
/* ── Skeleton ── */
function MatchSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-80 animate-pulse rounded-3xl bg-ink-2" />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="h-72 animate-pulse rounded-2xl bg-ink-2" />
        <div className="h-72 animate-pulse rounded-2xl bg-ink-2" />
      </div>
    </div>
  );
}

