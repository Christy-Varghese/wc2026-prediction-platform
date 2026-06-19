"use client";
import useSWR from "swr";
import Link from "next/link";
import { motion } from "framer-motion";
import { api, pct0 } from "@/lib/api";
import { MatchCard, Flag, ProbBar, Countdown, LiveBadge, SectionHeader } from "@/components/ui";

const fetcher = (p: string) => api(p);

export default function LiveCenter() {
  const { data, error } = useSWR("/api/matches?upcoming=true&limit=18", fetcher);
  if (error) return (
    <div className="card-broadcast flex items-center gap-3 text-danger">
      <span className="text-2xl">⚡</span> Live center offline.
    </div>
  );
  if (!data) return <div className="h-80 animate-pulse rounded-3xl bg-ink-2" />;

  const [next, ...rest] = data;
  return (
    <div className="space-y-8">
      <SectionHeader title="LIVE CENTER"
        sub="Upcoming fixtures · real-time predictions"
        action={<LiveBadge label="LIVE DATA" color="danger" />} />

      {/* up-next hero */}
      {next && (
        <motion.section
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-3xl border border-danger/30 bg-gradient-to-br from-ink-2 via-ink-3/80 to-ink p-7 shadow-[0_0_60px_rgba(255,77,77,0.06)] sm:p-10"
        >
          {/* live pulse beams */}
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -top-32 left-1/2 h-96 w-px bg-gradient-to-b from-danger/20 to-transparent" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_50%_-10%,rgba(255,77,77,0.04),transparent)]" />
          </div>

          <div className="relative z-10">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3 text-[11px] text-muted">
              <div className="flex items-center gap-3">
                <LiveBadge label="UP NEXT" color="danger" />
                <span className="chip-cyan font-display uppercase tracking-widest">
                  GROUP {next.group}
                </span>
              </div>
              <span className="font-display uppercase tracking-[0.2em]">
                🏟 {next.venue} · {next.city}
              </span>
            </div>

            <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-[1fr_auto_1fr] sm:gap-6">
              <LiveTeam name={next.home_team} flag={next.home_flag} prob={next.p_home}
                side="home" color="text-success" />
              <div className="flex flex-col items-center gap-3 sm:gap-4">
                <Countdown to={next.kickoff} />
                <span className="chip text-xs">Draw {pct0(next.p_draw)}</span>
              </div>
              <LiveTeam name={next.away_team} flag={next.away_flag} prob={next.p_away}
                side="away" color="text-cyan" />
            </div>

            <div className="mt-8">
              <ProbBar home={next.p_home} draw={next.p_draw} away={next.p_away} height={8} />
              <div className="mt-3 flex justify-end">
                <Link href={`/matches/${next.id}`} className="btn-gold text-xs">
                  Open Match Center →
                </Link>
              </div>
            </div>
          </div>
        </motion.section>
      )}

      {/* upcoming grid */}
      <section>
        <SectionHeader title="UPCOMING FIXTURES" sub="All scheduled matches" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rest.map((m: any, i: number) => (
            <motion.div key={m.id}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.04 }}>
              <MatchCard m={m} />
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}

function LiveTeam({ name, flag, prob, side, color }:
  { name: string; flag?: string; prob: number; side: "home" | "away"; color: string }) {
  const rev = side === "away";
  return (
    <div className={`flex min-w-0 items-center gap-3 sm:gap-4 ${rev ? "flex-row-reverse text-right" : ""}`}>
      <Flag url={flag} name={name} size={56} />
      <div className="min-w-0">
        <div className="break-words font-display text-lg font-bold leading-tight text-stadium sm:text-xl">{name}</div>
        <div className={`font-display text-3xl font-extrabold tabnum ${color}`}>{pct0(prob)}</div>
      </div>
    </div>
  );
}

