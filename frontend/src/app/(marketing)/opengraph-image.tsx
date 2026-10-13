import { ImageResponse } from "next/og";

// Social preview for the landing page. The layout declared a
// summary_large_image card but shipped no image, so shares had no preview.
export const alt = "JobPrep — automated tech career command center";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
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
          background: "#faf9f5",
          color: "#141413",
          fontFamily: "Georgia, serif",
        }}
      >
        <div style={{ fontSize: 40, color: "#1b3b2b", display: "flex" }}>JobPrep</div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 76, lineHeight: 1.1, letterSpacing: -1, display: "flex", flexWrap: "wrap" }}>
            Your automated&nbsp;<span style={{ color: "#1b3b2b", fontStyle: "italic" }}>tech career</span>&nbsp;command center.
          </div>
          <div style={{ fontSize: 30, color: "#57544d", marginTop: 28, fontFamily: "sans-serif", display: "flex" }}>
            SWE internships from GitHub &amp; LinkedIn · AI skill extraction · live updates
          </div>
        </div>
      </div>
    ),
    size,
  );
}
