"use client";
/* User prediction flow for the tournament's final two ties: pick a winner,
 * guess the full-time score, and (if you predict a level score) call the
 * penalty winner. Stored client-side only (localStorage) — this is a
 * personal "your call vs the model's call" comparison, not an aggregate
 * stat, so it needs no backend. */
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Flag } from "@/components/ui";

export type UserPrediction = {
  winner: string;
  homeScore: number;
  awayScore: number;
  penaltyWinner?: string;
};

export const predictionStorageKey = (matchId: number | string) => `prediction_${matchId}`;
const storageKey = predictionStorageKey;

export function loadPrediction(matchId: number | string): UserPrediction | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(storageKey(matchId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function ScorePredictor({ m }: { m: any }) {
  const [saved, setSaved] = useState<UserPrediction | null>(null);
  const [editing, setEditing] = useState(false);
  const [winner, setWinner] = useState<string | null>(null);
  const [homeScore, setHomeScore] = useState("");
  const [awayScore, setAwayScore] = useState("");
  const [penaltyWinner, setPenaltyWinner] = useState<string | null>(null);

  useEffect(() => {
    setSaved(loadPrediction(m.id));
  }, [m.id]);

  const isLevel = homeScore !== "" && awayScore !== "" && Number(homeScore) === Number(awayScore);
  const canSubmit = winner != null && homeScore !== "" && awayScore !== "" && (!isLevel || penaltyWinner != null);

  function handleSubmit() {
    if (!canSubmit || winner == null) return;
    const prediction: UserPrediction = {
      winner,
      homeScore: Number(homeScore),
      awayScore: Number(awayScore),
      penaltyWinner: isLevel ? penaltyWinner ?? undefined : undefined,
    };
    window.localStorage.setItem(storageKey(m.id), JSON.stringify(prediction));
    setSaved(prediction);
    setEditing(false);
  }

  function startEdit() {
    if (saved) {
      setWinner(saved.winner);
      setHomeScore(String(saved.homeScore));
      setAwayScore(String(saved.awayScore));
      setPenaltyWinner(saved.penaltyWinner ?? null);
    }
    setEditing(true);
  }

  if (saved && !editing) {
    return <PredictionComparison m={m} saved={saved} onEdit={startEdit} />;
  }

  return (
    <section className="card-broadcast">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-bold">Your Prediction</h2>
        <span className="chip text-[10px]">Saved on this device</span>
      </div>

      {/* winner cards */}
      <div className="mb-5 grid grid-cols-2 gap-3">
        {[m.home_team, m.away_team].map((team, i) => {
          const flag = i === 0 ? m.home_flag : m.away_flag;
          const selected = winner === team;
          return (
            <button key={team} type="button" onClick={() => setWinner(team)}
              className={`flex flex-col items-center gap-2 rounded-2xl border p-4 transition
                ${selected ? "border-gold/60 bg-gold/10 shadow-glow-gold" : "border-white/10 bg-white/3 hover:border-cyan/30"}`}>
              <Flag url={flag} name={team} size={36} />
              <span className={`font-display text-sm font-bold ${selected ? "text-gold" : "text-stadium"}`}>{team}</span>
              <span className="text-[10px] uppercase tracking-widest text-muted">{selected ? "✓ Your pick" : "Pick to win"}</span>
            </button>
          );
        })}
      </div>

      {/* score inputs */}
      <div className="mb-2 text-[10px] uppercase tracking-widest text-muted">Full-time score</div>
      <div className="mb-4 flex items-center justify-center gap-4">
        <ScoreInput label={m.home_team} value={homeScore} onChange={setHomeScore} />
        <span className="font-display text-xl text-muted">–</span>
        <ScoreInput label={m.away_team} value={awayScore} onChange={setAwayScore} />
      </div>

      {/* penalty winner */}
      <AnimatePresence>
        {isLevel && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} className="mb-4 overflow-hidden">
            <div className="mb-2 text-[10px] uppercase tracking-widest text-muted">Level score — who wins on penalties?</div>
            <div className="flex gap-3">
              {[m.home_team, m.away_team].map((team) => (
                <label key={team}
                  className={`flex-1 cursor-pointer rounded-xl border px-3 py-2 text-center text-sm transition
                    ${penaltyWinner === team ? "border-cyan/50 bg-cyan/10 text-cyan" : "border-white/10 text-muted hover:border-white/20"}`}>
                  <input type="radio" name="pens" className="sr-only" checked={penaltyWinner === team}
                    onChange={() => setPenaltyWinner(team)} />
                  {team}
                </label>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center gap-3">
        <button type="button" onClick={handleSubmit} disabled={!canSubmit}
          className="btn-gold disabled:cursor-not-allowed disabled:opacity-40">
          Submit Prediction
        </button>
        {editing && (
          <button type="button" onClick={() => setEditing(false)} className="btn-ghost">Cancel</button>
        )}
      </div>
    </section>
  );
}

function ScoreInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <input type="number" min={0} max={20} value={value} placeholder="0"
        onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, "").slice(0, 2))}
        className="w-16 rounded-xl border border-white/10 bg-ink-3 text-center font-display text-2xl font-bold
                   text-stadium placeholder:text-muted/40 focus:border-cyan/40 focus:outline-none focus:ring-1 focus:ring-cyan/20" />
      <span className="text-[9px] uppercase tracking-wider text-muted">{label}</span>
    </div>
  );
}

function PredictionComparison({ m, saved, onEdit }: { m: any; saved: UserPrediction; onEdit: () => void }) {
  const agreesOnWinner = saved.winner === m.predicted_winner;
  const yourScore = `${saved.homeScore}-${saved.awayScore}`;
  const aiScore = m.predicted_score;

  return (
    <section className="card-broadcast">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-bold">Your Prediction vs AI Prediction</h2>
        <button type="button" onClick={onEdit} className="btn-sm">Change my pick</button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <PredictionCard label="Your Prediction" accent="gold" winner={saved.winner}
          score={yourScore} penaltyWinner={saved.penaltyWinner} />
        <PredictionCard label="AI Prediction" accent="cyan" winner={m.predicted_winner}
          score={aiScore} penaltyWinner={m.shootout ? m.predicted_winner : undefined} />
      </div>
      <div className={`mt-4 rounded-xl border px-4 py-2.5 text-center text-[13px] font-semibold
        ${agreesOnWinner ? "border-success/30 bg-success/10 text-success" : "border-gold/30 bg-gold/10 text-gold"}`}>
        {agreesOnWinner
          ? `You and the AI both back ${saved.winner}.`
          : `You're backing ${saved.winner} against the model's ${m.predicted_winner} pick.`}
      </div>
    </section>
  );
}

function PredictionCard({ label, accent, winner, score, penaltyWinner }: {
  label: string; accent: "gold" | "cyan"; winner: string; score: string; penaltyWinner?: string;
}) {
  const cls = accent === "gold" ? "border-gold/25 bg-gold/5 text-gold" : "border-cyan/25 bg-cyan/5 text-cyan";
  return (
    <div className={`rounded-2xl border p-4 text-center ${cls}`}>
      <div className="mb-2 text-[10px] uppercase tracking-widest text-muted">{label}</div>
      <div className="font-display text-3xl font-black tabnum text-stadium">{score}</div>
      <div className="mt-1 text-sm font-semibold">{winner} to win</div>
      {penaltyWinner && <div className="mt-1 text-[11px] text-muted">{penaltyWinner} on penalties</div>}
    </div>
  );
}
