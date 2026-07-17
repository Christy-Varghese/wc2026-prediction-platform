"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

const fetcher = (p: string) => api(p);

/* ──────────────────────────────────────────────────────────────
   CIRCULAR BRACKET — Conference-table / orbital layout
   32 team positions around the outer ring, bracket progresses
   inward through R32 → R16 → QF → SF → Final (center trophy)

   Circular ordering (clockwise from top):
   LEFT HALF  (positions 0–15, angles 270°→90° via 0°):
     pairs: [74,77,73,75,83,84,81,82]
   RIGHT HALF (positions 16–31, angles 90°→270° via 180°):
     pairs: [76,78,79,80,86,88,85,87]
────────────────────────────────────────────────────────────── */

const R32_CIRCLE_ORDER = [74, 77, 73, 75, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87];
const R16_CIRCLE_ORDER = [89, 90, 93, 94, 91, 92, 95, 96];
const QF_CIRCLE_ORDER  = [97, 98, 99, 100];
const SF_CIRCLE_ORDER  = [101, 102];
const FINAL_ID         = 104;
const N = 32;

// SVG canvas
const SZ = 720;
const CX = SZ / 2;
const CY = SZ / 2;

// Ring radii (outermost = teams, innermost = Final)
const R_TEAM = 308;
const R_R32  = 252;
const R_R16  = 196;
const R_QF   = 143;
const R_SF   = 94;
const R_FINAL = 0; // center

// Node sizes
const SZ_TEAM = 18;
const SZ_R32  = 15;
const SZ_R16  = 17;
const SZ_QF   = 20;
const SZ_SF   = 23;
const SZ_FINAL = 36;

/* ── Geometry helpers ── */
function slotAngleDeg(slotFrac: number) {
  return -90 + slotFrac * (360 / N);
}
function slotXY(slotFrac: number, r: number) {
  const rad = (slotAngleDeg(slotFrac) * Math.PI) / 180;
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
}
function teamXY(i: number)  { return slotXY(i, R_TEAM); }
function r32XY(j: number)   { return slotXY(j * 2 + 0.5, R_R32); }
function r16XY(k: number)   { return slotXY(k * 4 + 1.5, R_R16); }
function qfXY(m: number)    { return slotXY(m * 8 + 3.5, R_QF); }
function sfXY(n: number)    { return slotXY(n * 16 + 7.5, R_SF); }

/* ── Winner resolver ── */
function winnerOf(m: any): string | null {
  if (!m) return null;
  if (m.played && m.home_score != null) {
    if (m.home_score > m.away_score) return m.home_team;
    if (m.away_score > m.home_score) return m.away_team;
    if (m.pen_home != null) return m.pen_home > m.pen_away ? m.home_team : m.away_team;
    if (m.pen_away != null) return m.pen_away > m.pen_home ? m.away_team : m.home_team;
  }
  return m.predicted_winner ?? null;
}

/* ── Round label config ── */
const ROUND_LABELS = [
  { r: R_TEAM - 32, label: "ROUND OF 32", slotFrac: 15.5 },
  { r: R_R16 - 28, label: "ROUND OF 16", slotFrac: 15.5 },
  { r: R_QF - 26,  label: "QUARTER-FINALS", slotFrac: 15.5 },
  { r: R_SF - 22,  label: "SEMI-FINALS",  slotFrac: 15.5 },
];

/* ── Clip path IDs ── */
function clipId(prefix: string, idx: number) { return `c-${prefix}-${idx}`; }

