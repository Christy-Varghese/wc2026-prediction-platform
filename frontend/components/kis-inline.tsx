"use client";
/* Compact one-line KIS mini-simulation, for embedding directly inside a
   match card (matches/page.tsx's QF/SF/Final cards) rather than a full
   KisVectorGrid/KisPressureGauge treatment — those live on the per-tie
   /knockout/[id] page (kis-powered-card.tsx) and on /kis. This is the
   "just the headline number" version for a dense grid of many cards.

   GET, not POST — same snapshot-fallback reasoning as kis-powered-card.tsx:
   works on the backend-free deployed demo for the pre-generated upcoming
   bracket ties via gen_snapshots.py; degrades to nothing (not an error
   message) for any fixture that isn't one of those. */
import useSWR from "swr";
import { api } from "@/lib/api";

const kisPath = (home: string, away: string) =>
  `/api/v1/predict/kis?home_team=${encodeURIComponent(home)}&away_team=${encodeURIComponent(away)}`;

export function KisInline({ home, away }: { home: string; away: string }) {
  const { data: r, error } = useSWR(kisPath(home, away), (p: string) => api(p), {
    revalidateOnFocus: false,
  });

  // Fail silently — a card for a fixture with no pre-generated KIS snapshot
  // (and no live backend) just doesn't show this row, rather than showing
  // an error inside an otherwise-working match card.
  if (error) return null;

  if (!r) return (
    <div className="mt-2 h-6 animate-pulse rounded-lg bg-chaos/5" />
  );

  const vm = r.vector_metrics ?? {};
  const homeSkill = Math.round((vm.home_skill_score ?? 0) * 100);
  const awaySkill = Math.round((vm.away_skill_score ?? 0) * 100);

  return (
    <div className="mt-2 flex items-center justify-between gap-1.5 rounded-lg border border-chaos/15 bg-chaos/[0.04] px-2 py-1 text-[10px]">
      <span className="flex items-center gap-1 font-bold uppercase tracking-wider text-chaos">
        ⚡ KIS
      </span>
      <span className="tabnum text-stadium">
        {r.predicted_winner} {(r.win_probability * 100).toFixed(0)}%
      </span>
      <span className="tabnum text-success">
        S {homeSkill}–{awaySkill}
      </span>
    </div>
  );
}
