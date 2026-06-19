"use client";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api, pct } from "@/lib/api";
import { Flag, ProbBar, SectionHeader } from "@/components/ui";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

const fetcher = (p: string) => api(p);

export default function SimulatorPage() {
  const { data, error } = useSWR("/api/simulate?top=24", fetcher);
  const { data: groups } = useSWR("/api/simulate/groups", fetcher);

  if (error) return (
    <div className="card-broadcast flex items-center gap-3 text-danger">
      <span className="text-2xl">⚡</span> Run the pipeline first — no simulation data.
    </div>
  );
  if (!data) return <SimSkeleton />;

  const chart = data.champion_odds.slice(0, 12);
  const fullTable = data.champion_odds;

  return (
    <div className="space-y-8">
      <SectionHeader
        title="TOURNAMENT SIMULATOR"
        sub="50 000 Monte Carlo tournaments · 12 groups · 32-team knockout"
      />

      {/* ════════════ CHAMPION ODDS CHART ════════════ */}
      <motion.section
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        className="card-broadcast">
        <SectionHeader title="CHAMPION PROBABILITY" sub="Top 12 contenders" />
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 40, top: 4, bottom: 4 }}>
              <XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`}
                stroke="#4A5B80" fontSize={11} tick={{ fill: "#8FA0C8" }} />
              <YAxis type="category" dataKey="team" width={96}
                fontSize={12} tick={{ fill: "#C8D3E8" }} />
              <Tooltip
                formatter={(v: number) => [`${pct(v)}`, "Champion"]}
                cursor={{ fill: "rgba(0,212,255,0.04)" }}
                contentStyle={{
                  background: "#0F1D3D",
                  border: "1px solid rgba(0,212,255,0.2)",
                  borderRadius: 12,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="Champion" radius={[0, 8, 8, 0]}>
                {chart.map((_: any, i: number) => (
                  <Cell key={i}
                    fill={i === 0 ? "#FFD700" : i === 1 ? "#00D4FF" : i <= 3 ? "#00FFB2" : "#2A3F6B"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </motion.section>

      {/* ════════════ STAGE-BY-STAGE TABLE ════════════ */}
      <motion.section
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
        className="card-broadcast overflow-hidden">
        <SectionHeader title="STAGE-BY-STAGE ODDS" sub="Full 48-team field" />
        <div className="overflow-x-auto">
          <div className="min-w-[440px]">
            {/* header — shares the row grid template so columns line up */}
            <div className={`${STAGE_GRID} border-b border-white/10 px-2 py-3
              text-[11px] uppercase tracking-widest text-muted`}>
              <span>#</span>
              <span>Team</span>
              <span className="text-right">R32</span>
              <span className="text-right">QF</span>
              <span className="text-right">SF</span>
              <span className="text-right">Final</span>
              <span className="pr-1 text-right">🏆</span>
            </div>
            {fullTable.map((r: any, i: number) => (
              <StageRow key={r.team} r={r} rank={i + 1} />
            ))}
          </div>
        </div>
      </motion.section>

      {/* ════════════ GROUP PROJECTIONS WALL-CHART ════════════ */}
      {groups && (
        <motion.section
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
          <SectionHeader title="GROUP PROJECTIONS" sub="Simulated advancement probabilities" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Object.entries(groups).map(([g, teams]: any) => (
              <GroupCard key={g} group={g} teams={teams} />
            ))}
          </div>
        </motion.section>
      )}
    </div>
  );
}

/* ── Stage-by-stage odds row (shared grid template w/ the header) ── */
const STAGE_GRID =
  "grid grid-cols-[26px_minmax(0,1fr)_repeat(5,46px)] items-center gap-1";

function StageRow({ r, rank }: { r: any; rank: number }) {
  return (
    <div className={`${STAGE_GRID} border-b border-line/30 px-2 py-2
      ${rank === 1 ? "border-l-2 border-l-gold"
        : rank === 2 ? "border-l-2 border-l-cyan" : ""}`}>
      <span className={`text-[11px] font-bold tabnum ${rank <= 3 ? "text-gold" : "text-muted/50"}`}>
        {rank}
      </span>
      <span className="flex min-w-0 items-center gap-1.5">
        <Flag url={r.flag_url} name={r.team} size={16} />
        <span className="min-w-0 break-words leading-tight font-display text-sm font-semibold">
          {r.team}
        </span>
      </span>
      <span className="text-right tabnum text-xs text-muted">{pct(r.R32)}</span>
      <span className="text-right tabnum text-xs text-muted">{pct(r.QF)}</span>
      <span className="text-right tabnum text-xs">{pct(r.SF)}</span>
      <span className="text-right tabnum text-xs">{pct(r.Final)}</span>
      <span className={`pr-1 text-right tabnum text-sm font-bold
        ${rank === 1 ? "text-gold" : rank <= 3 ? "text-cyan" : ""}`}>
        {pct(r.Champion)}
      </span>
    </div>
  );
}

/* ── Group wall-chart card ── */
function GroupCard({ group, teams }: { group: string; teams: any[] }) {
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
        {teams.map((t: any, i: number) => (
          <div key={t.team}>
            <div className="mb-1 flex items-center justify-between">
              <span className={`flex items-center gap-2 text-sm font-semibold ${i < 2 ? "text-stadium" : "text-muted"}`}>
                <span className={`text-xs w-4 ${i < 2 ? "text-teal" : "text-muted/50"}`}>{i + 1}.</span>
                {t.team}
                {i < 2 && <span className="chip-gold text-[9px]">ADV</span>}
              </span>
              <span className="tabnum text-xs font-bold text-cyan">{pct(t.advance_prob)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
              <motion.div
                className={`h-1.5 rounded-full ${i === 0 ? "bg-gold" : i === 1 ? "bg-cyan" : "bg-white/20"}`}
                initial={{ width: 0 }}
                animate={{ width: `${(t.advance_prob / maxProb) * 100}%` }}
                transition={{ duration: 0.7, delay: 0.3 + i * 0.05 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Skeleton ── */
function SimSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-12 w-80 animate-pulse rounded-lg bg-ink-2" />
      <div className="h-80 animate-pulse rounded-2xl bg-ink-2" />
      <div className="h-96 animate-pulse rounded-2xl bg-ink-2" />
    </div>
  );
}

