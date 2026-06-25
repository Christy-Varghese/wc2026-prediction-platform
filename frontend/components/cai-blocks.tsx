"use client";
import { Flag } from "@/components/ui";

const pctStr = (x?: number) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

/* ── CAI 3-scenario projection (Base / Upside / Downside) ─────────────────── */
export function CaiScenarios({ scenarios, knockout = false }:
  { scenarios?: any[]; knockout?: boolean }) {
  if (!scenarios?.length) return null;
  return (
    <section>
      <div className="mb-1 flex items-center gap-2">
        <h2 className="font-display text-lg font-bold">CAI runs it three ways</h2>
        <span className="chip text-[10px]">form-led · xG</span>
      </div>
      <p className="mb-3 text-[12px] text-muted">
        CAI weights this year's matches, the group stage and live momentum over pre-tournament
        data, then projects the goal flow under three outcomes.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {scenarios.map((s) => <ScenarioCard key={s.key} s={s} />)}
      </div>
    </section>
  );
}

function ScenarioCard({ s }: { s: any }) {
  const accent = s.key === "upside" ? "border-success/40"
    : s.key === "downside" ? "border-live/40" : "border-gold/40";
  const tag = s.result === "penalties" ? "→ pens" : s.result === "draw" ? "draw" : "in 90'";
  return (
    <div className={`card border ${accent} p-3`}>
      <div className="mb-1 flex items-center justify-between">
        <span className="font-display text-[12px] font-bold">{s.label}</span>
        {s.likelihood != null && <span className="text-[10px] text-muted">{Math.round(s.likelihood * 100)}%</span>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-display text-2xl font-bold tabular-nums text-gold">{s.score}</span>
        <span className="text-[10px] uppercase tracking-widest text-muted">{tag}</span>
      </div>
      <div className="mt-0.5 text-[11px] text-muted">xG {s.xg?.home}–{s.xg?.away}</div>
      <p className="mt-1.5 text-[12px] leading-snug text-stadium">{s.note}</p>
    </div>
  );
}

/* ── CAI pain points (per side vulnerabilities) ──────────────────────────── */
export function CaiPainPoints({ home, away, painPoints }:
  { home: string; away: string; painPoints?: Record<string, string[]> }) {
  if (!painPoints) return null;
  return (
    <section className="card p-5">
      <h2 className="mb-3 font-display text-lg font-bold">Pain points — where it could swing</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {[home, away].map((t) => (
          <div key={t}>
            <h3 className="mb-1.5 font-display text-sm font-bold text-gold">{t}</h3>
            <ul className="space-y-1 text-[13px] leading-snug text-stadium">
              {(painPoints[t] ?? []).map((p, k) => (
                <li key={k} className="flex gap-2"><span className="text-live">⚠</span><span>{p}</span></li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ── why the favoured side wins (condition / manager / GK / xG bars) ──────── */
export function CaiCompareBar({ label, h, a, fmt = pctStr }:
  { label: string; h?: number; a?: number; fmt?: (v?: number) => string }) {
  const hv = h ?? 0, av = a ?? 0, max = 1;
  const hLead = hv >= av;
  return (
    <div>
      <div className="mb-0.5 flex justify-between text-[11px]">
        <span className={hLead ? "font-bold text-gold" : "text-muted"}>{fmt(h)}</span>
        <span className="text-muted">{label}</span>
        <span className={!hLead ? "font-bold text-gold" : "text-muted"}>{fmt(a)}</span>
      </div>
      <div className="flex h-2 gap-1">
        <div className="flex flex-1 justify-end">
          <div className={`h-full rounded-l-full ${hLead ? "bg-gold/80" : "bg-white/20"}`}
            style={{ width: `${Math.min(100, (hv / max) * 100)}%` }} />
        </div>
        <div className="flex flex-1 justify-start">
          <div className={`h-full rounded-r-full ${!hLead ? "bg-gold/80" : "bg-white/20"}`}
            style={{ width: `${Math.min(100, (av / max) * 100)}%` }} />
        </div>
      </div>
    </div>
  );
}

/* ── 3 key players to note, per team, with images ────────────────────────── */
export function KeyPlayersToNote({ home, away, keyPlayers, flags }:
  { home: string; away: string; keyPlayers: Record<string, any>; flags: Record<string, string | undefined> }) {
  return (
    <section>
      <h2 className="mb-3 font-display text-lg font-bold">3 key players to note</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {[home, away].map((t) => (
          <div key={t} className="card p-4">
            <div className="mb-3 flex items-center gap-2">
              <Flag url={flags[t]} name={t} size={22} />
              <h3 className="font-display text-sm font-bold">{t}</h3>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {((keyPlayers[t]?.attacking ?? keyPlayers[t] ?? []) as any[]).slice(0, 3).map((pl) => (
                <KeyPlayer key={pl.name} p={pl} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function KeyPlayer({ p }: { p: any }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-white/10 bg-white/[0.02] p-2 text-center">
      <div className="relative mb-1 h-16 w-16 overflow-hidden rounded-full border border-gold/30 bg-white/5">
        {p.photo_url
          ? <img src={p.photo_url} alt={p.name} className="h-full w-full object-cover"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          : <div className="grid h-full w-full place-items-center text-lg text-muted">⚽</div>}
        {p.fitness && p.fitness !== "fit" && (
          <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 rounded-full bg-live px-1 text-[8px] font-bold text-white">
            {p.fitness}
          </span>
        )}
      </div>
      <div className="w-full truncate font-display text-[11px] font-bold leading-tight" title={p.name}>{p.name}</div>
      <div className="text-[9px] text-muted">{p.position ?? p.pos} · {p.club ?? ""}</div>
      <div className="mt-0.5 flex items-center gap-1.5 text-[9px]">
        {p.impact != null && <span className="rounded bg-gold/15 px-1 text-gold">{p.impact} imp</span>}
        {p.goals != null && p.goals > 0 && <span className="text-stadium">{p.goals}⚽</span>}
        {p.xg != null && <span className="text-muted">{p.xg}xG</span>}
      </div>
    </div>
  );
}

/* ── CAI verdict chip: what the model called, and (if played) if it was right ─ */
export function CaiVerdict({ predictedWinner, home, away, played, actualWinner }:
  { predictedWinner?: string; home: string; away: string; played?: boolean; actualWinner?: string }) {
  if (!predictedWinner) return null;
  const call = predictedWinner === "Draw" ? "a draw"
    : `${predictedWinner} to ${predictedWinner === home || predictedWinner === away ? "win" : "advance"}`;
  const right = played && actualWinner != null ? predictedWinner === actualWinner : null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-gold/10 p-3 text-sm">
      <span className="text-[11px] uppercase tracking-widest text-gold/80">CAI called</span>
      <span className="font-bold text-gold">{call}</span>
      {right != null && (
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-bold ${
          right ? "bg-success/20 text-success" : "bg-live/20 text-live"}`}>
          {right ? "✓ correct" : "✗ missed"}
        </span>
      )}
    </div>
  );
}
