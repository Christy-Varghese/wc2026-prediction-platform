/* Derives squad-level attribute ratings from individual player `impact`
 * scores — the only place these ratings exist (there's no separate
 * "attack_rating"/"defence_rating" field anywhere in the API). Originally
 * inlined in app/teams/[name]/page.tsx; extracted here once a second
 * consumer (final-match head-to-head) needed the same calculation. */

export type SquadPlayer = {
  position?: string;
  impact?: number;
  fitness?: string;
  [key: string]: unknown;
};

export type TeamAttributes = {
  attack: number;
  midfield: number;
  defence: number;
  benchDepth: number;
  fitPct: number;
};

const avg = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);

export function computeTeamAttributes(squad: SquadPlayer[]): TeamAttributes {
  const byPos = {
    GK: squad.filter((p) => p.position === "GK"),
    DEF: squad.filter((p) => p.position === "DF" || p.position === "DEF"),
    MID: squad.filter((p) => p.position === "MF" || p.position === "MID"),
    FWD: squad.filter((p) => p.position === "FW" || p.position === "FWD"),
  };
  const allImpact = squad.map((p) => p.impact ?? 0);

  const attack = avg(byPos.FWD.map((p) => p.impact ?? 0)) || avg(allImpact);
  const midfield = avg(byPos.MID.map((p) => p.impact ?? 0)) || avg(allImpact);
  const defence = avg([...byPos.DEF, ...byPos.GK].map((p) => p.impact ?? 0)) || avg(allImpact);

  // Bench depth: avg impact of players ranked 12th+ by impact (beyond a
  // nominal starting XI) — a derived proxy, not a modeled "bench depth"
  // stat, since no such field exists in the squad data.
  const sorted = [...squad].sort((a, b) => (b.impact ?? 0) - (a.impact ?? 0));
  const benchDepth = avg(sorted.slice(11).map((p) => p.impact ?? 0)) || avg(allImpact);

  const fitPct = squad.length
    ? (squad.filter((p) => p.fitness === "fit").length / squad.length) * 100
    : 100;

  return { attack, midfield, defence, benchDepth, fitPct };
}
