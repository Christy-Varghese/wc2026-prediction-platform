"use client";
/* Social sharing for the final two ties. Share text/links are built from
 * whatever the user predicted (falls back to the AI's prediction if they
 * haven't submitted one) — no new dependency: plain share-intent URLs plus
 * navigator.share() where supported, and a server-rendered PNG via Next's
 * built-in next/og ImageResponse (app/api/share-image) instead of a new
 * client-side screenshot library. */
import { useEffect, useState } from "react";
import { loadPrediction, type UserPrediction } from "@/components/final-match/score-predictor";

export function SharePrediction({ m }: { m: any }) {
  const [prediction, setPrediction] = useState<UserPrediction | null>(null);
  const [canNativeShare, setCanNativeShare] = useState(false);
  const [origin, setOrigin] = useState("");

  useEffect(() => {
    setPrediction(loadPrediction(m.id));
    setCanNativeShare(typeof navigator !== "undefined" && "share" in navigator);
    setOrigin(window.location.origin);
  }, [m.id]);

  const winner = prediction?.winner ?? m.predicted_winner;
  const score = prediction ? `${prediction.homeScore}-${prediction.awayScore}` : m.predicted_score;
  const url = `${origin}/knockout/${m.id}`;
  const text = prediction
    ? `I'm calling it: ${winner} to win the ${m.round} (${m.home_team} vs ${m.away_team}), ${score}. What's your prediction?`
    : `${m.round}: ${m.home_team} vs ${m.away_team} — the AI predicts ${winner} to win, ${score}. What do you think?`;

  const imageParams = new URLSearchParams();
  if (prediction) {
    imageParams.set("yourWinner", prediction.winner);
    imageParams.set("yourScore", score);
  }
  const imageUrl = `/api/share-image/${m.id}${imageParams.toString() ? `?${imageParams}` : ""}`;

  async function handleNativeShare() {
    try {
      await navigator.share({ title: `${m.home_team} vs ${m.away_team}`, text, url });
    } catch {
      // user cancelled — no-op
    }
  }

  const links = [
    { label: "X", href: `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}` },
    { label: "WhatsApp", href: `https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}` },
    { label: "Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}&quote=${encodeURIComponent(text)}` },
    { label: "LinkedIn", href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}` },
  ];

  return (
    <section className="card-broadcast">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-bold">Share Your Prediction</h2>
        {prediction && <span className="chip-gold text-[10px]">Your pick: {winner} {score}</span>}
      </div>

      <div className="flex flex-wrap items-center gap-2.5">
        {canNativeShare && (
          <button type="button" onClick={handleNativeShare} className="btn-gold">Share</button>
        )}
        {links.map((l) => (
          <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer" className="btn-sm">
            {l.label}
          </a>
        ))}
        <a href={imageUrl} download={`wc2026-${m.round.toLowerCase().replace(/\s+/g, "-")}.png`}
          target="_blank" rel="noopener noreferrer" className="btn-ghost">
          ⬇ Download as Image
        </a>
      </div>
    </section>
  );
}