/* ── FlagCircle ── */
function FlagCircle({
  cx, cy, r, flagUrl, dimmed, winner, gold, predictedWinner, predictedLoser,
  tapPad = 6, onClick,
}: {
  cx: number; cy: number; r: number;
  flagUrl?: string; dimmed?: boolean; winner?: boolean; gold?: boolean;
  predictedWinner?: boolean; predictedLoser?: boolean;
  // Extra radius (viewBox units) added to the invisible click target beyond
  // the visible circle. Defaults to a small fixed pad, but the page computes
  // a larger value on narrow viewports so tap targets stay usable even as
  // the whole diagram scales down — the visible flag can stay small, but the
  // tappable area shouldn't shrink below a real-finger-sized minimum.
  tapPad?: number;
  onClick?: () => void;
}) {
  const id = `fc-${cx.toFixed(0)}-${cy.toFixed(0)}-${r}`;
  return (
    <g onClick={onClick} style={{ cursor: onClick ? "pointer" : "default" }}>
      <defs>
        <clipPath id={id}><circle cx={cx} cy={cy} r={r} /></clipPath>
        {dimmed && (
          <filter id={`gs-${id}`}>
            <feColorMatrix type="saturate" values="0" />
          </filter>
        )}
      </defs>

      {/* Outer glow / accent ring */}
      {winner && !gold && (
        <circle cx={cx} cy={cy} r={r + 4}
          fill="none" stroke="rgba(22,163,74,0.35)" strokeWidth={2} />
      )}
      {gold && (
        <circle cx={cx} cy={cy} r={r + 5}
          fill="none" stroke="rgba(255,215,0,0.4)" strokeWidth={2.5} />
      )}
      {/* Predicted (not yet played) winner: cyan dashed outline — visually
          distinct from the solid green "confirmed" ring above, so a
          projection never reads as an already-settled result. */}
      {predictedWinner && !winner && !gold && (
        <circle cx={cx} cy={cy} r={r + 4}
          fill="none"
          stroke="rgba(0,212,255,0.55)"
          strokeWidth={2}
          strokeDasharray="4 3"
        />
      )}
      {/* Predicted loser: yellow dashed outline */}
      {predictedLoser && (
        <circle cx={cx} cy={cy} r={r + 3}
          fill="none"
          stroke="rgba(253,224,71,0.55)"
          strokeWidth={1.5}
          strokeDasharray="3 3"
        />
      )}

      {/* Background fill */}
      <circle cx={cx} cy={cy} r={r}
        fill={dimmed ? "#06101E" : "#101C38"}
        stroke={
          gold            ? "rgba(255,215,0,0.65)" :
          winner          ? "#16A34A" :
          predictedWinner ? "rgba(0,212,255,0.5)" :
          predictedLoser  ? "rgba(253,224,71,0.4)" :
                            "rgba(255,255,255,0.13)"
        }
        strokeDasharray={!winner && !gold && predictedWinner ? "3 2" : undefined}
        strokeWidth={gold ? 2.5 : winner ? 2 : predictedWinner ? 2 : predictedLoser ? 1.5 : 1}
        opacity={dimmed ? 0.38 : 1}
      />

      {/* Flag image */}
      {flagUrl && (
        <image
          href={flagUrl}
          x={cx - r} y={cy - r}
          width={r * 2} height={r * 2}
          clipPath={`url(#${id})`}
          preserveAspectRatio="xMidYMid slice"
          opacity={dimmed ? 0.25 : 1}
          filter={dimmed ? `url(#gs-${id})` : undefined}
        />
      )}

      {/* Confirmed-winner wash — a translucent green tint over the flag
          itself (same idea as the "dimmed" grayscale wash for eliminated
          teams, opposite direction), so a win reads at a glance even before
          checking the outline. */}
      {winner && !gold && flagUrl && (
        <circle cx={cx} cy={cy} r={r} clipPath={`url(#${id})`}
          fill="rgba(22,163,74,0.32)" />
      )}

      {/* Invisible click target */}
      {onClick && (
        <circle cx={cx} cy={cy} r={r + tapPad} fill="transparent" />
      )}
    </g>
  );
}

/* ── Confetti burst — fired around the center Final/Champion node. Bigger
   and brighter once the Final is actually played (a real champion); a
   lighter sparkle version while it's still just CAI's projection, so the
   celebration intensity itself doesn't overclaim a result that hasn't
   happened yet. Pure Framer Motion (SVG <motion.g> translate), no new
   confetti dependency. ── */
const CONFETTI_COLORS = ["#FFD700", "#00D4FF", "#00E676", "#00FFB2", "#B14EFF", "#FF9500"];

