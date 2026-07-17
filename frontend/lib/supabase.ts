import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(url, key);

export type FeedbackRow = {
  name?: string;
  rating: number;
  message: string;
  page?: string;
};

export async function submitFeedback(data: FeedbackRow) {
  const { error } = await supabase.from("feedback").insert([data]);
  if (error) throw error;
}

/* ── Fan voting (final-match fan-vote.tsx) ──────────────────────────────── */
export type VoteRow = {
  match_id: number;
  choice: string;
};

export async function submitVote(data: VoteRow) {
  const { error } = await supabase.from("votes").insert([data]);
  if (error) throw error;
}

export async function getVoteCounts(matchId: number, choices: string[]): Promise<Record<string, number>> {
  const counts = await Promise.all(
    choices.map((choice) =>
      supabase.from("votes").select("*", { count: "exact", head: true })
        .eq("match_id", matchId).eq("choice", choice)
    )
  );
  const firstError = counts.find((c) => c.error)?.error;
  if (firstError) throw firstError;
  const result: Record<string, number> = {};
  choices.forEach((choice, i) => {
    result[choice] = counts[i].count ?? 0;
  });
  return result;
}
