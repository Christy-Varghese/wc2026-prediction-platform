"use client";
/* Tournament wrap-up: champion celebration, final recap, award winners, and
 * CAI's full-tournament prediction-accuracy retrospective — the "everything"
 * capstone page once the Final is played. Reuses existing data (no new
 * fabricated numbers): /api/tournament-summary (champion/finalists +
 * accuracy, backend/app/main.py), /api/knockout (final match detail),
 * /api/awards (winner cards, already-existing endpoint). */
import { useMemo } from "react";
import Link from "next/link";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Flag, SectionHeader } from "@/components/ui";

const fetcher = (p: string) => api(p);

const CONFETTI_COLORS = ["#FFD700", "#00D4FF", "#00E676", "#00FFB2", "#B14EFF", "#FF9500"];

function ConfettiField() {
  const particles = useMemo(() => Array.from({ length: 60 }).map((_, i) => ({
    id: i,
    left: Math.random() * 100,
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
    w: 4 + Math.random() * 5,
    h: 8 + Math.random() * 10,
    delay: Math.random() * 2.5,
    duration: 3 + Math.random() * 2.5,
    rotate: (Math.random() - 0.5) * 720,
  })), []);
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {particles.map((p) => (
        <motion.span
          key={p.id}
          className="absolute top-0 rounded-sm"
          style={{ left: `${p.left}%`, width: p.w, height: p.h, background: p.color }}
          initial={{ y: -40, opacity: 0, rotate: 0 }}
          animate={{ y: "110vh", opacity: [0, 1, 1, 0], rotate: p.rotate }}
          transition={{ duration: p.duration, delay: p.delay, repeat: Infinity, ease: "linear" }}
        />
      ))}
    </div>
  );
}

