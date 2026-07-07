"use client";
import { useState, useEffect, useMemo } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import Link from "next/link";
import { api, pct } from "@/lib/api";
import { AIInsightCard, SectionHeader, Flag } from "@/components/ui";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";

const fetcher = (p: string) => api(p);

// Distinct line colours for the champion-trend chart (by team rank).
const TREND_COLORS = ["#FFD700", "#00D4FF", "#00FFB2", "#FF6B9D", "#B388FF",
  "#FFA94D", "#4DD0E1", "#F06292", "#AED581", "#9575CD"];

/* ── Derive eliminated teams and confirmed R16 qualifiers from knockout
 * results (merged in from the old /simulator page). ── */
function useKnockoutStatus() {
  const { data: ko } = useSWR("/api/knockout", fetcher, { revalidateOnFocus: false });
  return useMemo<{ eliminated: Set<string>; r16Teams: Set<string> }>(() => {
    const eliminated = new Set<string>();
    const r16Teams   = new Set<string>();
    if (!ko?.matches) return { eliminated, r16Teams };
    for (const m of ko.matches as any[]) {
      const hs = m.home_score;
      const aws = m.away_score;
      if (hs == null || aws == null) continue;
      const home = m.home_team;
      const away = m.away_team;
      if (!home || !away) continue;
      const ph: number | null = m.pen_home ?? null;
      const pa: number | null = m.pen_away ?? null;
      let winner: string, loser: string;
      if (hs > aws)           { winner = home; loser = away; }
      else if (aws > hs)      { winner = away; loser = home; }
      else if (ph != null && pa != null) {
        winner = ph > pa ? home : away;
        loser  = ph > pa ? away : home;
      } else { continue; }
      eliminated.add(loser);
      if (m.type === "r32") r16Teams.add(winner);
    }
    return { eliminated, r16Teams };
  }, [ko]);
}

/* Flag teams already through their R32 tie for the ✓ display — the backend
 * sim resolves the real, fixed bracket directly, so R32+ odds for these
 * teams are already conditioned on the real bracket state. */
function applyConditional(r: any, r16Teams: Set<string>): any {
  if (!r16Teams.has(r.team)) return r;
  return { ...r, _conditional: true };
}

type SortStage = "R32" | "QF" | "SF" | "Final" | "Champion";
const SORT_STAGES: SortStage[] = ["R32", "QF", "SF", "Final", "Champion"];
const STAGE_GRID = "grid grid-cols-[26px_minmax(0,1fr)_repeat(5,46px)] items-center gap-1";

