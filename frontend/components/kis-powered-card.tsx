"use client";
/* "Powered by KIS" card for upcoming (unplayed) knockout ties. Fetches
   POST /api/v1/predict/kis for the given fixture and renders the vector
   decomposition (reusing kis-vector-grid.tsx / kis-pressure-gauge.tsx from
   the KIS Hub) plus a click-to-expand "How KIS works" explainer. Shown only
   for unplayed ties — played matches already have their own post-match
   analysis on this page. */
import { useState } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { KisVectorGrid } from "@/components/kis-vector-grid";
import { KisPressureGauge } from "@/components/kis-pressure-gauge";

// POST body varies per fixture, so key on a stable string and fetch manually
// (useSWR's default fetcher assumes GET) rather than reusing the sitewide
// `api()`-only `fetcher`.
const kisFetcher = ([, home, away]: [string, string, string]) =>
  api("/api/v1/predict/kis", {
    method: "POST",
    body: JSON.stringify({ home_team: home, away_team: away }),
  });

export function KisPoweredCard({ home, away }: { home: string; away: string }) {
  const [showHow, setShowHow] = useState(false);
  const { data: result, error } = useSWR(["kis", home, away], kisFetcher, {
    revalidateOnFocus: false,
  });

  return (
    <div className="card-broadcast overflow-hidden p-0">
      <button onClick={() => setShowHow((v) => !v)}
        className="flex w-full items-center justify-between gap-2 border-b border-chaos/15 bg-chaos/[0.04] px-4 py-2.5 text-left transition hover:bg-chaos/[0.07]">
        <div className="flex items-center gap-2">
          <span className="font-display text-sm font-bold uppercase tracking-widest text-stadium">
            ⚡ Powered by KIS
          </span>
          <span className="chip text-[9px] text-chaos border-chaos/30 bg-chaos/10">
            Knockout Intelligence System
          </span>
        </div>
        <span className="text-[11px] text-muted">
          {showHow ? "Hide" : "ⓘ How it works"} {showHow ? "▲" : "▼"}
        </span>
      </button>

      <AnimatePresence>
        {showHow && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            className="overflow-hidden border-b border-white/8">
            <div className="space-y-2 bg-white/[0.02] px-4 py-4 text-[12px] leading-relaxed text-muted">
              <p>
                KIS runs a fresh <b className="text-stadium">50,000-simulation</b> Monte
                Carlo for this specific matchup and decomposes the projected result into
                two vectors: <span className="tabnum">‖P‖² = ‖S‖² + ‖L‖²</span>
              </p>
              <p>
                <b className="text-success">Skill (S)</b> — form, tactical style, and
                composure under pressure, reprojected from CAI's existing statistical/form/
                tactical/psychology model blend.
              </p>
              <p>
                <b className="text-chaos">Luck (L)</b> — how much each team has over- or
                under-performed the model's own goal expectations so far, plus a
                environmental-volatility factor (venue climate + officiating) that flags
                simulation runs where a tail-probability swing (a deflection, a red card,
                a shootout) — not the underlying form — decided the outcome.
              </p>
              <p>
                The <b className="text-gold">Knockout Pressure Score</b> (0–100) blends
                knockout experience, penalty-shootout history, and in-game composure —
                it's a <i>partial</i> formula (captain-specific data isn't available yet),
                labeled honestly rather than guessed at.
              </p>
              <p className="text-muted/70">
                This platform is an AI-driven probability simulation built for
                entertainment and analytics purposes. Not betting advice. Run a custom
                matchup at <a href="/kis" className="text-cyan hover:underline">/kis</a>.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="p-4">
        {error && (
          <p className="text-[12px] text-danger">KIS simulation unavailable — backend offline.</p>
        )}
        {!error && !result && (
          <div className="h-24 animate-pulse rounded-xl bg-white/5" />
        )}
        {result && (
          <div className="space-y-4">
            <div className="text-center">
              <div className="font-display text-lg font-bold text-gold">
                {result.predicted_winner}
                <span className="ml-2 text-stadium">{result.predicted_score}</span>
                {result.shootout && <span className="ml-1 text-sm text-muted">· pens</span>}
              </div>
              <div className="text-[11px] text-muted">
                probability <b className="text-stadium">{(result.win_probability * 100).toFixed(1)}%</b>
                {" · "}{result.n_sims?.toLocaleString()} KIS runs
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <KisVectorGrid result={result} />
              <KisPressureGauge result={result} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