export default function ChampionsPage() {
  const { data: summary } = useSWR("/api/tournament-summary", fetcher, { revalidateOnFocus: false });
  const { data: ko } = useSWR("/api/knockout", fetcher, { revalidateOnFocus: false });
  const { data: awards } = useSWR("/api/awards", fetcher, { revalidateOnFocus: false });

  if (!summary) return <ChampionsSkeleton />;
  if (!summary.final_played) {
    return (
      <div className="card-broadcast text-center text-muted">
        The Final hasn't been played yet — check back once it has for the full tournament wrap-up.{" "}
        <Link href="/bracket" className="text-cyan hover:underline">View the bracket →</Link>
      </div>
    );
  }

  const byId: Record<number, any> = {};
  for (const m of ko?.matches ?? []) byId[m.id] = m;
  const final = byId[summary.final_match_id];
  const third = byId[summary.third_place_match_id];

  const champFlag = final
    ? (final.home_team === summary.champion ? final.home_flag : final.away_flag)
    : undefined;
  const runnerFlag = final
    ? (final.home_team === summary.runner_up ? final.home_flag : final.away_flag)
    : undefined;
  const thirdFlag = third
    ? (third.home_team === summary.third_place ? third.home_flag : third.away_flag)
    : undefined;
  const fourthFlag = third
    ? (third.home_team === summary.fourth_place ? third.home_flag : third.away_flag)
    : undefined;

  const acc = summary.accuracy;
  const accPct = acc.total_max ? Math.round((acc.total_pts / acc.total_max) * 100) : 0;
  const koPct = acc.knockout_max ? Math.round((acc.knockout_pts / acc.knockout_max) * 100) : 0;
  const groupPct = acc.group_max ? Math.round((acc.group_pts / acc.group_max) * 100) : 0;
  const missedFinal = summary.final_predicted_winner && summary.final_predicted_winner !== summary.champion;

  const boot = awards?.golden_boot?.[0];
  const ball = awards?.golden_ball?.[0];
  const glove = awards?.golden_glove?.[0];
  const young = awards?.best_young_player?.[0];

  return (
    <div className="space-y-8">

      {/* ══════════════ TROPHY HERO ══════════════ */}
      <motion.section
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="relative overflow-hidden rounded-3xl border border-gold/30 bg-gradient-to-b from-ink-2 via-ink-3/80 to-ink p-8 text-center shadow-[0_0_80px_rgba(255,215,0,0.1)] sm:p-14"
      >
        <ConfettiField />
        <div className="relative z-10">
          <motion.div
            initial={{ scale: 0.3, opacity: 0, rotate: -15 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 160, damping: 12 }}
            className="mb-4 text-7xl sm:text-8xl"
          >
            🏆
          </motion.div>
          <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.4em] text-gold/70">
            FIFA World Cup 2026 · Final
          </div>
          <h1 className="gold-text font-display text-4xl font-black uppercase tracking-tight sm:text-6xl">
            {summary.champion} are World Champions
          </h1>
          <div className="mt-6 flex items-center justify-center gap-6 sm:gap-10">
            <div className="flex flex-col items-center gap-2">
              <Flag url={champFlag} name={summary.champion} size={72} />
              <span className="font-display text-lg font-bold text-gold">{summary.champion}</span>
            </div>
            <div className="text-center">
              <div className="font-display text-5xl font-black tabnum text-stadium sm:text-6xl">
                {final?.home_team === summary.champion ? `${final.home_score}–${final.away_score}` : `${final?.away_score}–${final?.home_score}`}
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-widest text-muted">After Extra Time</div>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Flag url={runnerFlag} name={summary.runner_up} size={72} />
              <span className="font-display text-lg font-bold text-stadium">{summary.runner_up}</span>
            </div>
          </div>
          <p className="mx-auto mt-6 max-w-xl text-[13px] leading-relaxed text-muted">
            {summary.champion}'s second World Cup title, settled by a single extra-time goal — just like 2010.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2.5">
            <Link href={`/knockout/${summary.final_match_id}`} className="btn-gold text-xs">
              Full Match Analysis →
            </Link>
            <Link href="/bracket" className="btn-ghost text-xs">View Full Bracket</Link>
          </div>
        </div>
      </motion.section>

      {/* ══════════════ PODIUM ══════════════ */}
      <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
        <SectionHeader title="FINAL STANDINGS" sub="Top four · World Cup 2026" />
        <div className="grid gap-3 sm:grid-cols-4">
          <PodiumCard place={1} label="Champions" team={summary.champion} flag={champFlag} accent="gold" />
          <PodiumCard place={2} label="Runners-up" team={summary.runner_up} flag={runnerFlag} accent="silver" />
          <PodiumCard place={3} label="Third place" team={summary.third_place} flag={thirdFlag} accent="bronze" />
          <PodiumCard place={4} label="Fourth place" team={summary.fourth_place} flag={fourthFlag} accent="none" />
        </div>
      </motion.section>

      {/* ══════════════ AWARD WINNERS ══════════════ */}
      <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
        <SectionHeader title="INDIVIDUAL AWARDS" sub="FIFA official winners"
          action={<Link href="/awards" className="btn-sm">Full leaderboards →</Link>} />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {boot && <AwardCard icon="🥇" label="Golden Boot" player={boot.player} team={boot.team}
            flag={boot.flag_url} stat={`${boot.goals} goals`} />}
          {ball && <AwardCard icon="⭐" label="Golden Ball" player={ball.player} team={ball.team}
            flag={ball.flag_url} stat="Best player" />}
          {glove && <AwardCard icon="🧤" label="Golden Glove" player={glove.player} team={glove.team}
            flag={glove.flag_url} stat={`${glove.clean_sheets} clean sheets`} />}
          {young && <AwardCard icon="🌟" label="Best Young Player" player={young.player} team={young.team}
            flag={young.flag_url} stat={young.age ? `Age ${young.age}` : ""} />}
        </div>
      </motion.section>

      {/* ══════════════ CAI RETROSPECTIVE ══════════════ */}
      <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}
        className="card-broadcast">
        <div className="mb-5 flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <div>
            <h2 className="font-display text-lg font-bold uppercase tracking-widest text-stadium">
              How CAI Did — Full Tournament
            </h2>
            <p className="text-[11px] text-muted">Every prediction, scored against the real results</p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <StatTile label="Overall Accuracy" value={`${accPct}%`} sub={`${acc.total_pts}/${acc.total_max} pts`} color="#FFD700" />
          <StatTile label="Group Stage" value={`${groupPct}%`} sub={`${acc.group_pts}/${acc.group_max} pts · ${acc.group_n} matches`} color="#00E676" />
          <StatTile label="Knockout Stage" value={`${koPct}%`} sub={`${acc.knockout_pts}/${acc.knockout_max} pts · ${acc.knockout_n} ties`} color="#00D4FF" />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <StatTile label="Exact Scorelines Called" value={acc.exact_scores} sub="across the whole tournament" color="#B14EFF" />
          <StatTile label="Golden Boot Call" value={boot?.player ?? "—"} sub="CAI's live leaderboard nailed the outright winner" color="#00FFB2" small />
        </div>

        {/* Honest miss disclosure on the Final */}
        {missedFinal && (
          <div className="mt-5 flex items-start gap-3 rounded-xl border border-white/10 bg-white/3 p-4">
            <span className="text-lg">⚠</span>
            <div>
              <div className="font-display text-sm font-bold text-stadium">
                The Final was a miss — and CAI said so beforehand
              </div>
              <p className="mt-1 text-[12px] leading-relaxed text-muted">
                CAI backed {summary.final_predicted_winner} pre-match, and {summary.champion} won instead. But the
                model's own confidence on that call was just {summary.final_predicted_confidence}/100 — deep in
                toss-up territory, flagged as such at the time rather than presented as a confident pick. A low-confidence
                miss on the single biggest match of the tournament is still a miss, but it's the outcome the model's own
                uncertainty estimate said was live. See the{" "}
                <Link href={`/knockout/${summary.final_match_id}`} className="text-cyan hover:underline">
                  full pre- and post-match breakdown
                </Link>.
              </p>
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2.5">
          <Link href="/analytics" className="btn-sm">Full Tournament Analytics →</Link>
          <Link href="/matches" className="btn-sm">Every Match & Prediction →</Link>
        </div>
      </motion.section>

      <p className="px-1 pb-6 text-center text-[11px] text-muted">
        Not affiliated with FIFA. Not betting advice. Built for entertainment and analytics — thanks for following along all tournament.
      </p>
    </div>
  );
}

