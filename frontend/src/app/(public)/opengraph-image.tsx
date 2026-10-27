import { ImageResponse } from "next/og";
import { SITE_NAME } from "@/lib/site";

export const alt = `${SITE_NAME}: child safety voting records from Congress.gov`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** Sitewide fallback social card for every public page. */
export default function Image() {
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
          color: "#ffffff",
          backgroundImage: "linear-gradient(135deg, #1e40af 0%, #0b1220 62%)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 18,
              height: 64,
              backgroundColor: "#b91c1c",
              borderRadius: 4,
            }}
          />
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: 22, letterSpacing: 8, color: "#fca5a5" }}>
              OPERATION
            </span>
            <span style={{ fontSize: 44, fontWeight: 700, letterSpacing: 2 }}>
              CHILD SHIELD
            </span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 62, fontWeight: 700, lineHeight: 1.1 }}>
            How Congress voted on
          </span>
          <span style={{ fontSize: 62, fontWeight: 700, lineHeight: 1.1 }}>
            child safety bills
          </span>
          <span style={{ fontSize: 28, color: "#cbd5e1", marginTop: 24 }}>
            A 501(c)(3) public record built from the Congress.gov API
          </span>
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
          <span>Protect · Educate · Mobilize</span>
          <span>operationchildshield.org</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
