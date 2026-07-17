"use client";
/* Fan voting for the final two ties. One vote per browser (localStorage
 * dedupe, matching the brief's ask), aggregate counts from Supabase — same
 * `supabase.from(...).insert(...)` pattern lib/supabase.ts already uses for
 * the feedback widget. Degrades gracefully if the `votes` table hasn't
 * been created yet, rather than crashing the section. */
import { useEffect, useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { Flag } from "@/components/ui";
import { getVoteCounts, submitVote } from "@/lib/supabase";

const votedKey = (matchId: number | string) => `voted_${matchId}`;

export function FanVote({ m }: { m: any }) {
  const [voted, setVoted] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [voteError, setVoteError] = useState(false);

  const { data: counts, mutate, error } = useSWR(
    `votes_${m.id}`,
    () => getVoteCounts(m.id, [m.home_team, m.away_team]),
    { refreshInterval: 20000, revalidateOnFocus: true, shouldRetryOnError: false }
  );

  useEffect(() => {
    setVoted(window.localStorage.getItem(votedKey(m.id)));
  }, [m.id]);

  async function handleVote(choice: string) {
    if (voted || submitting || error) return;
    setSubmitting(true);
    try {
      await submitVote({ match_id: m.id, choice });
      window.localStorage.setItem(votedKey(m.id), choice);
      setVoted(choice);
      mutate();
    } catch {
      setVoteError(true);
    } finally {
      setSubmitting(false);
    }
  }

  const homeVotes = counts?.[m.home_team] ?? 0;
  const awayVotes = counts?.[m.away_team] ?? 0;
  const total = homeVotes + awayVotes;
  const homePct = total ? (homeVotes / total) * 100 : 50;
  const awayPct = total ? (awayVotes / total) * 100 : 50;

  return (
    <section className="card-broadcast">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-bold">Who Wins?</h2>
        <span className="chip text-[10px]">{total.toLocaleString()} vote{total === 1 ? "" : "s"}</span>
      </div>

      {error && (
        <p className="mb-3 text-[12px] text-muted">Voting is temporarily unavailable.</p>
      )}
      {voteError && (
        <p className="mb-3 text-[12px] text-danger">Couldn't record your vote — try again.</p>
      )}

      <div className="grid grid-cols-2 gap-3">
        {[m.home_team, m.away_team].map((team, i) => {
          const flag = i === 0 ? m.home_flag : m.away_flag;
          const isVoted = voted === team;
          const disabled = Boolean(voted) || Boolean(error) || submitting;
          return (
            <button key={team} type="button" disabled={disabled} onClick={() => handleVote(team)}
              className={`flex flex-col items-center gap-2 rounded-2xl border p-4 transition
                ${isVoted ? "border-gold/60 bg-gold/10" : "border-white/10 bg-white/3"}
                ${!disabled ? "hover:border-cyan/30 active:scale-[0.98]" : ""}
                ${disabled && !isVoted ? "opacity-70" : ""}`}>
              <Flag url={flag} name={team} size={32} />
              <span className={`font-display text-sm font-bold ${isVoted ? "text-gold" : "text-stadium"}`}>{team}</span>
              {isVoted && <span className="text-[10px] uppercase tracking-widest text-gold">✓ Your vote</span>}
            </button>
          );
        })}
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex justify-between text-[11px] tabnum">
          <span className="font-semibold text-success">{homePct.toFixed(0)}%</span>
          <span className="font-semibold text-cyan">{awayPct.toFixed(0)}%</span>
        </div>
        <div className="flex h-3 overflow-hidden rounded-full bg-white/5">
          <motion.div className="h-full bg-gradient-to-r from-success to-teal"
            initial={{ width: "50%" }} animate={{ width: `${homePct}%` }} transition={{ duration: 0.7 }} />
          <motion.div className="h-full bg-gradient-to-r from-cyan to-sky-400"
            initial={{ width: "50%" }} animate={{ width: `${awayPct}%` }} transition={{ duration: 0.7 }} />
        </div>
      </div>
    </section>
  );
}