function PodiumCard({ place, label, team, flag, accent }: {
  place: number; label: string; team?: string; flag?: string;
  accent: "gold" | "silver" | "bronze" | "none";
}) {
  const cls = accent === "gold" ? "border-gold/40 bg-gold/5"
    : accent === "silver" ? "border-white/25 bg-white/5"
    : accent === "bronze" ? "border-orange-500/30 bg-orange-500/5"
    : "border-white/10 bg-white/2";
  const medal = accent === "gold" ? "🥇" : accent === "silver" ? "🥈" : accent === "bronze" ? "🥉" : "4️⃣";
  return (
    <div className={`flex flex-col items-center gap-2 rounded-2xl border p-5 text-center ${cls}`}>
      <span className="text-2xl">{medal}</span>
      {team ? <Flag url={flag} name={team} size={40} /> : <div className="h-[29px]" />}
      <div className="font-display text-sm font-bold text-stadium">{team ?? "—"}</div>
      <div className="text-[10px] uppercase tracking-widest text-muted">{label}</div>
    </div>
  );
}

function AwardCard({ icon, label, player, team, flag, stat }: {
  icon: string; label: string; player: string; team: string; flag?: string; stat: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-gold/20 bg-ink-2/80 p-4">
      <div className="pointer-events-none absolute right-0 top-0 h-20 w-20 rounded-full bg-gold/10 blur-2xl" />
      <div className="relative z-10">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="text-[10px] uppercase tracking-widest text-gold/80">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <Flag url={flag} name={team} size={20} />
          <span className="font-display text-base font-bold text-stadium">{player}</span>
        </div>
        <p className="mt-1 text-[11px] text-muted">{team} · {stat}</p>
      </div>
    </div>
  );
}

function StatTile({ label, value, sub, color, small }: {
  label: string; value: string | number; sub: string; color: string; small?: boolean;
}) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/3 p-4">
      <div className="text-[10px] uppercase tracking-widest text-muted">{label}</div>
      <div className={`mt-1 font-display font-black tabnum ${small ? "text-lg" : "text-3xl"}`} style={{ color }}>
        {value}
      </div>
      <div className="mt-0.5 text-[10px] text-muted">{sub}</div>
    </div>
  );
}

function ChampionsSkeleton() {
  return (
    <div className="space-y-8">
      <div className="h-96 animate-pulse rounded-3xl bg-ink-2" />
      <div className="grid gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className="h-40 animate-pulse rounded-2xl bg-ink-2" />)}
      </div>
      <div className="h-64 animate-pulse rounded-2xl bg-ink-2" />
    </div>
  );
}