function ConfettiBurst({ cx, cy, celebratory }: { cx: number; cy: number; celebratory?: boolean }) {
  const particles = useMemo(() => {
    const count = celebratory ? 46 : 24;
    return Array.from({ length: count }).map((_, i) => {
      const angle = (i / count) * Math.PI * 2 + (Math.random() - 0.5) * 0.6;
      const dist = (celebratory ? 130 : 80) + Math.random() * (celebratory ? 220 : 130);
      return {
        id: i,
        color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        tx: Math.cos(angle) * dist,
        ty: Math.sin(angle) * dist * 0.65 + (celebratory ? 60 : 30),
        w: 3 + Math.random() * (celebratory ? 5 : 3),
        h: 5 + Math.random() * (celebratory ? 8 : 5),
        rotate: (Math.random() - 0.5) * 540,
        delay: 1.3 + Math.random() * (celebratory ? 0.5 : 0.3),
        duration: 1.5 + Math.random() * 1,
      };
    });
  }, [celebratory]);

  return (
    <g pointerEvents="none">
      {particles.map((p) => (
        <motion.g
          key={p.id}
          initial={{ opacity: 0, x: 0, y: 0, rotate: 0 }}
          animate={{ opacity: [0, 1, 1, 0], x: [0, p.tx], y: [0, p.ty], rotate: [0, p.rotate] }}
          transition={{ duration: p.duration, delay: p.delay, ease: "easeOut" }}
        >
          <rect x={cx - p.w / 2} y={cy - p.h / 2} width={p.w} height={p.h} rx={1} fill={p.color} />
        </motion.g>
      ))}
    </g>
  );
}

/* ── Animated connector line ── */
function ConnLine({
  x1, y1, x2, y2, delay, color = "rgba(255,255,255,0.08)",
}: {
  x1: number; y1: number; x2: number; y2: number;
  delay: number; color?: string;
}) {
  const len = Math.hypot(x2 - x1, y2 - y1);
  return (
    <motion.line
      x1={x1} y1={y1} x2={x2} y2={y2}
      stroke={color} strokeWidth={1.2}
      strokeDasharray={len}
      initial={{ strokeDashoffset: len, opacity: 0 }}
      animate={{ strokeDashoffset: 0, opacity: 1 }}
      transition={{ duration: 0.4, delay, ease: "easeOut" }}
    />
  );
}

