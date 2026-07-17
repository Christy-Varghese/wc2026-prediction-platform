"use client";
/* Head-to-head comparison for the final two ties. Every axis is backed by
 * a real field: Attack/Midfield/Defence/Bench Depth are derived from squad
 * `impact` scores (see lib/team-attributes.ts, same calc the team pages
 * already use), Goalkeeper/Manager come straight from the match's
 * `analysis` block, Recent Form from `flow.tournament_form`, and Momentum
 * from `analysis.*_momentum`. Nothing here is invented. */
import useSWR from "swr";
import { motion } from "framer-motion";
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ResponsiveContainer, Legend,
} from "recharts";
import { api } from "@/lib/api";
import { Flag, TeamComparisonCard, ProbRing } from "@/components/ui";
import { computeTeamAttributes } from "@/lib/team-attributes";

const fetcher = (p: string) => api(p);
const clamp = (v: number) => Math.max(0, Math.min(100, v));

export function HeadToHead({ m }: { m: any }) {
  const { data: home } = useSWR(`/api/teams/${encodeURIComponent(m.home_team)}`, fetcher, { revalidateOnFocus: false });
  const { data: away } = useSWR(`/api/teams/${encodeURIComponent(m.away_team)}`, fetcher, { revalidateOnFocus: false });

  if (!home || !away) {
    return (
      <section className="card-broadcast">
        <div className="h-64 animate-pulse rounded-2xl bg-white/5" />
      </section>
    );
  }

  const homeAttrs = computeTeamAttributes(home.squad ?? []);
  const awayAttrs = computeTeamAttributes(away.squad ?? []);
  const a = m.analysis ?? {};
  const homeForm = m.flow?.tournament_form?.[m.home_team]?.form_delta ?? 0;
  const awayForm = m.flow?.tournament_form?.[m.away_team]?.form_delta ?? 0;
  const homeMomentum = a.home_momentum ?? 0;
  const awayMomentum = a.away_momentum ?? 0;

  const barAttrs = {
    home: {
      Attack: Math.round(homeAttrs.attack),
      Midfield: Math.round(homeAttrs.midfield),
      Defence: Math.round(homeAttrs.defence),
      "Bench Depth": Math.round(homeAttrs.benchDepth),
      "Recent Form": Math.round(Math.max(0, homeForm)),
    },
    away: {
      Attack: Math.round(awayAttrs.attack),
      Midfield: Math.round(awayAttrs.midfield),
      Defence: Math.round(awayAttrs.defence),
      "Bench Depth": Math.round(awayAttrs.benchDepth),
      "Recent Form": Math.round(Math.max(0, awayForm)),
    },
  };

  const radarData = [
    { axis: "Attack", [m.home_team]: clamp(homeAttrs.attack), [m.away_team]: clamp(awayAttrs.attack) },
    { axis: "Midfield", [m.home_team]: clamp(homeAttrs.midfield), [m.away_team]: clamp(awayAttrs.midfield) },
    { axis: "Defence", [m.home_team]: clamp(homeAttrs.defence), [m.away_team]: clamp(awayAttrs.defence) },
    { axis: "Goalkeeper", [m.home_team]: clamp((a.home_gk_quality ?? 0) * 100), [m.away_team]: clamp((a.away_gk_quality ?? 0) * 100) },
    { axis: "Manager", [m.home_team]: clamp((a.home_manager_wr ?? 0) * 100), [m.away_team]: clamp((a.away_manager_wr ?? 0) * 100) },
    { axis: "Bench Depth", [m.home_team]: clamp(homeAttrs.benchDepth), [m.away_team]: clamp(awayAttrs.benchDepth) },
    { axis: "Recent Form", [m.home_team]: clamp(homeForm * 2), [m.away_team]: clamp(awayForm * 2) },
    { axis: "Momentum", [m.home_team]: clamp(50 + homeMomentum), [m.away_team]: clamp(50 + awayMomentum) },
  ];

  return (
    <section className="card-broadcast space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-bold">Head to Head</h2>
        <span className="chip text-[10px]" title="Attack/Midfield/Defence/Bench Depth are derived from squad player impact scores, not a separately-modeled rating">
          ⓘ derived from squad data
        </span>
      </div>

      {/* radar overview */}
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData} outerRadius="70%">
            <PolarGrid stroke="rgba(255,255,255,0.08)" />
            <PolarAngleAxis dataKey="axis" tick={{ fill: "#8FA0C8", fontSize: 10 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Radar name={m.home_team} dataKey={m.home_team} stroke="#00E676" fill="#00E676" fillOpacity={0.25} />
            <Radar name={m.away_team} dataKey={m.away_team} stroke="#00D4FF" fill="#00D4FF" fillOpacity={0.25} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* bar breakdown */}
      <TeamComparisonCard home={barAttrs.home} away={barAttrs.away} homeTeam={m.home_team} awayTeam={m.away_team} />

      {/* percentage-shaped stats as rings */}
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
        <RingPair label="Goalkeeper" home={m.home_team} away={m.away_team}
          homeFlag={m.home_flag} awayFlag={m.away_flag}
          homeVal={a.home_gk_quality} awayVal={a.away_gk_quality} />
        <RingPair label="Manager" home={m.home_team} away={m.away_team}
          homeFlag={m.home_flag} awayFlag={m.away_flag}
          homeVal={a.home_manager_wr} awayVal={a.away_manager_wr} />
      </div>

      {/* momentum — can be negative, so it gets its own diverging bar */}
      <MomentumCompare homeTeam={m.home_team} awayTeam={m.away_team} homeVal={homeMomentum} awayVal={awayMomentum} />
    </section>
  );
}

