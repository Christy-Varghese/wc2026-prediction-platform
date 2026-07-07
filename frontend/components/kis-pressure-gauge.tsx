"use client";
/* Knockout Pressure Score gauge — KIS_SPEC.md §4[6]. Renders
   `result.pressure_score` (0-100 per team) from POST /api/v1/predict/kis.
   Deliberately labeled PARTIAL (3 of 5 formula inputs — captain_maturity and
   crowd_factor have no data source yet, see KIS_SPEC.md's Phase 1/2 status
   notes) rather than presenting it as the complete formula — the D1 honesty
   principle applies to the UI, not just the API's `basis` field. */
import { motion } from "framer-motion";

export function KisPressureGauge({ result }: { result: any }) {
  if (!result?.pressure_score) return null;
  const scores: Record<string, number> = result.pressure_score;
  const teams = Object.keys(scores);
  const max = Math.max(...Object.values(scores), 1);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-widest text-muted">
          Knockout Pressure Score
        </div>
        <span className="chip text-[9px]"
          title="Partial formula: knockout experience + shootout record + composure only. captain_maturity and crowd_factor are excluded — no reliable data source yet.">
          ⓘ 3/5 inputs
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {teams.map((team) => {
          const score = scores[team];
          const color = score >= 65 ? "#00E676" : score >= 40 ? "#FFD700" : "#FF4D4D";
          return (
            <div key={team} className="flex flex-col items-center gap-2 rounded-xl border border-white/5 bg-white/3 p-3">
              <GaugeRing value={score} max={100} color={color} />
              <div className="truncate text-center font-display text-[11px] font-semibold text-stadium">
                {team}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GaugeRing({ value, max, color, size = 84 }:
  { value: number; max: number; color: string; size?: number }) {
  const r = size / 2 - 7;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / max));
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={6} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={6} strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - frac) }}
          transition={{ duration: 1.1, ease: "easeOut" }} />
      </svg>
      <div className="absolute text-center pointer-events-none">
        <div className="font-display text-lg font-bold tabnum leading-none" style={{ color }}>
          {Math.round(value)}
        </div>
        <div className="mt-0.5 text-[8px] uppercase tracking-wider text-muted leading-none">/ 100</div>
      </div>
    </div>
  );
}
