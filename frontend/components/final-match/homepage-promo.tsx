"use client";
/* Homepage spotlight for the tournament's last two fixtures — surfaces the
 * new interactive Match Center (score predictor, head-to-head, AI insights,
 * fan vote, share) that otherwise only lives on /knockout/[id]. Renders
 * nothing if Third place/Final aren't in the knockout payload (keeps the
 * homepage safe outside this exact window of the tournament). */
import Link from "next/link";
import { motion } from "framer-motion";
import { Flag, Countdown, ProbBar } from "@/components/ui";
import { FanVote } from "@/components/final-match/fan-vote";

export function FinalStretchPromo({ matches }: { matches: any[] | undefined }) {
  if (!matches?.length) return null;
  const thirdPlace = matches.find((m: any) => m.round === "Third place");
  const final = matches.find((m: any) => m.round === "Final");
  if (!thirdPlace && !final) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15, ease: "easeOut" }}
      className="relative overflow-hidden rounded-3xl border border-gold/25
                 bg-gradient-to-br from-ink-2 via-ink-3/70 to-ink p-6 shadow-[0_0_60px_rgba(255,215,0,0.08)] sm:p-8"
    >
      {/* gold floodlight beams */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 left-1/5 h-96 w-px bg-gradient-to-b from-gold/25 to-transparent" />
        <div className="absolute -top-32 right-1/5 h-96 w-px bg-gradient-to-b from-gold/15 to-transparent" />
        <div className="absolute right-0 top-0 h-64 w-64 rounded-full bg-gold/10 blur-3xl" />
      </div>

      <div className="relative z-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="animate-float text-3xl">🏆</span>
            <div>
              <h2 className="gold-text font-display text-2xl font-extrabold uppercase tracking-tight sm:text-3xl">
                The Final Countdown
              </h2>
              <p className="text-[12px] text-muted">Two matches left. Make your call, then see if CAI agrees.</p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {thirdPlace && <PromoMatchCard m={thirdPlace} />}
          {final && <PromoMatchCard m={final} highlight />}
        </div>

        {(thirdPlace || final) && (
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {thirdPlace && <FanVote m={thirdPlace} />}
            {final && <FanVote m={final} />}
          </div>
        )}
      </div>
    </motion.section>
  );
}

function PromoMatchCard({ m, highlight }: { m: any; highlight?: boolean }) {
  const homeWin = m.predicted_winner === m.home_team;
  const winProbResolved = m.win_probability ?? 0.5;
  const homeProb = homeWin ? winProbResolved : 1 - winProbResolved;
  const awayProb = 1 - homeProb;

  return (
    <Link href={`/knockout/${m.id}`}
      className={`group relative overflow-hidden rounded-2xl border p-5 transition-all duration-200
        ${highlight
          ? "border-gold/40 bg-gradient-to-br from-gold/[0.06] to-transparent hover:border-gold/70 hover:shadow-glow-gold"
          : "border-white/10 bg-white/[0.02] hover:border-cyan/40 hover:shadow-glow"}`}>
      <div className="mb-3 flex items-center justify-between">
        <span className={highlight ? "chip-gold text-[10px] uppercase tracking-wider" : "chip-cyan text-[10px] uppercase tracking-wider"}>
          {m.round}
        </span>
        <Countdown to={m.kickoff} compact />
      </div>

      <div className="flex items-center justify-between gap-2">
        <TeamMini name={m.home_team} flag={m.home_flag} lead={homeWin} prob={homeProb} />
        <span className="font-display text-[11px] font-bold text-muted/60">VS</span>
        <TeamMini name={m.away_team} flag={m.away_flag} lead={!homeWin} prob={awayProb} right />
      </div>

      <div className="mt-3">
        <ProbBar home={homeProb} draw={0} away={awayProb} height={6} />
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px]">
        <span className="text-muted">📍 {m.city}</span>
        <span className="font-display font-bold text-gold opacity-80 transition group-hover:opacity-100 group-hover:underline">
          Predict &amp; Vote →
        </span>
      </div>
    </Link>
  );
}

function TeamMini({ name, flag, lead, prob, right }: {
  name: string; flag?: string; lead: boolean; prob: number; right?: boolean;
}) {
  return (
    <div className={`flex flex-1 flex-col items-center gap-1 ${right ? "" : ""}`}>
      <Flag url={flag} name={name} size={30} />
      <span className={`text-center font-display text-[12px] font-bold leading-tight ${lead ? "text-gold" : "text-stadium"}`}>
        {name}
      </span>
      <span className={`text-[10px] font-bold tabnum ${lead ? "text-gold" : "text-muted"}`}>
        {Math.round(prob * 100)}%
      </span>
    </div>
  );
}
