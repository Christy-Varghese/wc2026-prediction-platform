"use client";
/* KIS chaos-tagged match-flow timeline — KIS_SPEC.md §5.5. Renders
   `result.match_flow` from POST /api/v1/predict/kis, where goal events carry
   a `vector_dominant: "skill" | "luck"` tag (kis_engine.narrate_with_chaos()).
   This is the vertical chronological match-flow timeline the original
   request asked for, distinguished from the reused MatchFlowReport's plain
   "Projected flow" list by the skill/luck visual split. */

export function KisChaosTimeline({ result }: { result: any }) {
  const events: any[] = result?.match_flow ?? [];
  if (!events.length) return null;
  const luckCount = events.filter(e => e.vector_dominant === "luck").length;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-widest text-muted">
          Match-Flow Timeline · Skill vs Luck
        </div>
        {luckCount > 0 && (
          <span className="chip text-[9px] text-chaos border-chaos/30 bg-chaos/10">
            ⚡ {luckCount} luck-dominant event{luckCount > 1 ? "s" : ""}
          </span>
        )}
      </div>

      <ol className="relative space-y-2 border-l border-white/10 pl-4">
        {events.map((e, i) => {
          const isLuck = e.vector_dominant === "luck";
          const isGoal = e.type === "goal" || e.type === "shootout";
          const dotColor = !isGoal ? "bg-white/20" : isLuck ? "bg-chaos" : "bg-success";
          return (
            <li key={i} className="relative">
              <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-ink">
                <span className={`block h-full w-full rounded-full ${dotColor}`} />
              </span>
              <div className="flex gap-2 text-[12px] leading-snug">
                <span className="w-9 shrink-0 text-right font-bold tabnum text-gold/80">{e.minute}′</span>
                <span className={isGoal ? "font-medium text-stadium" : "text-muted"}>
                  {isGoal ? (e.type === "goal" ? "⚽ " : "🎯 ") : ""}
                  {e.text}
                  {isGoal && (
                    <span className={`ml-2 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide
                      ${isLuck ? "bg-chaos/15 text-chaos" : "bg-success/15 text-success"}`}>
                      {isLuck ? "luck" : "skill"}
                    </span>
                  )}
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      <p className="mt-3 text-[10px] leading-snug text-muted/70">
        Skill/luck tagging is a narrative overlay derived from the fixture's
        overall chaos-event rate ({((result?.chaos_events?.run_rate ?? 0) * 100).toFixed(1)}%
        of simulated runs) — it flags which goals in this projected flow line
        up with the model's expectation vs. a tail-probability swing, not a
        claim about any specific real goal.
      </p>
    </div>
  );
}
