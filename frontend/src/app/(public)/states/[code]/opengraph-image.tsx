import { ImageResponse } from "next/og";
import { SITE_NAME } from "@/lib/site";
import { getStateNameFromCode } from "@/lib/states";

export const alt = "State voting record on Operation Child Shield";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

interface StateImageProps {
  params: Promise<{ code: string }>;
}

export default async function Image({ params }: StateImageProps) {
  const { code } = await params;
  const upper = (code || "").toUpperCase();
  const stateName = getStateNameFromCode(upper) ?? upper;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          justifyContent: "space-between",
          padding: "64px 72px",
          backgroundColor: "#0b1220",
          backgroundImage: "linear-gradient(120deg, #0b1220 45%, #1e40af 100%)",
          color: "#ffffff",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "100%",
          }}
        >
          <span style={{ fontSize: 24, letterSpacing: 6, color: "#fca5a5" }}>
            {SITE_NAME.toUpperCase()}
          </span>

          <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 190,
                height: 190,
                borderRadius: 24,
                backgroundColor: "rgba(255,255,255,0.12)",
                fontSize: 84,
                fontWeight: 700,
                letterSpacing: 2,
              }}
            >
              {upper}
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: 26, color: "#93c5fd", letterSpacing: 2 }}>
                STATE OVERVIEW
              </span>
              <span
                style={{
                  fontSize: stateName.length > 14 ? 62 : 78,
                  fontWeight: 700,
                  marginTop: 12,
                  lineHeight: 1.05,
                }}
              >
                {stateName}
              </span>
              <span style={{ fontSize: 28, color: "#cbd5e1", marginTop: 18 }}>
                How its House members voted on tracked child safety bills
              </span>
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
            <span>Recorded House roll-call votes</span>
            <span>operationchildshield.org</span>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