export default function AnalyticsPage() {
  const { data: ins } = useSWR("/api/insights", fetcher);
  const { data: sim } = useSWR("/api/simulate?top=24", fetcher);
  const { data: groups } = useSWR("/api/simulate/groups", fetcher);
  const { data: trend } = useSWR("/api/simulate/champion-trend", fetcher);
  const { eliminated, r16Teams } = useKnockoutStatus();
  const [sortBy, setSortBy] = useState<SortStage>("Champion");

  // Which teams to plot on the trend chart. All teams are selectable; default
  // to the current top 6 so the chart isn't 48-line spaghetti.
  const [picked, setPicked] = useState<string[] | null>(null);
  useEffect(() => {
    if (trend?.teams && picked === null) setPicked(trend.teams.slice(0, 6));
  }, [trend, picked]);
  const sel = picked ?? [];
  const colorFor = (team: string) =>
    TREND_COLORS[(trend?.teams?.indexOf(team) ?? 0) % TREND_COLORS.length];
  const toggle = (team: string) =>
    setPicked((p) => {
      const cur = p ?? [];
      return cur.includes(team) ? cur.filter((t) => t !== team) : [...cur, team];
    });

  const fullTable = (sim?.champion_odds as any[] ?? []).map((r: any) => applyConditional(r, r16Teams));
  const sortFn = (a: any, b: any) => (b[sortBy] ?? 0) - (a[sortBy] ?? 0);
  const activeRows = fullTable.filter((r: any) => !eliminated.has(r.team)).sort(sortFn);
  const eliminatedRows = fullTable.filter((r: any) => eliminated.has(r.team));
  const chartAll = [...fullTable].sort((a: any, b: any) => b.Champion - a.Champion).slice(0, 12);
  const chartRows = [
    ...chartAll.filter((r: any) => !eliminated.has(r.team)),
    ...chartAll.filter((r: any) => eliminated.has(r.team)),
  ];

  return (
    <div className="space-y-8">
      <SectionHeader title="ANALYTICS" sub="Model signals, tournament simulation & upset alerts" />

      {/* ════ KNOCKED-OUT NOTICE ════ */}
      {eliminated.size > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-white/8 bg-white/3 px-5 py-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="font-display text-sm font-semibold text-muted">
              {eliminated.size} team{eliminated.size > 1 ? "s" : ""} knocked out · shown faded below
            </span>
          </div>
          <div className="flex flex-wrap gap-3">
            {[...eliminated].sort().map((team) => {
              const row = fullTable.find((r: any) => r.team === team);
              return (
                <Link key={team} href={`/teams/${encodeURIComponent(team)}`}
                  className="flex items-center gap-2 rounded-xl border border-white/8 bg-white/3
                             px-3 py-2 opacity-50 transition hover:opacity-80">
                  <div className="grayscale">
                    <Flag url={row?.flag_url} name={team} size={20} />
                  </div>
                  <div>
                    <div className="font-display text-[12px] font-bold text-muted/60 leading-tight">
                      {team}
                    </div>
                    <div className="text-[9px] text-muted/40 uppercase tracking-wider">
                      Was {pct(row?.Champion ?? 0)} title odds
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* champion odds chart */}
      <section className="card-broadcast">
        <SectionHeader title="TITLE-WINNER PROBABILITY" sub="Top 12 · 50 000 simulations" />
        {eliminated.size > 0 && (
          <p className="mb-3 text-[11px] text-muted">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-white/20 mr-1.5 align-middle" />
            Faded bars = knocked out · probabilities are pre-tournament model output
          </p>
        )}
        <div className="h-80">
          {sim ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartRows} layout="vertical" margin={{ left: 8, right: 56, top: 4, bottom: 4 }}>
                <XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`}
                  stroke="#4A5B80" fontSize={11} tick={{ fill: "#8FA0C8" }} />
                <YAxis type="category" dataKey="team" width={100} fontSize={11}
                  tick={(props: any) => {
                    const isOut = eliminated.has(props.payload.value);
                    return (
                      <text
                        x={props.x} y={props.y} dy={4}
                        textAnchor="end"
                        fill={isOut ? "#4A5B80" : "#C8D3E8"}
                        fontSize={11}
                        opacity={isOut ? 0.45 : 1}
                      >
                        {props.payload.value}
                      </text>
                    );
                  }}
                />
                <Tooltip
                  formatter={(v: number, _: any, props: any) => {
                    const isOut = eliminated.has(props.payload.team);
                    return [`${pct(v)}${isOut ? " (knocked out)" : ""}`, "Champion"];
                  }}
                  cursor={{ fill: "rgba(0,212,255,0.04)" }}
                  contentStyle={{
                    background: "#0F1D3D",
                    border: "1px solid rgba(0,212,255,0.2)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="Champion" radius={[0, 8, 8, 0]}>
                  {chartRows.map((r: any, i: number) => {
                    const isOut = eliminated.has(r.team);
                    if (isOut) return <Cell key={i} fill="#2A3F6B" opacity={0.35} />;
                    const rank = chartRows.filter((x: any) => !eliminated.has(x.team)).indexOf(r);
                    return (
                      <Cell key={i}
                        fill={rank === 0 ? "#FFD700" : rank === 1 ? "#00D4FF" : rank <= 3 ? "#00FFB2" : "#2A3F6B"} />
                    );
                  })}
                  <LabelList dataKey="Champion"
                    position="right"
                    formatter={(v: number) => `${(v * 100).toFixed(1)}%`}
                    style={{ fill: "#8FA0C8", fontSize: 10 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="h-full animate-pulse rounded-xl bg-ink-2" />}
        </div>
      </section>

      {/* champion % trend over time */}
      <section className="card-broadcast">
        <SectionHeader title="CHAMPION % TREND"
          sub="How title-winner probability has moved as results come in"
          action={trend?.teams?.length > 0 ? (
            <div className="flex gap-1.5">
              <button onClick={() => setPicked(trend.teams)}
                className="btn-sm text-[11px]">All</button>
              <button onClick={() => setPicked(trend.teams.slice(0, 6))}
                className="btn-sm text-[11px]">Top 6</button>
              <button onClick={() => setPicked([])}
                className="btn-sm text-[11px]">Clear</button>
            </div>
          ) : undefined} />

        {/* team selector — every team is toggleable */}
        {trend?.teams?.length > 0 && (
          <div className="mb-3 flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
            {trend.teams.map((t: string) => {
              const on = sel.includes(t);
              return (
                <button key={t} onClick={() => toggle(t)}
                  className={`chip cursor-pointer text-[10px] transition ${on ? "" : "opacity-50"}`}
                  style={on ? { borderColor: colorFor(t), color: colorFor(t) } : undefined}>
                  {t} {trend.current?.[t] != null && <span className="opacity-70">{trend.current[t]}%</span>}
                </button>
              );
            })}
          </div>
        )}

        <div className="h-80">
          {trend && trend.series?.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend.series}
                margin={{ left: 4, right: 20, top: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" stroke="#4A5B80" fontSize={11} tick={{ fill: "#8FA0C8" }} />
                <YAxis tickFormatter={(v) => `${v}%`} stroke="#4A5B80" fontSize={11}
                  tick={{ fill: "#8FA0C8" }} width={40} domain={[0, "auto"]} />
                <Tooltip
                  formatter={(v: number, name: string) => [`${v}%`, name]}
                  contentStyle={{
                    background: "#0F1D3D",
                    border: "1px solid rgba(0,212,255,0.2)",
                    borderRadius: 12,
                    fontSize: 12,
                  }} />
                {sel.length <= 8 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                {sel.map((t: string) => (
                  <Line key={t} type="monotone" dataKey={t}
                    stroke={colorFor(t)} strokeWidth={1.8}
                    dot={{ r: 2 }} activeDot={{ r: 4 }} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : <div className="h-full animate-pulse rounded-xl bg-ink-2" />}
        </div>
        <p className="mt-2 text-[11px] text-muted/70">
          {sel.length} of {trend?.teams?.length ?? 0} teams shown · tap a team to toggle. One point
          per matchday · in-tournament results nudge each team's Elo, which feeds the 50 000-run
          knockout simulation. Moves are small by design (group-stage K-factor is damped).
        </p>
      </section>

      {/* ════ STAGE-BY-STAGE ODDS TABLE ════ */}
      <section className="card-broadcast overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
          <SectionHeader
            title="STAGE-BY-STAGE ODDS"
            sub={`${activeRows.length} active · ${eliminatedRows.length} eliminated${r16Teams.size > 0 ? " · R16 odds conditional on current bracket" : ""}`}
          />
          {/* Sort filter pills */}
          <div className="flex items-center gap-1 flex-wrap">
            <span className="text-[10px] text-muted/50 uppercase tracking-widest mr-1">Sort by</span>
            {SORT_STAGES.map((stage) => (
              <button
                key={stage}
                onClick={() => setSortBy(stage)}
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition
                  ${sortBy === stage
                    ? stage === "Champion"
                      ? "bg-gold/20 text-gold border border-gold/40"
                      : stage === "SF" || stage === "Final"
                        ? "bg-cyan/15 text-cyan border border-cyan/30"
                        : "bg-white/10 text-white border border-white/20"
                    : "text-muted/50 border border-white/8 hover:text-muted hover:border-white/20"
                  }`}
              >
                {stage === "Champion" ? "🏆" : stage}
                {sortBy === stage && <span className="ml-0.5 opacity-70">↓</span>}
              </button>
            ))}
          </div>
        </div>

        {!sim ? (
          <div className="h-64 animate-pulse rounded-xl bg-ink-2" />
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[440px]">
              {/* header */}
              <div className={`${STAGE_GRID} border-b border-white/10 px-2 py-3 text-[11px] uppercase tracking-widest text-muted`}>
                <span>#</span>
                <span>Team</span>
                {SORT_STAGES.map((stage) => (
                  <button
                    key={stage}
                    onClick={() => setSortBy(stage)}
                    className={`text-right transition w-full
                      ${sortBy === stage
                        ? stage === "Champion" ? "text-gold font-bold" : "text-cyan font-bold"
                        : "text-muted/60 hover:text-muted"
                      }`}
                  >
                    {stage === "Champion" ? "🏆" : stage}
                  </button>
                ))}
              </div>

              {/* Active teams */}
              {activeRows.map((r: any, i: number) => (
                <StageRow key={r.team} r={r} rank={i + 1} eliminated={false} sortBy={sortBy} />
              ))}

              {/* Knocked-out divider */}
              {eliminatedRows.length > 0 && (
                <div className="flex items-center gap-3 border-t border-white/8 bg-white/2 px-3 py-2 mt-1">
                  <span className="font-display text-[10px] uppercase tracking-widest text-muted/50">
                    Knocked out
                  </span>
                </div>
              )}

              {/* Eliminated teams */}
              {eliminatedRows.map((r: any, i: number) => (
                <StageRow key={r.team} r={r} rank={activeRows.length + i + 1} eliminated={true} sortBy={sortBy} />
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ════ GROUP PROJECTIONS ════ */}
      {groups && (
        <section>
          <SectionHeader title="GROUP PROJECTIONS" sub="Simulated advancement probabilities" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Object.entries(groups).map(([g, teams]: any) => (
              <GroupCard key={g} group={g} teams={teams} eliminated={eliminated} />
            ))}
          </div>
        </section>
      )}

      {/* upset alerts + dark horses */}
      <div className="grid gap-6 md:grid-cols-2">
        <section className="card-broadcast">
          <SectionHeader title="⚠ UPSET ALERTS" sub="High-variance fixtures" />
          {ins?.upset_alerts?.length
            ? ins.upset_alerts.map((a: any, i: number) => (
              <motion.div key={a.match}
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="border-b border-white/5 py-3">
                <div className="flex justify-between text-sm">
                  <span className="font-display font-semibold text-stadium">{a.match}</span>
                  <span className="font-bold tabnum text-gold">{pct(a.underdog_win_prob)}</span>
                </div>
                <p className="mt-1 text-[11px] text-muted">{a.note}</p>
              </motion.div>
            ))
            : <p className="text-sm text-muted py-4">No high-variance fixtures flagged.</p>}
        </section>

        <section className="card-broadcast">
          <SectionHeader title="🐎 DARK HORSES" sub="Value picks — outperforming their seed" />
          {ins?.dark_horses?.length
            ? ins.dark_horses
              .filter((d: any) => !eliminated.has(d.team))
              .map((d: any, i: number) => (
                <motion.div key={d.team}
                  initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="border-b border-white/5 py-3">
                  <div className="flex justify-between text-sm">
                    <span className="font-display font-semibold text-stadium">
                      {d.team} <span className="chip text-[10px]">#{d.elo_rank}</span>
                    </span>
                    <div className="flex gap-3 text-right">
                      <div>
                        <div className="font-bold tabnum text-teal">{pct(d.semi_prob)}</div>
                        <div className="text-[9px] text-muted">SF prob</div>
                      </div>
                      <div>
                        <div className="font-bold tabnum text-gold">{pct(d.title_prob)}</div>
                        <div className="text-[9px] text-muted">Title prob</div>
                      </div>
                    </div>
                  </div>
                  <p className="mt-1 text-[11px] text-muted">{d.note}</p>
                </motion.div>
              ))
            : <p className="text-sm text-muted py-4">Run the simulator to surface dark horses.</p>}
        </section>
      </div>

      {/* AI insights */}
      {ins?.insights?.length > 0 && (
        <section>
          <SectionHeader title="CAI INSIGHTS" sub="Model anomaly signals" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ins.insights.slice(0, 6).map((ins: any, i: number) => (
              <AIInsightCard key={i} text={ins.text} confidence={ins.confidence} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

/* ── Stage row (merged in from the old /simulator page) ── */
function StageRow({ r, rank, eliminated, sortBy }: {
  r: any; rank: number; eliminated: boolean; sortBy: SortStage;
}) {
  return (
    <Link href={`/teams/${encodeURIComponent(r.team)}`}
      className={`
        ${STAGE_GRID} border-b px-2 py-2 transition
        ${eliminated
          ? "border-white/5 opacity-40 hover:opacity-70"
          : rank === 1
            ? "border-line/30 border-l-2 border-l-gold hover:bg-white/3"
            : rank === 2
              ? "border-line/30 border-l-2 border-l-cyan hover:bg-white/3"
              : "border-line/30 hover:bg-white/3"
        }
      `}>

      {/* rank */}
      <span className={`text-[11px] font-bold tabnum ${
        eliminated ? "text-muted/30" : rank <= 3 ? "text-gold" : "text-muted/50"}`}>
        {rank}
      </span>

      {/* team */}
      <span className="flex min-w-0 items-center gap-1.5">
        <div className={eliminated ? "grayscale" : ""}>
          <Flag url={r.flag_url} name={r.team} size={16} />
        </div>
        <span className={`min-w-0 break-words font-display text-sm font-semibold leading-tight
          ${eliminated ? "text-muted/50" : ""}`}>
          {r.team}
        </span>
      </span>

      {/* stage probabilities */}
      {(["R32", "QF", "SF", "Final", "Champion"] as const).map((stage, si) => {
        const isSort = stage === sortBy;
        const isWonR32 = !eliminated && r._conditional && stage === "R32";
        return (
          <span key={stage}
            className={`text-right tabnum text-xs
              ${eliminated ? "text-muted/25" : ""}
              ${!eliminated && isSort && stage === "Champion" ? "font-bold text-gold" : ""}
              ${!eliminated && isSort && stage !== "Champion" ? "font-bold text-cyan" : ""}
              ${!eliminated && !isSort ? "text-muted/60" : ""}
              ${si === 4 ? "pr-1" : ""}
            `}>
            {eliminated ? "—" : isWonR32 ? <span className="text-teal">✓</span> : pct(r[stage])}
          </span>
        );
      })}
    </Link>
  );
}

/* ── Group wall-chart card (merged in from the old /simulator page) ── */
function GroupCard({ group, teams, eliminated }: {
  group: string; teams: any[]; eliminated: Set<string>;
}) {
  const maxProb = Math.max(...teams.map((t: any) => t.advance_prob ?? 0), 0.01);
  return (
    <div className="card-broadcast">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-display text-xs font-bold uppercase tracking-widest text-stadium">
          Group {group}
        </span>
        <span className="chip-cyan text-[9px]">Advancement</span>
      </div>
      <div className="space-y-3">
        {teams.map((t: any, i: number) => {
          const isOut = eliminated.has(t.team);
          return (
            <div key={t.team} className={isOut ? "opacity-35" : ""}>
              <div className="mb-1 flex items-center justify-between">
                <span className={`flex items-center gap-1.5 text-sm font-semibold
                  ${isOut ? "text-muted/50" : i < 2 ? "text-stadium" : "text-muted"}`}>
                  <span className={`text-xs w-4 ${
                    isOut ? "text-muted/30" : i < 2 ? "text-teal" : "text-muted/50"}`}>
                    {i + 1}.
                  </span>
                  {t.team}
                  {!isOut && i < 2 && <span className="chip-gold text-[9px]">ADV</span>}
                </span>
                <span className={`tabnum text-xs font-bold ${isOut ? "text-muted/30" : "text-cyan"}`}>
                  {isOut ? "—" : pct(t.advance_prob)}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                <motion.div
                  className={`h-1.5 rounded-full ${
                    isOut ? "bg-white/10"
                    : i === 0 ? "bg-gold"
                    : i === 1 ? "bg-cyan"
                    : "bg-white/20"}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${(t.advance_prob / maxProb) * 100}%` }}
                  transition={{ duration: 0.7, delay: 0.3 + i * 0.05 }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
