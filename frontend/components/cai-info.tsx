"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

/* Footer badge: replaces the old "Elo · Poisson · Dixon-Coles · …" tagline with
   the CAI model name. Click → a modal explaining how CAI works. */
export function CaiInfo() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="mt-1 inline-flex items-center gap-1.5 text-[11px] text-muted/70 transition hover:text-gold">
        <span className="font-semibold tracking-wide">Powered by the CAI model</span>
        <span className="rounded-full border border-gold/40 px-1.5 text-[9px] text-gold/80">how it works</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <motion.div
              initial={{ scale: 0.96, y: 12 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="card max-h-[88vh] w-full max-w-lg overflow-y-auto p-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-display text-xl font-bold">
                  CAI <span className="text-muted">· ChrisAI prediction model</span>
                </h2>
                <button onClick={() => setOpen(false)} className="text-muted hover:text-stadium">✕</button>
              </div>

              <p className="text-[13px] leading-relaxed text-stadium">
                CAI predicts each match by understanding how a team is playing
                <span className="text-gold"> right now</span> — not just its history.
                It reads this year's matches and the group stage, the key moments of
                completed games, and the live state of each squad, then leans on that
                current picture more heavily than pre-tournament data.
              </p>

              <Section title="What CAI looks at">
                <Bullet>This season's results + every World Cup group game, with the key moments of each.</Bullet>
                <Bullet>Form & fitness of the playing XI and the bench / likely substitutes.</Bullet>
                <Bullet>Manager tactics, play style, formation and how the units fit together.</Bullet>
                <Bullet>Goalkeeper quality and penalty composure for knockout ties.</Bullet>
                <Bullet>Momentum — the Elo a side has actually banked across the tournament.</Bullet>
              </Section>

              <Section title="How it decides">
                <Bullet>
                  A historical base (Elo · Poisson · Dixon-Coles · XGBoost · market odds) sets the
                  starting prior — but CAI <span className="text-gold">prioritises current form and
                  momentum over that base</span>. Recent form leads; history supports.
                </Bullet>
                <Bullet>
                  For every knockout tie CAI runs it three ways —
                  <b className="text-gold"> Base · Upside · Downside</b> — each with its own expected
                  goals, so you see the range, not a single guess.
                </Bullet>
                <Bullet>
                  It names each side's <b className="text-gold">pain points</b> — the weaknesses
                  (keeper, fitness, cold form, penalty fragility) an upset would exploit.
                </Bullet>
                <Bullet>
                  A Monte-Carlo (50,000 tournaments) turns match-level edges into title & survival odds.
                </Bullet>
              </Section>

              <p className="mt-4 rounded-xl bg-gold/10 p-3 text-[12px] leading-snug text-stadium">
                Why it's different: CAI tries to read the game from the root — current form, fitness and
                tactics — rather than only extrapolating past data. Previous data matters, but the way a
                team is playing now is the lead signal: there's no going back.
              </p>

              <p className="mt-3 text-[10px] text-muted/60">
                For entertainment. Not affiliated with FIFA. Not betting advice.
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <h3 className="mb-1.5 text-[11px] uppercase tracking-widest text-gold/80">{title}</h3>
      <ul className="space-y-1.5 text-[13px] leading-snug text-stadium">{children}</ul>
    </div>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2"><span className="text-gold">›</span><span>{children}</span></li>
  );
}
