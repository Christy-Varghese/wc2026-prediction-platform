"use client";
/* KIS Vector Analytics Grid — Skill (S_t) vs Luck (L_t) side by side, per
   KIS_SPEC.md §5. Renders `result.vector_metrics` + `result.tactical_rating`
   from POST /api/v1/predict/kis. Skill reuses the site's existing `success`
   green (already means "on-model, as expected"); Luck uses the new
   KIS-scoped `chaos` violet — see tailwind.config.ts D2 note. */
import { motion } from "framer-motion";

const pctStr = (x?: number | null) => (x == null ? "—" : `${(x * 100).toFixed(0)}%`);
const signed = (x?: number | null) =>
  x == null ? "—" : `${x > 0 ? "+" : ""}${x.toFixed(2)}`;

export function KisVectorGrid({ result }: { result: any }) {
  if (!result?.vector_metrics) return null;
  const vm = result.vector_metrics;
  const home = result.home_team, away = result.away_team;
  const tac = result.tactical_rating || {};

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-widest text-muted">
          Vector Analytics · ‖P‖² = ‖S‖² + ‖L‖²
        </div>
        <span className="chip text-[9px]" title={vm.basis}>ⓘ basis</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {[[home, "home"], [away, "away"]].map(([team, side]: any) => {
          const skill = vm[`${side}_skill_score`];
          const luck = vm[`${side}_luck_mu_bias`];
          return (
            <div key={team} className="rounded-xl border border-white/5 bg-white/3 p-3">
              <div className="mb-2 truncate font-display text-[12px] font-bold text-stadium">
                {team}
              </div>

              {/* Skill bar */}
              <div className="mb-2">
                <div className="mb-1 flex justify-between text-[10px]">
                  <span className="text-success">Skill (S)</span>
                  <span className="tabnum font-semibold text-success">{pctStr(skill)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5">
                  <motion.div className="h-1.5 rounded-full bg-success"
                    initial={{ width: 0 }} animate={{ width: `${(skill ?? 0) * 100}%` }}
                    transition={{ duration: 0.8 }} />
                </div>
              </div>

              {/* Luck bias */}
              <div className="mb-2">
                <div className="mb-1 flex justify-between text-[10px]">
                  <span className="text-chaos">Luck bias (μ)</span>
                  <span className={`tabnum font-semibold ${luck == null ? "text-muted" : luck >= 0 ? "text-chaos" : "text-danger"}`}>
                    {signed(luck)}
                  </span>
                </div>
                {luck == null ? (
                  <div className="text-[9px] text-muted/70">no DC-model signal for this team</div>
                ) : (
                  <div className="text-[9px] text-muted/70">
                    {luck >= 0 ? "over-performing" : "under-performing"} the model's own retrospective goal estimate
                  </div>
                )}
              </div>

              {/* Tactical rating (heuristic proxy) */}
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-muted" title="Heuristic proxy — not a tracking-data measurement (no PPDA/pressing data source exists)">
                  Tactical intensity ⓘ
                </span>
                <span className="tabnum font-semibold text-gold">{pctStr(tac[team])}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* shared chaos/volatility */}
      <div className="rounded-xl bg-chaos/5 border border-chaos/15 p-3">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-chaos/90">σ chaos (environmental volatility)</span>
          <span className="tabnum font-bold text-chaos">{vm.luck_sigma_chaos?.toFixed(3) ?? "—"}</span>
        </div>
        {result.chaos_events && (
          <div className="mt-1 text-[10px] text-muted">
            {(result.chaos_events.run_rate * 100).toFixed(1)}% of {result.n_sims?.toLocaleString()} simulated
            runs exceeded the {result.chaos_events.threshold_sigma}σ chaos-event threshold
            (margin σ = {result.chaos_events.margin_sigma?.toFixed(2)})
          </div>
        )}
      </div>
    </div>
  );
}
