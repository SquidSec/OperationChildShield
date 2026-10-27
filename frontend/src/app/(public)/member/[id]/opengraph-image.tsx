import { ImageResponse } from "next/og";
import { getReportCard } from "@/lib/api";
import { formatDisplayName } from "@/lib/format";
import { SITE_NAME } from "@/lib/site";

export const alt = "Member voting record on Operation Child Shield";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

interface MemberImageProps {
  params: Promise<{ id: string }>;
}

export default async function Image({ params }: MemberImageProps) {
  const { id } = await params;

  let name = "How they voted";
  let subtitle = "Child safety voting record";
  let party: string | null = null;

  try {
    const card = await getReportCard(id);
    name = formatDisplayName(card.name);
    const prefix = card.chamber === "Senate" ? "Sen." : "Rep.";
    subtitle = `${prefix} ${card.state}${card.district ? `-${card.district}` : ""}`;
    party = card.party || null;
  } catch {
    // Fall back to a generic card; the page itself handles the error state.
  }

  const partyColor =
    party === "Democrat" ? "#1d4ed8" : party === "Republican" ? "#b91c1c" : "#475569";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          backgroundColor: "#0b1220",
          backgroundImage: "linear-gradient(150deg, #1e40af 0%, #0b1220 70%)",
          color: "#ffffff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 24, letterSpacing: 6, color: "#fca5a5" }}>
            {SITE_NAME.toUpperCase()}
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 26, color: "#93c5fd", letterSpacing: 2 }}>
            CHILD SAFETY VOTING RECORD
          </span>
          <span
            style={{
              fontSize: name.length > 22 ? 62 : 78,
              fontWeight: 700,
              marginTop: 16,
              lineHeight: 1.05,
            }}
          >
            {name}
          </span>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              marginTop: 26,
            }}
          >
            <span style={{ fontSize: 30, color: "#e2e8f0" }}>{subtitle}</span>
            {party ? (
              <span
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: "#ffffff",
                  backgroundColor: partyColor,
                  padding: "6px 16px",
                  borderRadius: 999,
                }}
              >
                {party}
              </span>
            ) : null}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 24,
            color: "#93c5fd",
            borderTop: "2px solid rgba(255,255,255,0.2)",
            paddingTop: 24,
          }}
        >
          <span>Every tracked vote, bill by bill</span>
          <span>operationchildshield.org</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
