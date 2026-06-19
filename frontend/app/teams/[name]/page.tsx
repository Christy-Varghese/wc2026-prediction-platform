"use client";
import useSWR from "swr";
import { api, pct } from "@/lib/api";
import { Flag, StatRow, Meter } from "@/components/ui";

const fetcher = (p: string) => api(p);

const avg = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);

export default function TeamPage({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  const { data, error } = useSWR(`/api/teams/${encodeURIComponent(name)}`, fetcher);
  if (error) return <div className="card text-danger">Team not found.</div>;
  if (!data) return <p className="text-muted">Loading…</p>;
  const prog = data.progression;
  const sq = data.squad || [];
  const attack = avg(sq.filter((p: any) => p.position === "FW").map((p: any) => p.impact))
    || data.strength_index;
  const midfield = avg(sq.filter((p: any) => p.position === "MF").map((p: any) => p.impact))
    || data.strength_index;
  const defense = avg(sq.filter((p: any) => ["DF", "GK"].includes(p.position)).map((p: any) => p.impact))
    || data.strength_index;
  const depth = Math.min(100, sq.length * 4 + avg(sq.map((p: any) => p.impact)));

  return (
    <div className="space-y-6">
      <section className="card flex items-center gap-4">
        <Flag url={data.flag_url} name={name} size={48} />
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{name}</h1>
          <p className="text-sm text-muted">
            Group {data.group} · {data.confederation || "—"} · Manager{" "}
            {data.manager || "—"}
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-muted">Strength index</div>
          <div className="text-3xl font-extrabold text-acc tabnum">{data.strength_index}</div>
        </div>
      </section>

      <section className="card">
        <h2 className="h2">Team Profile</h2>
        <div className="grid gap-x-8 sm:grid-cols-2">
          <Meter label="Attack" value={attack} color="#2FBF71" />
          <Meter label="Defense" value={defense} color="#4aa8ff" />
          <Meter label="Midfield" value={midfield} color="#E8C66B" />
          <Meter label="Squad depth" value={depth} color="#C9D2E3" />
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="card">
          <h2 className="h2">Tournament Progression</h2>
          {prog ? (
            <>
              <StatRow label="Advance from group" value={pct(prog.advance_R32)} />
              <StatRow label="Reach quarter-final" value={pct(prog.reach_QF)} />
              <StatRow label="Reach semi-final" value={pct(prog.reach_SF)} />
              <StatRow label="Reach final" value={pct(prog.reach_Final)} />
              <StatRow label="Win the title" value={
                <span className="text-acc">{pct(prog.win_title)}</span>} />
            </>
          ) : <p className="text-muted text-sm">Run the simulator to populate odds.</p>}
        </section>

        <section className="card">
          <h2 className="h2">Group Rivals</h2>
          {data.group_rivals?.map((r: string) => (
            <div key={r} className="border-b border-line py-2 text-sm">{r}</div>
          ))}
        </section>
      </div>

      <section className="card">
        <h2 className="h2">Squad</h2>
        <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead><tr className="text-xs text-muted">
            <th className="py-1 text-left">Player</th><th>Pos</th><th>Club</th>
            <th className="text-right">G</th><th className="text-right">A</th>
            <th className="text-right">xG</th><th className="text-right">Impact</th>
            <th className="text-right">Fit</th>
          </tr></thead>
          <tbody>
            {data.squad.map((p: any) => (
              <tr key={p.name} className="border-t border-line">
                <td className="py-1.5">{p.name}</td>
                <td className="text-center"><span className="chip">{p.position}</span></td>
                <td className="text-center text-muted">{p.club}</td>
                <td className="text-right tabnum">{p.goals}</td>
                <td className="text-right tabnum">{p.assists}</td>
                <td className="text-right tabnum">{p.xg}</td>
                <td className="text-right tabnum text-acc">{p.impact}</td>
                <td className="text-right">
                  <span className={p.fitness === "fit" ? "text-acc"
                    : p.fitness === "doubt" ? "text-warn" : "text-danger"}>
                    {p.fitness}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>
    </div>
  );
}
