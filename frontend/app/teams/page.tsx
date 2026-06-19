"use client";
import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Flag, SectionHeader } from "@/components/ui";

const fetcher = (p: string) => api(p);

const GROUPS = "ABCDEFGHIJKL".split("");

export default function TeamsPage() {
  const { data, error } = useSWR("/api/teams", fetcher);
  const [group, setGroup] = useState("");
  const [search, setSearch] = useState("");

  if (error) return (
    <div className="card-broadcast flex items-center gap-3 text-danger">
      <span className="text-2xl">⚡</span> Backend unreachable.
    </div>
  );
  if (!data) return <TeamsSkeleton />;

  const sorted = [...data].sort((a: any, b: any) => a.fifa_rank - b.fifa_rank);
  const filtered = sorted.filter((t: any) =>
    (!group || t.group === group) &&
    (!search || t.name.toLowerCase().includes(search.toLowerCase()))
  );

  // Tier labels by Elo
  const getTier = (elo: number) =>
    elo >= 2000 ? { label: "Elite", color: "text-gold" } :
    elo >= 1850 ? { label: "Contender", color: "text-cyan" } :
    elo >= 1700 ? { label: "Solid", color: "text-teal" } :
    { label: "Underdog", color: "text-muted" };

  return (
    <div className="space-y-6">
      <SectionHeader title="NATIONS" sub={`${filtered.length} teams · FIFA World Cup 2026`} />

      {/* filter bar */}
      <div className="card-broadcast flex flex-wrap items-center gap-3 py-4">
        <button onClick={() => setGroup("")}
          className={`chip cursor-pointer text-xs transition hover:border-cyan/50 ${!group ? "chip-cyan" : ""}`}>
          All Groups
        </button>
        {GROUPS.map((g) => (
          <button key={g} onClick={() => setGroup(group === g ? "" : g)}
            className={`chip cursor-pointer text-xs transition hover:border-cyan/50 ${group === g ? "chip-cyan" : ""}`}>
            Grp {g}
          </button>
        ))}
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search team…"
          className="min-w-[160px] flex-1 rounded-lg border border-white/10 bg-ink-3 px-3 py-1.5 text-sm placeholder:text-muted focus:border-cyan/40 focus:outline-none focus:ring-1 focus:ring-cyan/20" />
      </div>

      {/* team grid */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((t: any, i: number) => {
          const tier = getTier(t.elo);
          const strengthW = Math.min(100, Math.max(0, ((t.strength_index - 30) / 70) * 100));
          return (
            <motion.div key={t.name}
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.025 }}>
              <Link href={`/teams/${encodeURIComponent(t.name)}`}
                className="card-broadcast match-card-hover group flex items-center gap-4">
                {/* flag */}
                <div className="relative shrink-0">
                  <Flag url={t.flag_url} name={t.name} size={44} />
                  <span className="absolute -bottom-1 -right-1 rounded-full bg-ink-3 px-1 text-[9px] font-bold text-muted border border-white/10">
                    #{t.fifa_rank}
                  </span>
                </div>

                {/* info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 leading-tight">
                    <span className="min-w-0 break-words leading-tight font-display font-semibold text-stadium">{t.name}</span>
                    <span className={`text-[10px] font-bold ${tier.color} shrink-0`}>{tier.label}</span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
                    <span className="chip-cyan text-[9px]">GRP {t.group}</span>
                    <span>Elo {t.elo}</span>
                  </div>
                  {/* strength bar */}
                  <div className="mt-2 h-1.5 w-full rounded-full bg-white/5">
                    <motion.div
                      className="h-1.5 rounded-full bg-gradient-to-r from-cyan/60 to-teal/60"
                      initial={{ width: 0 }}
                      animate={{ width: `${strengthW}%` }}
                      transition={{ duration: 0.6, delay: i * 0.025 }} />
                  </div>
                </div>

                {/* strength index */}
                <div className="text-right shrink-0">
                  <div className="font-display text-xl font-bold tabnum text-cyan">{t.strength_index}</div>
                  <div className="text-[10px] text-muted">Strength</div>
                </div>
              </Link>
            </motion.div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-muted py-8">No teams match the filter.</p>
      )}
    </div>
  );
}

function TeamsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-12 w-64 animate-pulse rounded-lg bg-ink-2" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(12)].map((_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-2xl bg-ink-2" />
        ))}
      </div>
    </div>
  );
}

