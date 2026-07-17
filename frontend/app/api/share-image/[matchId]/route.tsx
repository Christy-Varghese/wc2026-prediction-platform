/* Server-rendered share card for a knockout tie, used by
 * final-match/share-prediction.tsx's "Download as Image" button. Uses
 * Next's built-in next/og ImageResponse rather than a new client-side
 * screenshot dependency. Reads straight from the pre-generated snapshot
 * (same file the client-side snapshot fallback in lib/api.ts serves) so it
 * works identically on the backend-free deployed demo. */
import { ImageResponse } from "next/og";
import fs from "node:fs";
import path from "node:path";

export const runtime = "nodejs";

function loadMatch(matchId: string) {
  const file = path.join(process.cwd(), "public", "snapshot", "api_knockout.json");
  const raw = fs.readFileSync(file, "utf-8");
  const data = JSON.parse(raw);
  return (data.matches ?? []).find((m: any) => String(m.id) === matchId);
}

export async function GET(req: Request, { params }: { params: { matchId: string } }) {
  const { searchParams } = new URL(req.url);
  const m = loadMatch(params.matchId);
  if (!m) return new Response("Match not found", { status: 404 });

  const yourWinner = searchParams.get("yourWinner");
  const yourScore = searchParams.get("yourScore");

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%", height: "100%", display: "flex", flexDirection: "column",
          background: "linear-gradient(180deg, #0F1D3D 0%, #071226 100%)",
          color: "#FFFFFF", padding: 56,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 22, color: "#8FA0C8" }}>
          <span>{m.round} · WC 2026</span>
          <span>{m.venue}, {m.city}</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flex: 1, marginTop: 24 }}>
          <TeamBlock name={m.home_team} flag={m.home_flag} />
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div style={{ display: "flex", fontSize: 72, fontWeight: 900, color: "#FFD700" }}>{m.predicted_score}</div>
            <div style={{ display: "flex", fontSize: 16, color: "#8FA0C8", letterSpacing: 4, textTransform: "uppercase" }}>
              AI Predicted
            </div>
          </div>
          <TeamBlock name={m.away_team} flag={m.away_flag} />
        </div>

        {yourWinner && (
          <div
            style={{
              display: "flex", justifyContent: "center", marginTop: 16,
              fontSize: 26, color: "#00D4FF", fontWeight: 700,
            }}
          >
            My prediction: {yourWinner}{yourScore ? ` (${yourScore})` : ""}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "center", marginTop: 24, fontSize: 14, color: "#8FA0C8" }}>
          AI-driven probability simulation · entertainment &amp; analytics, not betting advice
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}

function TeamBlock({ name, flag }: { name: string; flag?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 340 }}>
      {flag && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={flag} width={110} height={78} style={{ borderRadius: 8, marginBottom: 16 }} alt="" />
      )}
      <div style={{ display: "flex", fontSize: 30, fontWeight: 700, textAlign: "center" }}>{name}</div>
    </div>
  );
}