/* ══════════════════════════════════════════════════════════════
   MAIN PAGE
══════════════════════════════════════════════════════════════ */
export default function BracketPage() {
  const router = useRouter();
  const { data: ko } = useSWR("/api/knockout", fetcher, { revalidateOnFocus: false });
  const { data: teams } = useSWR("/api/teams", fetcher, { revalidateOnFocus: false });
  const [hovered, setHovered] = useState<number | null>(null);

  // The whole diagram scales down via the SVG's viewBox to fit narrow
  // viewports (no horizontal scroll), but that shrinks tap targets right
  // along with the visuals — a flag that's fine to *see* on a phone can be
  // too small to reliably *tap*. Track the actual rendered width so we can
  // pad the invisible tap-target circles up to a real-finger-sized minimum
  // without changing how anything looks.
  const svgWrapRef = useRef<HTMLDivElement>(null);
  const [renderScale, setRenderScale] = useState(1); // rendered CSS width / SZ
  useEffect(() => {
    const el = svgWrapRef.current;
    if (!el) return;
    const update = () => setRenderScale(el.clientWidth / SZ);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
    // Re-run once `ko` arrives: before that, this component renders
    // <BracketSkeleton /> instead (see the early return below), so
    // svgWrapRef.current is still null on the very first effect run.
  }, [ko]);
  const MIN_TAP_R_PX = 21; // ~42px minimum tap diameter (Apple/Google guidance is ~44px)
  const tapPadFor = (baseR: number) =>
    renderScale > 0 ? Math.max(6, MIN_TAP_R_PX / renderScale - baseR) : 6;

  const flagMap = useMemo<Record<string, string>>(() => {
    const m: Record<string, string> = {};
    if (Array.isArray(teams)) for (const t of teams) if (t.name) m[t.name] = t.flag_url ?? "";
    return m;
  }, [teams]);

  if (!ko) return <BracketSkeleton />;

  const byId: Record<number, any> = {};
  for (const m of ko.matches ?? []) byId[m.id] = m;

  // Build the 32 team-slot entries (pos 2i = home, 2i+1 = away of R32_CIRCLE_ORDER[i])
  const teamSlots = R32_CIRCLE_ORDER.map((matchId, i) => {
    const m = byId[matchId];
    return [
      { team: m?.home_team ?? null, matchId, side: "home" as const },
      { team: m?.away_team ?? null, matchId, side: "away" as const },
    ];
  }).flat();

  const champion = winnerOf(byId[FINAL_ID]);
  const champFlag = champion ? (flagMap[champion] ?? "") : "";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="text-center pb-2">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan/20 bg-cyan/5 px-4 py-1.5 mb-3">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan animate-pulse" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-cyan/80">
            CAI Knockout Prediction
          </span>
        </div>
        <h2 className="font-display text-2xl font-black uppercase tracking-widest text-white">
          Tournament Bracket
        </h2>
        <p className="mt-1 text-[11px] text-muted">
          Click any node to view full match analysis · flags rotate inward as teams advance
        </p>
      </div>

      {/* Circular SVG bracket */}
      <div className="flex justify-center w-full overflow-x-auto">
        <div ref={svgWrapRef} className="w-full" style={{ minWidth: 320, maxWidth: 760 }}>
          <svg
            viewBox={`0 0 ${SZ} ${SZ}`}
            className="w-full h-auto select-none"
            style={{ maxHeight: "90vh" }}>

            {/* ── Defs: radial gradient background glow ── */}
            <defs>
              <radialGradient id="bgGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(255,215,0,0.04)" />
                <stop offset="40%" stopColor="rgba(14,42,90,0.06)" />
                <stop offset="100%" stopColor="rgba(0,0,0,0)" />
              </radialGradient>
            </defs>

            {/* Background glow */}
            <circle cx={CX} cy={CY} r={SZ / 2} fill="url(#bgGlow)" />

            {/* ── Guide rings (subtle dashed circles) ── */}
            {[R_TEAM, R_R32, R_R16, R_QF, R_SF].map((r, i) => (
              <circle key={i} cx={CX} cy={CY} r={r}
                fill="none" stroke="rgba(255,255,255,0.04)"
                strokeWidth={1} strokeDasharray="3 7" />
            ))}

            {/* ── CONNECTORS: Team → R32 node ── */}
            {teamSlots.map((slot, ti) => {
              const p1 = teamXY(ti);
              const p2 = r32XY(Math.floor(ti / 2));
              const m = byId[slot.matchId];
              const isWinner = slot.team && slot.team === winnerOf(m);
              return (
                <ConnLine key={`t-r32-${ti}`}
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  delay={0.02 + ti * 0.012}
                  color={isWinner ? "rgba(22,163,74,0.25)" : "rgba(255,255,255,0.06)"}
                />
              );
            })}

            {/* ── CONNECTORS: R32 → R16 ── */}
            {R32_CIRCLE_ORDER.map((matchId, j) => {
              const p1 = r32XY(j);
              const p2 = r16XY(Math.floor(j / 2));
              const m = byId[matchId];
              const advancing = !!winnerOf(m);
              return (
                <ConnLine key={`r32-r16-${j}`}
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  delay={0.35 + j * 0.018}
                  color={advancing ? "rgba(22,163,74,0.2)" : "rgba(255,255,255,0.06)"}
                />
              );
            })}

            {/* ── CONNECTORS: R16 → QF ── */}
            {R16_CIRCLE_ORDER.map((matchId, k) => {
              const p1 = r16XY(k);
              const p2 = qfXY(Math.floor(k / 2));
              return (
                <ConnLine key={`r16-qf-${k}`}
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  delay={0.62 + k * 0.022}
                  color="rgba(255,255,255,0.07)"
                />
              );
            })}

            {/* ── CONNECTORS: QF → SF ── */}
            {QF_CIRCLE_ORDER.map((matchId, m) => {
              const p1 = qfXY(m);
              const p2 = sfXY(Math.floor(m / 2));
              return (
                <ConnLine key={`qf-sf-${m}`}
                  x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                  delay={0.85 + m * 0.03}
                  color="rgba(255,215,0,0.15)"
                />
              );
            })}

            {/* ── CONNECTORS: SF → center ── */}
            {SF_CIRCLE_ORDER.map((matchId, n) => {
              const p1 = sfXY(n);
              return (
                <ConnLine key={`sf-final-${n}`}
                  x1={p1.x} y1={p1.y} x2={CX} y2={CY}
                  delay={1.0}
                  color="rgba(255,215,0,0.25)"
                />
              );
            })}

            {/* ══════════════════════════════
                TEAM FLAGS — outer ring (R32)
            ══════════════════════════════ */}
            {teamSlots.map((slot, ti) => {
              const pos = teamXY(ti);
              const m = byId[slot.matchId];
              const played = !!m?.played;
              const predictedWinnerName = m?.predicted_winner ?? null;
              const actualWinner = played ? winnerOf(m) : null;
              const hasTeam = slot.team != null;

              // Grey out only if the match is completed and this team lost
              const isEliminated = played && hasTeam && slot.team !== actualWinner;
              // Green border if match is completed and this team won
              const isWinner = played && hasTeam && slot.team === actualWinner;
              // Cyan dashed outline if match not yet played but CAI predicts this team wins
              const isPredictedWinner =
                !played && hasTeam &&
                predictedWinnerName != null &&
                slot.team === predictedWinnerName;
              // Yellow dashed outline if match not yet played but CAI predicts this team loses
              const isPredictedLoser =
                !played && hasTeam &&
                predictedWinnerName != null &&
                slot.team !== predictedWinnerName;

              return (
                <motion.g
                  key={`team-${ti}`}
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.04 + ti * 0.018, type: "spring", stiffness: 280, damping: 22 }}
                  whileHover={{ scale: 1.15, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  whileTap={{ scale: 0.92, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  onMouseEnter={() => setHovered(slot.matchId)}
                  onMouseLeave={() => setHovered(null)}
                >
                  <FlagCircle
                    cx={pos.x} cy={pos.y}
                    r={hovered === slot.matchId ? SZ_TEAM + 3 : SZ_TEAM}
                    flagUrl={flagMap[slot.team ?? ""] ?? ""}
                    dimmed={isEliminated}
                    winner={isWinner}
                    predictedWinner={isPredictedWinner}
                    predictedLoser={isPredictedLoser}
                    tapPad={tapPadFor(SZ_TEAM)}
                    onClick={() => router.push(`/knockout/${slot.matchId}`)}
                  />
                </motion.g>
              );
            })}

            {/* ══════════════════════════════
                R32 MATCH NODES (winner flags — R32 is complete, so every
                node here is a real qualifier, not a projection like R16+)
            ══════════════════════════════ */}
            {R32_CIRCLE_ORDER.map((matchId, j) => {
              const pos = r32XY(j);
              const m = byId[matchId];
              const winner = winnerOf(m);
              const flagUrl = winner ? (flagMap[winner] ?? "") : "";
              return (
                <motion.g
                  key={`r32-${j}`}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.4 + j * 0.02, type: "spring" }}
                  whileHover={{ scale: 1.15, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  whileTap={{ scale: 0.92, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  style={{ cursor: "pointer" }}
                  onClick={() => router.push(`/knockout/${matchId}`)}
                  onMouseEnter={() => setHovered(matchId)}
                  onMouseLeave={() => setHovered(null)}
                >
                  <circle cx={pos.x} cy={pos.y} r={SZ_R32 + tapPadFor(SZ_R32)} fill="transparent" />
                  <FlagCircle
                    cx={pos.x} cy={pos.y} r={SZ_R32}
                    flagUrl={flagUrl}
                    winner={!!winner}
                  />
                  {!winner && (
                    <text x={pos.x} y={pos.y + 3.5} textAnchor="middle"
                      fill="rgba(255,255,255,0.2)" fontSize={6.5} fontFamily="monospace">
                      R32
                    </text>
                  )}
                </motion.g>
              );
            })}

            {/* ══════════════════════════════
                R16 NODES (winner flags)
            ══════════════════════════════ */}
            {R16_CIRCLE_ORDER.map((matchId, k) => {
              const pos = r16XY(k);
              const m = byId[matchId];
              const winner = winnerOf(m);
              const isPlayed = !!m?.played;
              const flagUrl = winner ? (flagMap[winner] ?? "") : "";
              return (
                <motion.g
                  key={`r16-${k}`}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.65 + k * 0.03, type: "spring" }}
                  whileHover={{ scale: 1.15, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  whileTap={{ scale: 0.92, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  style={{ cursor: "pointer" }}
                  onClick={() => router.push(`/knockout/${matchId}`)}
                >
                  <circle cx={pos.x} cy={pos.y} r={SZ_R16 + tapPadFor(SZ_R16)} fill="transparent" />
                  <FlagCircle
                    cx={pos.x} cy={pos.y} r={SZ_R16}
                    flagUrl={flagUrl}
                    winner={isPlayed && !!winner}
                    predictedWinner={!isPlayed && !!winner}
                  />
                  {!winner && (
                    <text x={pos.x} y={pos.y + 3.5} textAnchor="middle"
                      fill="rgba(255,255,255,0.2)" fontSize={6.5} fontFamily="monospace">
                      R16
                    </text>
                  )}
                </motion.g>
              );
            })}

            {/* ══════════════════════════════
                QF NODES
            ══════════════════════════════ */}
            {QF_CIRCLE_ORDER.map((matchId, mi) => {
              const pos = qfXY(mi);
              const m = byId[matchId];
              const winner = winnerOf(m);
              const isPlayed = !!m?.played;
              const flagUrl = winner ? (flagMap[winner] ?? "") : "";
              return (
                <motion.g
                  key={`qf-${mi}`}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.88 + mi * 0.04, type: "spring" }}
                  whileHover={{ scale: 1.15, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  whileTap={{ scale: 0.92, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  style={{ cursor: "pointer" }}
                  onClick={() => router.push(`/knockout/${matchId}`)}
                >
                  <circle cx={pos.x} cy={pos.y} r={SZ_QF + tapPadFor(SZ_QF)} fill="transparent" />
                  <FlagCircle
                    cx={pos.x} cy={pos.y} r={SZ_QF}
                    flagUrl={flagUrl}
                    winner={isPlayed && !!winner}
                    predictedWinner={!isPlayed && !!winner}
                  />
                  {!winner && (
                    <text x={pos.x} y={pos.y + 3.5} textAnchor="middle"
                      fill="rgba(255,255,255,0.2)" fontSize={7} fontFamily="monospace">
                      QF
                    </text>
                  )}
                </motion.g>
              );
            })}

            {/* ══════════════════════════════
                SF NODES
            ══════════════════════════════ */}
            {SF_CIRCLE_ORDER.map((matchId, ni) => {
              const pos = sfXY(ni);
              const m = byId[matchId];
              const winner = winnerOf(m);
              const flagUrl = winner ? (flagMap[winner] ?? "") : "";
              return (
                <motion.g
                  key={`sf-${ni}`}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 1.05 + ni * 0.05, type: "spring" }}
                  whileHover={{ scale: 1.15, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  whileTap={{ scale: 0.92, transition: { type: "spring", stiffness: 400, damping: 14 } }}
                  style={{ cursor: "pointer" }}
                  onClick={() => router.push(`/knockout/${matchId}`)}
                >
                  {/* Gold accent ring */}
                  <circle cx={pos.x} cy={pos.y} r={SZ_SF + 4}
                    fill="none" stroke="rgba(255,215,0,0.12)" strokeWidth={1} />
                  <circle cx={pos.x} cy={pos.y} r={SZ_SF + tapPadFor(SZ_SF)} fill="transparent" />
                  <FlagCircle
                    cx={pos.x} cy={pos.y} r={SZ_SF}
                    flagUrl={flagUrl}
                    winner={!!winner}
                    gold={true}
                  />
                  {!winner && (
                    <text x={pos.x} y={pos.y + 3.5} textAnchor="middle"
                      fill="rgba(255,215,0,0.3)" fontSize={7.5} fontFamily="monospace">
                      SF
                    </text>
                  )}
                </motion.g>
              );
            })}

            {/* ══════════════════════════════
                CENTER — Final / Champion
            ══════════════════════════════ */}
            <motion.g
              initial={{ opacity: 0, scale: 0.3 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 1.2, type: "spring", stiffness: 200 }}
              style={{ cursor: "pointer" }}
              onClick={() => router.push(`/knockout/${FINAL_ID}`)}
            >
              {/* Confetti burst behind the flag/trophy — brighter once the Final's
                  actually been played (a real champion), lighter sparkle while it's
                  still CAI's projection. */}
              {champion && <ConfettiBurst cx={CX} cy={CY} celebratory={!!byId[FINAL_ID]?.played} />}

              {/* Pulsing aura */}
              <motion.circle cx={CX} cy={CY} r={54}
                fill="none" stroke="rgba(255,215,0,0.15)" strokeWidth={1}
                animate={{ r: [54, 60, 54], opacity: [0.15, 0.05, 0.15] }}
                transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
              />
              <circle cx={CX} cy={CY} r={46}
                fill="none" stroke="rgba(255,215,0,0.2)" strokeWidth={1.5} strokeDasharray="4 6" />

              {champion && champFlag ? (
                /* Show champion flag */
                <motion.g whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.94 }}
                  transition={{ type: "spring", stiffness: 320, damping: 18 }}>
                  <FlagCircle
                    cx={CX} cy={CY} r={SZ_FINAL}
                    flagUrl={champFlag}
                    gold={true}
                  />
                </motion.g>
              ) : (
                /* Show trophy placeholder */
                <motion.g
                  animate={{ y: [0, -4, 0], rotate: [-3, 3, -3] }}
                  transition={{ repeat: Infinity, duration: 2.6, ease: "easeInOut" }}
                >
                  <circle cx={CX} cy={CY} r={SZ_FINAL}
                    fill="#0F1830"
                    stroke="rgba(255,215,0,0.45)" strokeWidth={2.5}
                  />
                  <text x={CX} y={CY + 12} textAnchor="middle" fontSize={32}>🏆</text>
                </motion.g>
              )}

              {/* "FINAL" label below center */}
              <text x={CX} y={CY + SZ_FINAL + 14}
                textAnchor="middle"
                fill="rgba(255,215,0,0.55)"
                fontSize={8} fontFamily="monospace" fontWeight="bold" letterSpacing="2">
                FINAL
              </text>
            </motion.g>

            {/* ── Round label pills positioned on each ring ── */}
            {[
              { r: R_TEAM + 18, label: "R32",  slotFrac: 7.5, color: "rgba(255,255,255,0.3)" },
              { r: R_R16 + 16,  label: "R16",  slotFrac: 7.5, color: "rgba(255,255,255,0.35)" },
              { r: R_QF + 14,   label: "QF",   slotFrac: 7.5, color: "rgba(255,215,0,0.4)" },
              { r: R_SF + 12,   label: "SF",   slotFrac: 7.5, color: "rgba(255,215,0,0.55)" },
            ].map(({ r, label, slotFrac, color }) => {
              const pos = slotXY(slotFrac, r);
              return (
                <text key={label}
                  x={pos.x} y={pos.y + 3}
                  textAnchor="middle" fontSize={7.5}
                  fontFamily="monospace" fontWeight="bold"
                  fill={color} letterSpacing="1.5">
                  {label}
                </text>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 pt-1 text-[10px] text-muted/60">
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full border-2 border-success/70 bg-[#101C38]" />
          Won (confirmed)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full border-2 border-cyan/60 border-dashed bg-[#101C38]" />
          Predicted to win
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full border-2 border-yellow-400/60 border-dashed bg-[#101C38]" />
          Predicted to lose
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-white/10 opacity-35" />
          Eliminated
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full border border-success/30 bg-success/10" />
          R32 qualifier (inner)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full border-2 border-gold/60" />
          SF · Final
        </span>
      </div>

      {/* Champion section */}
      {champion && (
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.92 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: 1.4, type: "spring", stiffness: 260, damping: 20 }}
          // Extra bottom margin + right padding on mobile: the fixed CAI
          // mascot/feedback widgets sit bottom-right on every page and this
          // is the last card on the page, so its text can end up directly
          // under them while scrolling past on a narrow viewport.
          className="mx-auto mb-24 max-w-xs rounded-2xl border border-gold/30 bg-gradient-to-br from-gold/8 to-transparent p-5 pr-6 text-center sm:mb-6 sm:pr-5"
        >
          <div className="text-[9px] font-bold uppercase tracking-[0.3em] text-gold/60 mb-1">
            {byId[FINAL_ID]?.played ? "🏆 World Champions" : "CAI Predicted Champion"}
          </div>
          <div className="flex items-center justify-center gap-3">
            {champFlag && (
              <img src={champFlag} alt={champion}
                className="h-10 w-16 rounded object-cover border border-gold/20" />
            )}
            <div className="gold-text font-display text-xl font-black uppercase tracking-widest">
              {champion}
            </div>
          </div>
          <div className="mt-2 text-[10px] text-gold/50">
            {byId[FINAL_ID]?.conf != null
              ? `${byId[FINAL_ID].conf}% confidence · CAI model`
              : "CAI bracket projection"}
          </div>
        </motion.div>
      )}
    </div>
  );
}

function BracketSkeleton() {
  return (
    <div className="flex flex-col items-center space-y-4 py-8">
      <div className="h-6 w-48 rounded-lg bg-white/5 animate-pulse" />
      <div className="aspect-square w-full max-w-[720px] rounded-full bg-white/3 animate-pulse" />
    </div>
  );
}
