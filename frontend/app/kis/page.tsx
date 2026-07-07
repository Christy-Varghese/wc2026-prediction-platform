"use client";
/* KIS Hub — Knockout Intelligence System. Team-vs-team vector simulator.
   Picks two teams, POSTs to /api/v1/predict/kis, and renders the result
   using the reused MatchFlowReport (probability ladder / scenarios / pain
   points / key players / explainability — unchanged, byte-for-byte the same
   component the knockout/analytics pages already use) plus three net-new
   KIS-specific components for the vector decomposition, pressure score, and
   chaos-tagged timeline. See KIS_SPEC.md §6.4 for the component hierarchy. */
import { useState } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { Flag, SectionHeader } from "@/components/ui";
import { MatchFlowReport } from "@/components/match-flow";
import { KisVectorGrid } from "@/components/kis-vector-grid";
import { KisPressureGauge } from "@/components/kis-pressure-gauge";
import { KisChaosTimeline } from "@/components/kis-chaos-timeline";

const fetcher = (p: string) => api(p);

export default function KisHubPage() {
  const { data: teams } = useSWR("/api/teams", fetcher);
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [result, setResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const teamList: any[] = teams ?? [];
  const canRun = home && away && home !== away && state !== "loading";

  async function runSimulation() {
    if (!canRun) return;
    setState("loading");
    setErrorMsg("");
    try {
      const r = await api("/api/v1/predict/kis", {
        method: "POST",
        body: JSON.stringify({ home_team: home, away_team: away }),
      });
      setResult(r);
      setState("done");
    } catch (err: any) {
      setErrorMsg(err?.message ?? "KIS simulation failed — the backend may be offline.");
      setState("error");
    }
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        title="KIS · Knockout Intelligence System"
        sub="Vector-decomposed tactical simulation"
      />

      <div className="card-broadcast">
        <p className="mb-5 max-w-2xl text-[13px] leading-relaxed text-muted">
          KIS runs a 50,000-simulation Monte Carlo for any knockout matchup and
          decomposes the result into a <b className="text-success">Skill</b> vector
          (form, tactics, composure) and a <b className="text-chaos">Luck</b> vector
          (variance, chaos events) — <span className="tabnum">‖P‖² = ‖S‖² + ‖L‖²</span>.
          This platform is an AI-driven probability simulation built for
          entertainment and analytics purposes. Not betting advice.
        </p>

        {/* team picker */}
        <div className="flex flex-wrap items-end gap-4">
          <TeamSelect label="Home / Team A" value={home} onChange={setHome}
            teams={teamList} exclude={away} />
          <div className="pb-2.5 font-display text-lg font-bold text-gold/70">vs</div>
          <TeamSelect label="Away / Team B" value={away} onChange={setAway}
            teams={teamList} exclude={home} />
          <button onClick={runSimulation} disabled={!canRun}
            className="btn-gold disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-gold">
            {state === "loading" ? "Simulating…" : "Run KIS Simulation"}
          </button>
        </div>

        {home && away && home === away && (
          <p className="mt-2 text-[11px] text-danger">Pick two different teams.</p>
        )}
        {state === "error" && (
          <p className="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
            {errorMsg}
          </p>
        )}
      </div>

      <AnimatePresence mode="wait">
        {state === "done" && result && (
          <motion.div key={`${home}-${away}`}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }} className="space-y-5">

            {/* headline */}
            <div className="card-broadcast text-center">
              <div className="flex items-center justify-center gap-4">
                <Flag url={teamList.find(t => t.name === home)?.flag_url} name={home} size={40} />
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-muted">
                    {result.mode === "knockout" ? "Projected to advance" : "Projected result"}
                  </div>
                  <div className="font-display text-2xl font-bold text-gold">
                    {result.predicted_winner}
                    <span className="ml-2 text-stadium">{result.predicted_score}</span>
                    {result.shootout && <span className="ml-1 text-sm text-muted">· pens</span>}
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    probability <b className="text-stadium">{(result.win_probability * 100).toFixed(1)}%</b>
                    {" · "}{result.n_sims?.toLocaleString()} Monte Carlo runs
                  </div>
                </div>
                <Flag url={teamList.find(t => t.name === away)?.flag_url} name={away} size={40} />
              </div>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <div className="card-broadcast">
                <KisVectorGrid result={result} />
              </div>
              <div className="card-broadcast">
                <KisPressureGauge result={result} />
              </div>
            </div>

            <div className="card-broadcast">
              <KisChaosTimeline result={result} />
            </div>

            <div className="card-broadcast">
              <div className="mb-4 text-[11px] uppercase tracking-widest text-muted">
                Full Knockout Report
              </div>
              <MatchFlowReport flow={result} />
            </div>

            <p className="text-center text-[10px] text-muted/60">{result.disclaimer}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {state === "idle" && (
        <div className="card-broadcast py-12 text-center text-muted">
          Pick two teams above and run a simulation to see the full KIS breakdown.
        </div>
      )}
    </div>
  );
}

function TeamSelect({ label, value, onChange, teams, exclude }: {
  label: string; value: string; onChange: (v: string) => void;
  teams: any[]; exclude?: string;
}) {
  return (
    <div className="min-w-[220px]">
      <label className="mb-1.5 block text-[10px] uppercase tracking-widest text-muted">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-white/10 bg-ink-3 px-4 py-2.5 text-sm text-stadium
                   focus:border-cyan/40 focus:outline-none focus:ring-1 focus:ring-cyan/20">
        <option value="">Select team…</option>
        {teams
          .filter((t) => t.name !== exclude)
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((t) => (
            <option key={t.name} value={t.name}>{t.name}</option>
          ))}
      </select>
    </div>
  );
}
