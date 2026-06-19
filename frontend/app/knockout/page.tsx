"use client";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

const fetcher = (p: string) => api(p);
const ET = "America/New_York";
const fmt = (iso: string) =>
  new Date(iso).toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", timeZone: ET,
  });

export default function KnockoutPage() {
  const { data, error } = useSWR("/api/knockout", fetcher);
  if (error) return <div className="card text-live">Knockout schedule offline.</div>;
  if (!data) return <div className="h-80 animate-pulse rounded-2xl bg-white/5" />;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold">Knockout Bracket · World Cup 2026</h1>
        <span className="text-xs text-muted">Jun 28 – Jul 19 · times ET</span>
      </div>
      <p className="text-sm text-muted">
        Official knockout schedule (Round of 32 → Final). Team slots resolve from
        the group standings — winners, runners-up and the eight best third-placed
        teams advance to the 32-team bracket.
      </p>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {data.rounds.map((r: any, ri: number) => (
          <div key={r.round} className="min-w-[260px] flex-1">
            <h2 className="h2 sticky top-0 mb-3">{r.round}</h2>
            <div className="space-y-3">
              {r.matches.map((m: any, i: number) => (
                <motion.div key={m.id}
                  initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: ri * 0.05 + i * 0.02 }}
                  className={`card p-3 ${m.round === "Final"
                    ? "border-gold/50 bg-gold/10 shadow-glow" : ""}`}>
                  <div className="mb-2 flex items-center justify-between text-[11px] text-muted">
                    <span className="chip">Match {m.id}</span>
                    <span>{fmt(m.kickoff)}</span>
                  </div>
                  <div className="space-y-1 font-display text-sm font-semibold">
                    <div className="break-words leading-tight">{m.home_label}</div>
                    <div className="text-[10px] uppercase tracking-widest text-gold/70">vs</div>
                    <div className="break-words leading-tight">{m.away_label}</div>
                  </div>
                  <div className="mt-2 text-[11px] text-muted">
                    📍 {m.venue} · {m.city}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