function RingPair({ label, home, away, homeFlag, awayFlag, homeVal, awayVal }: {
  label: string; home: string; away: string; homeFlag?: string; awayFlag?: string;
  homeVal?: number; awayVal?: number;
}) {
  return (
    <div className="col-span-2 flex items-center justify-around rounded-xl border border-white/8 bg-white/3 p-3">
      <div className="flex flex-col items-center gap-1">
        <ProbRing value={homeVal ?? 0} color="#00E676" size={64} />
        <Flag url={homeFlag} name={home} size={16} />
      </div>
      <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <div className="flex flex-col items-center gap-1">
        <ProbRing value={awayVal ?? 0} color="#00D4FF" size={64} />
        <Flag url={awayFlag} name={away} size={16} />
      </div>
    </div>
  );
}

function MomentumCompare({ homeTeam, awayTeam, homeVal, awayVal }: {
  homeTeam: string; awayTeam: string; homeVal: number; awayVal: number;
}) {
  const max = Math.max(Math.abs(homeVal), Math.abs(awayVal), 1);
  const homePct = (Math.abs(homeVal) / max) * 100;
  const awayPct = (Math.abs(awayVal) / max) * 100;
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-[11px]">
        <span className={`font-medium ${homeVal >= 0 ? "text-success" : "text-danger"}`}>
          {homeTeam} {homeVal > 0 ? "+" : ""}{homeVal.toFixed(1)}
        </span>
        <span className="text-[10px] uppercase tracking-widest text-muted">Momentum (Elo Δ)</span>
        <span className={`font-medium ${awayVal >= 0 ? "text-success" : "text-danger"}`}>
          {awayVal > 0 ? "+" : ""}{awayVal.toFixed(1)} {awayTeam}
        </span>
      </div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full">
        <div className="flex flex-1 justify-end overflow-hidden rounded-l-full bg-white/5">
          <motion.div className={`h-full ${homeVal >= 0 ? "bg-success" : "bg-danger/60"}`}
            initial={{ width: 0 }} animate={{ width: `${homePct}%` }} transition={{ duration: 0.8 }} />
        </div>
        <div className="w-px bg-white/20" />
        <div className="flex flex-1 justify-start overflow-hidden rounded-r-full bg-white/5">
          <motion.div className={`h-full ${awayVal >= 0 ? "bg-success" : "bg-danger/60"}`}
            initial={{ width: 0 }} animate={{ width: `${awayPct}%` }} transition={{ duration: 0.8, delay: 0.05 }} />
        </div>
      </div>
    </div>
  );
}
