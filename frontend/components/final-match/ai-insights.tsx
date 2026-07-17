"use client";
/* Curated AI insight cards for the final two ties. Every number here is
 * either a real field from the match/team APIs or a clearly-labeled
 * statistical derivation from one (e.g. clean-sheet % via Poisson from a
 * real xG figure). "Expected possession" is deliberately omitted — no
 * pre-match possession prediction exists anywhere in the data model, and
 * fabricating one would read as a model output it isn't. */
import useSWR from "swr";
import { api } from "@/lib/api";
import { Flag } from "@/components/ui";
import { useCountUp } from "@/lib/use-count-up";

const fetcher = (p: string) => api(p);
const pct0 = (x: number) => `${Math.round(x * 100)}%`;

function topBy(players: any[], field: string) {
  return players.reduce((best: any, p: any) =>
    (p[field] ?? -Infinity) > (best?.[field] ?? -Infinity) ? p : best, null);
}

export function AIInsights({ m }: { m: any }) {
  const { data: home } = useSWR(`/api/teams/${encodeURIComponent(m.home_team)}`, fetcher, { revalidateOnFocus: false });
  const { data: away } = useSWR(`/api/teams/${encodeURIComponent(m.away_team)}`, fetcher, { revalidateOnFocus: false });

  const a = m.analysis ?? {};
  const flowProb = m.flow?.probabilities;
  const homeXg = a.expected_goals?.home ?? 0;
  const awayXg = a.expected_goals?.away ?? 0;
  const totalGoals = homeXg + awayXg;

  const homeCleanSheet = Math.exp(-awayXg);
  const awayCleanSheet = Math.exp(-homeXg);
  const cleanSheetTeam = homeCleanSheet >= awayCleanSheet ? m.home_team : m.away_team;
  const cleanSheetVal = Math.max(homeCleanSheet, awayCleanSheet);

  const upsetChance = m.confidence != null ? Math.max(0, 1 - m.confidence / 100) : null;

  const attackers = [
    ...(home?.key_players?.attacking ?? []).map((p: any) => ({ ...p, team: m.home_team, flag: m.home_flag })),
    ...(away?.key_players?.attacking ?? []).map((p: any) => ({ ...p, team: m.away_team, flag: m.away_flag })),
  ];
  const dangerousPlayer = topBy(attackers, "impact");
  const highestXgPlayer = topBy(attackers, "xg");

  const totalGoalsAnim = useCountUp(totalGoals);
  const penaltyAnim = useCountUp((flowProb?.shootout ?? 0) * 100);
  const cleanSheetAnim = useCountUp(cleanSheetVal * 100);
  const upsetAnim = useCountUp((upsetChance ?? 0) * 100);

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-bold">AI Insights</h2>
        <span className="chip text-[10px]">CAI · pre-match</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <InsightTile icon="🥅" label="Penalty Probability"
          value={`${penaltyAnim.toFixed(0)}%`}
          caption="Chance this tie is decided by a shootout" />

        <InsightTile icon="⚽" label="Expected Total Goals"
          value={totalGoalsAnim.toFixed(2)}
          caption={`${homeXg.toFixed(2)} + ${awayXg.toFixed(2)} combined xG`} />

        <InsightTile icon="🧤" label="Clean Sheet Probability"
          value={`${cleanSheetTeam} ${cleanSheetAnim.toFixed(0)}%`}
          caption="Derived from expected goals (Poisson P(0))" />

        {upsetChance != null && (
          <InsightTile icon="⚡" label="Upset Chance"
            value={`${upsetAnim.toFixed(0)}%`}
            caption={`Model confidence is ${m.confidence}/100 — lower confidence, higher upset risk`} />
        )}

        {dangerousPlayer && (
          <PlayerTile icon="🔥" label="Most Dangerous Player" player={dangerousPlayer} stat={`${dangerousPlayer.impact} impact`} />
        )}

        {highestXgPlayer && (
          <PlayerTile icon="🎯" label="Highest xG Player" player={highestXgPlayer} stat={`${highestXgPlayer.xg} xG`} />
        )}
      </div>
    </section>
  );
}

function InsightTile({ icon, label, value, caption }: { icon: string; label: string; value: string; caption: string }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-cyan/20 bg-ink-2/80 p-4">
      <div className="pointer-events-none absolute right-0 top-0 h-20 w-20 rounded-full bg-cyan/10 blur-2xl" />
      <div className="relative z-10">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="text-[10px] uppercase tracking-widest text-cyan/80">{label}</span>
        </div>
        <div className="font-display text-2xl font-bold tabnum text-stadium">{value}</div>
        <p className="mt-1 text-[11px] leading-snug text-muted">{caption}</p>
      </div>
    </div>
  );
}

function PlayerTile({ icon, label, player, stat }: { icon: string; label: string; player: any; stat: string }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-gold/20 bg-ink-2/80 p-4">
      <div className="pointer-events-none absolute right-0 top-0 h-20 w-20 rounded-full bg-gold/10 blur-2xl" />
      <div className="relative z-10">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="text-[10px] uppercase tracking-widest text-gold/80">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <Flag url={player.flag} name={player.team} size={18} />
          <span className="font-display text-base font-bold text-stadium">{player.name}</span>
        </div>
        <p className="mt-1 text-[11px] leading-snug text-muted">{player.team} · {stat}</p>
      </div>
    </div>
  );
}
