import { redirect } from "next/navigation";

// Dropped from nav once the tournament finished (2026-07-19) — every
// knockout tie is resolved, so there's no "up next" left to show.
export default function LivePage() {
  redirect("/matches");
}
