"use client";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api, pct } from "@/lib/api";
import { SectionHeader, Flag } from "@/components/ui";

const fetcher = (p: string) => api(p);

export default function GroupsPage() {
  const { data, error } = useSWR("/api/simulate/groups", fetcher);
  if (error) return (
    <div className="card-broadcast flex items-center gap-3 text-danger">
      <span className="text-2xl">⚡</span> Run the simulator first.
    </div>
  );
  if (!data) return <div className="h-80 animate-pulse rounded-2xl bg-ink-2" />;

  return (
    <div className="space-y-6">
      <SectionHeader title="GROUP STANDINGS"
        sub="Played results · advancement % from 50 000 Monte Carlo simulations" />
      <p className="text-sm text-muted">
        Top two from each group advance automatically. Eight best third-placed
        teams also qualify. <span className="text-teal">Q</span> = projected to advance.
        <span className="text-stadium"> Pts</span> = earned so far ·
        <span className="text-gold"> Proj</span> = projected final points (incl. remaining games) ·
        <span className="text-cyan"> Adv%</span> = simulated chance to advance. A strong side can sit
        on few points yet show a high Proj/Adv% if its remaining fixtures are favourable.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Object.entries(data).map(([g, teams]: any, gi: number) => (
          <motion.div key={g} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: gi * 0.04 }} className="card-broadcast overflow-hidden">
            <div className="mb-3 flex items-center justify-between">
              <span className="font-display text-sm font-bold uppercase tracking-widest text-stadium">
                Group {g}
              </span>
              <span className="chip-cyan text-[9px]">{teams[0]?.mp ?? 0} MP</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[340px] text-sm">
                <thead>
                  <tr className="border-b border-line/60 text-[10px] uppercase tracking-wider text-muted">
                    <th className="py-1.5 pr-1 text-left font-medium">#</th>
                    <th className="py-1.5 pl-1 text-left font-medium">Team</th>
                    <th className="px-1.5 py-1.5 text-center font-medium" title="Matches played">MP</th>
                    <th className="px-1 py-1.5 text-center font-medium" title="Won">W</th>
                    <th className="px-1 py-1.5 text-center font-medium" title="Drawn">D</th>
                    <th className="px-1 py-1.5 text-center font-medium" title="Lost">L</th>
                    <th className="px-1.5 py-1.5 text-center font-medium" title="Goal difference">GD</th>
                    <th className="px-1.5 py-1.5 text-center font-semibold text-stadium" title="Points so far (played matches)">Pts</th>
                    <th className="px-1.5 py-1.5 text-center font-medium text-gold/80" title="Projected final points: points so far + expected points from remaining group games">Proj</th>
                    <th className="py-1.5 pl-1.5 text-right font-medium" title="Advance probability (forward-looking, from 50k Monte Carlo sims)">Adv%</th>
                  </tr>
                </thead>
                <tbody>
                  {teams.map((t: any, i: number) => {
                    const q = i < 2;
                    return (
                      <tr key={t.team}
                        className={`border-b border-line/30 ${q ? "" : "text-muted"}
                          ${i === 0 ? "border-l-2 border-l-gold"
                            : i === 1 ? "border-l-2 border-l-cyan" : ""}`}>
                        <td className={`py-2 pr-1 text-left text-[11px] font-bold ${q ? "text-teal" : "text-muted/40"}`}>
                          {i + 1}
                        </td>
                        <td className="py-2 pl-1">
                          <span className="flex items-center gap-1.5">
                            <Flag url={t.flag_url} name={t.team} size={16} />
                            <span className={`min-w-0 break-words leading-tight ${q ? "font-semibold text-stadium" : ""}`}>
                              {t.team}
                            </span>
                            {q && <span className="chip-gold shrink-0 text-[8px]">Q</span>}
                          </span>
                        </td>
                        <td className="px-1.5 py-2 text-center tabnum">{t.mp}</td>
                        <td className="px-1 py-2 text-center tabnum">{t.w}</td>
                        <td className="px-1 py-2 text-center tabnum">{t.d}</td>
                        <td className="px-1 py-2 text-center tabnum">{t.l}</td>
                        <td className="px-1.5 py-2 text-center tabnum">
                          {t.gd > 0 ? `+${t.gd}` : t.gd}
                        </td>
                        <td className="px-1.5 py-2 text-center font-display font-bold tabnum text-stadium">
                          {t.pts}
                        </td>
                        <td className="px-1.5 py-2 text-center font-display tabnum text-gold/90 text-xs"
                          title="Projected final points (incl. remaining games)">
                          {t.proj_pts != null ? t.proj_pts.toFixed(1) : "—"}
                        </td>
                        <td className="py-2 pl-1.5 text-right font-bold tabnum text-cyan text-xs">
                          {pct(t.advance_prob)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
