"use client";
import useSWR from "swr";
import Link from "next/link";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Flag } from "@/components/ui";

const fetcher = (p: string) => api(p);
const ET = "America/New_York";
const fmt = (iso: string) =>
  new Date(iso).toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", timeZone: ET,
  });
const pctStr = (x?: number) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

export default function KnockoutPage() {
  const { data, error } = useSWR("/api/knockout", fetcher);

  if (error) return <div className="card text-live">Knockout schedule offline.</div>;
  if (!data) return <div className="h-80 animate-pulse rounded-2xl bg-white/5" />;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Road to the Final · World Cup 2026</h1>
          <p className="text-xs text-muted">Knockout stage · Jun 28 – Jul 19 · times ET</p>
        </div>
      </div>

      {data.projected && data.podium?.champion && <Podium podium={data.podium} />}

      <p className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-[13px] leading-snug text-muted">
        {data.projected
          ? (data.modal_path_note ?? "Projected bracket from current standings.") +
            " 🏆 % is a team's chance to win the whole tournament; ↗ % is its Monte-Carlo chance to clear that round. Tap any match for its full story — both sides' road here, the key moments, and the projected game flow."
          : "Official knockout schedule. Slots resolve once the group stage completes."}
      </p>

      {/* Round-by-round sections: R32 → R16 → QF → SF → 3rd → Final */}
      <div className="space-y-8">
        {data.rounds.map((r: any, ri: number) => (
          <section key={r.round}>
            <div className="mb-3 flex items-center gap-3">
              <h2 className="font-display text-lg font-bold text-gold">{r.round}</h2>
              <div className="h-px flex-1 bg-gradient-to-r from-gold/40 to-transparent" />
              <span className="text-[11px] text-muted">{r.matches.length} ties</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {r.matches.map((m: any, i: number) => (
                <MatchCard key={m.id} m={m} delay={ri * 0.04 + i * 0.015} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

/* ── one match card → links to the full match page ──────────────────────── */
function MatchCard({ m, delay }: { m: any; delay: number }) {
  const resolved = m.resolved;
  const homeWin = resolved && m.predicted_winner === m.home_team;
  const wp = m.win_probability ? Math.round(m.win_probability * 100) : null;
  const scoreStr = m.predicted_score
    ? (m.shootout ? `${m.predicted_score} · pens` : m.predicted_score)
    : "vs";
  const isFinal = m.round === "Final";

  const inner = (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className={`card h-full p-3 transition ${
        resolved ? "cursor-pointer hover:-translate-y-0.5 hover:border-gold/50" : "opacity-80"} ${
        isFinal ? "border-gold/50 bg-gold/10 shadow-glow" : ""}`}>
      <div className="mb-2 flex items-center justify-between text-[10px] text-muted">
        <span className="chip">Match {m.id}</span>
        <span>{fmt(m.kickoff)}</span>
      </div>

      {resolved ? (
        <>
          <TeamLine name={m.home_team} flag={m.home_flag} win={homeWin}
            title={m.home_title_pct} />
          <div className="my-1 text-center text-[10px] uppercase tracking-widest text-gold/70">
            {scoreStr}
          </div>
          <TeamLine name={m.away_team} flag={m.away_flag} win={!homeWin && resolved}
            title={m.away_title_pct} />

          <div className="mt-2 flex items-center justify-between text-[11px] text-muted">
            <span>win <span className="font-bold text-stadium">{wp}%</span></span>
            {m.confidence != null && <span className="text-gold font-bold">{m.confidence} conf</span>}
          </div>
          {wp != null && (
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gold/80" style={{ width: `${wp}%` }} />
            </div>
          )}
          {m.survival?.advance_stage && (
            <div className="mt-1.5 flex justify-between text-[10px] text-muted"
              title={`Monte-Carlo chance each side reaches the ${m.survival.advance_stage}`}>
              <span>↗ {m.survival.advance_stage}</span>
              <span className="tabular-nums">
                {pctStr(m.survival.home?.advance)} · {pctStr(m.survival.away?.advance)}
              </span>
            </div>
          )}
          <div className="mt-2 text-center text-[10px] font-semibold text-gold/80">
            view match story →
          </div>
        </>
      ) : (
        <div className="space-y-1 font-display text-sm font-semibold">
          <div className="break-words leading-tight">{m.home_label}</div>
          <div className="text-[10px] uppercase tracking-widest text-gold/70">vs</div>
          <div className="break-words leading-tight">{m.away_label}</div>
        </div>
      )}
      <div className="mt-2 text-[10px] text-muted">📍 {m.city}</div>
    </motion.div>
  );

  return resolved
    ? <Link href={`/knockout/${m.id}`} className="block h-full">{inner}</Link>
    : inner;
}

function TeamLine({ name, flag, win, title }:
  { name: string; flag?: string; win: boolean; title?: number }) {
  return (
    <div className={`flex items-center gap-2 rounded-lg px-1.5 py-1 ${win ? "bg-gold/15" : ""}`}>
      <Flag url={flag} name={name} size={20} />
      <span className={`min-w-0 flex-1 break-words font-display text-sm leading-tight ${
        win ? "font-bold text-stadium" : "font-medium"}`}>{name}</span>
      {title != null && (
        <span className="shrink-0 text-[10px] text-muted" title="Chance to win the whole tournament">
          🏆 {pctStr(title)}
        </span>
      )}
    </div>
  );
}

/* ── Podium (unchanged) ──────────────────────────────────────────────────── */
function Podium({ podium }: { podium: any }) {
  const { champion, runner_up, third } = podium;
  return (
    <div className="card bg-gradient-to-b from-gold/10 to-transparent p-5">
      <div className="mb-4 text-center text-[11px] uppercase tracking-widest text-gold/80">
        Projected Final Standing
      </div>
      <div className="flex items-end justify-center gap-3 sm:gap-6">
        <Step place={2} block="h-16 sm:h-20" data={runner_up} medal="🥈" />
        <Step place={1} block="h-24 sm:h-32" data={champion} medal="🏆" big />
        <Step place={3} block="h-10 sm:h-14" data={third} medal="🥉" />
      </div>
    </div>
  );
}

function Step({ place, block, data, medal, big }:
  { place: number; block: string; data: any; medal: string; big?: boolean }) {
  if (!data) return <div className="flex-1" />;
  return (
    <div className="flex flex-1 flex-col items-center gap-2">
      <div className="text-2xl">{medal}</div>
      <Flag url={data.flag} name={data.team} size={big ? 48 : 36} />
      <div className={`text-center font-display leading-tight ${big ? "text-base font-bold text-gold" : "text-sm font-semibold"}`}>
        {data.team}
      </div>
      <div className="text-[10px] text-muted">title {pctStr(data.title_pct)}</div>
      <div className={`w-full rounded-t-lg bg-gradient-to-t from-gold/30 to-gold/10 ${block}`} />
    </div>
  );
}
