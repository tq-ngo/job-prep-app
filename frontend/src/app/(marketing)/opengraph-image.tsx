import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "JobPrep — Software engineering internships in one feed";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          backgroundColor: "#f8fafd",
          color: "#1f1f1f",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: 999,
              backgroundColor: "#0b57d0",
            }}
          />
          <span style={{ fontSize: 30, fontWeight: 700, letterSpacing: "-0.02em", color: "#1f1f1f" }}>
            JobPrep
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 22, maxWidth: 960 }}>
          <div
            style={{
              fontSize: 66,
              fontWeight: 700,
              lineHeight: 1.08,
              letterSpacing: "-0.03em",
              color: "#1f1f1f",
            }}
          >
            Every SWE internship, deduplicated and live
          </div>
          <div style={{ fontSize: 28, lineHeight: 1.4, color: "#444746" }}>
            Hourly GitHub and LinkedIn crawls with extracted skills, pay ranges, and visa sponsorship tags.
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            paddingTop: 24,
            borderTop: "1px solid #c4c7c5",
            fontSize: 22,
            color: "#444746",
          }}
        >
          <span
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              backgroundColor: "#d3e3fd",
              color: "#041e49",
              fontWeight: 600,
            }}
          >
            Hourly crawls
          </span>
          <span>GitHub &amp; LinkedIn</span>
          <span>·</span>
          <span>Skill extraction</span>
          <span>·</span>
          <span>Live feed updates</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
