"use client";
/* Animated Match Center scoreboard for the tournament's final two ties
 * (Third place, Final) — replaces the plain pre-match hero block on
 * knockout/[id]/page.tsx for those two fixtures only. Every field shown
 * here already existed on that static block; this just restyles it into
 * a broadcast-style scoreboard with a countdown, a two-way animated win
 * bar, and a collapsible regulation/ET/pens breakdown. No new data. */
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Flag, Countdown, ProbBar, ProbRing, isLowConfidence, LowConfidenceTag } from "@/components/ui";
import { useCountUp } from "@/lib/use-count-up";

const ET = "America/New_York";
const fmt = (iso: string) =>
  new Date(iso).toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", timeZone: ET,
  });
const pctStr = (x?: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

export function MatchHero({ m }: { m: any }) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  const homeWin = m.predicted_winner === m.home_team;

  // Two-way, AET+pens-resolved probability that each side advances —
  // knockout ties can't end level, so unlike group-stage ProbBar usage
  // there's no draw outcome here.
  const winProbResolved = m.win_probability ?? 0.5;
  const homeProb = homeWin ? winProbResolved : 1 - winProbResolved;
  const awayProb = 1 - homeProb;
  const homePct = useCountUp(homeProb * 100);
  const awayPct = useCountUp(awayProb * 100);

  const hasTitleOdds = (m.home_title_pct ?? 0) > 0 || (m.away_title_pct ?? 0) > 0;
  const reg = m.prediction ?? {};
  const flowProb = m.flow?.probabilities;

  const scoreLabel = m.shootout
    ? "predicted after pens"
    : (() => {
        const [h, a] = (m.predicted_score ?? "0-0").split("-").map(Number);
        return h === a && m.predicted_winner ? "predicted AET" : "predicted";
      })();

  return (
    <div className="card-broadcast overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-white/[0.04] px-4 py-2.5 text-[11px] text-muted">
        <span className="chip-gold">{m.round} · Match {m.id}</span>
        <span>📍 {m.venue}, {m.city} · {fmt(m.kickoff)}</span>
      </div>

      <div className="flex items-center justify-center border-b border-white/8 bg-white/[0.02] px-4 py-3">
        <Countdown to={m.kickoff} />
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 p-6">
        <TeamHead name={m.home_team} flag={m.home_flag} win={homeWin} titlePct={m.home_title_pct} showTitle={hasTitleOdds} />
        <div className="text-center">
          <div className="font-display text-4xl font-black tabnum text-gold sm:text-5xl">
            {m.predicted_score}
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-widest text-muted">{scoreLabel}</div>
        </div>
        <TeamHead name={m.away_team} flag={m.away_flag} win={!homeWin} titlePct={m.away_title_pct} showTitle={hasTitleOdds} right />
      </motion.div>

      <div className="px-6 pb-5">
        <div className="mb-1.5 flex items-center justify-between text-[11px]">
          <span className={`font-bold tabnum ${homeWin ? "text-success" : "text-muted"}`}>
            {m.home_team} {homePct.toFixed(0)}%
          </span>
          <span className="text-[10px] uppercase tracking-widest text-muted">Win Probability</span>
          <span className={`font-bold tabnum ${!homeWin ? "text-cyan" : "text-muted"}`}>
            {awayPct.toFixed(0)}% {m.away_team}
          </span>
        </div>
        <ProbBar home={homeProb} draw={0} away={awayProb} height={12} />
      </div>

      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-t border-white/10 px-4 py-3 text-sm">
        <span><span className="font-bold text-gold">{m.predicted_winner}</span> advances</span>
        {m.confidence != null && (
          <>
            <span className="text-muted">·</span>
            <span>conf <span className="font-bold">{m.confidence}</span></span>
          </>
        )}
        {isLowConfidence(m) && <LowConfidenceTag confidence={m.confidence} />}
        <button onClick={() => setShowBreakdown((v) => !v)}
          className="ml-1 text-[11px] text-cyan/80 transition hover:text-cyan">
          {showBreakdown ? "Hide breakdown ▲" : "ⓘ Regulation / ET / pens ▼"}
        </button>
      </div>

      <AnimatePresence>
        {showBreakdown && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-white/8 bg-white/[0.02]">
            <div className="space-y-4 px-5 py-4">
              {reg.p_home != null && (
                <div>
                  <div className="mb-1.5 text-[10px] uppercase tracking-widest text-muted">Regulation (90')</div>
                  <ProbBar home={reg.p_home} draw={reg.p_draw ?? 0} away={reg.p_away ?? 0} height={8} />
                  <div className="mt-1 flex justify-between text-[10px] tabnum text-muted">
                    <span>{pctStr(reg.p_home)}</span><span>D {pctStr(reg.p_draw)}</span><span>{pctStr(reg.p_away)}</span>
                  </div>
                </div>
              )}
              {flowProb && (
                <div className="grid grid-cols-2 gap-3 text-[11px] sm:grid-cols-3">
                  <BreakdownStat label="Goes to ET" value={pctStr(flowProb.extra_time)} />
                  <BreakdownStat label="Goes to pens" value={pctStr(flowProb.shootout)} />
                  {flowProb.shootout_winner && (
                    <BreakdownStat label="Pens favourite"
                      value={`${flowProb.shootout_winner.predicted} ${pctStr(
                        Math.max(flowProb.shootout_winner.home ?? 0, flowProb.shootout_winner.away ?? 0)
                      )}`} />
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {m.survival?.advance_stage && (
        <div className="flex justify-center gap-6 border-t border-white/10 px-4 py-2 text-[11px] text-muted">
          <span>↗ reach {m.survival.advance_stage}:</span>
          <span>{m.home_team} <b className="text-stadium">{pctStr(m.survival.home?.advance)}</b></span>
          <span>{m.away_team} <b className="text-stadium">{pctStr(m.survival.away?.advance)}</b></span>
        </div>
      )}
    </div>
  );
}

function TeamHead({ name, flag, win, titlePct, showTitle, right }: {
  name: string; flag?: string; win: boolean; titlePct?: number; showTitle?: boolean; right?: boolean;
}) {
  return (
    <div className={`flex flex-col items-center gap-2 ${right ? "md:items-center" : ""}`}>
      <Flag url={flag} name={name} size={60} />
      <div className={`text-center font-display leading-tight ${win ? "text-lg font-bold text-gold" : "text-base font-semibold text-stadium"}`}>
        {name}
      </div>
      {showTitle && <ProbRing value={titlePct ?? 0} label="Title Odds" color="#FFD700" size={72} />}
    </div>
  );
}

function BreakdownStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/8 bg-white/3 px-3 py-2 text-center">
      <div className="font-display font-bold tabnum text-stadium">{value}</div>
      <div className="mt-0.5 text-[9px] uppercase tracking-wider text-muted">{label}</div>
    </div>
  );
}
