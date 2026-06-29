import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Syllabuddy — Extract assignments and due dates from your course syllabi";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "80px",
          background:
            "linear-gradient(135deg, #FDF8F2 0%, #F8EDDC 60%, #E8F5EC 100%)",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "20px",
            marginBottom: "32px",
          }}
        >
          <div
            style={{
              width: "72px",
              height: "72px",
              borderRadius: "20px",
              background: "#4FB286",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
              fontSize: "44px",
              fontWeight: 700,
            }}
          >
            S
          </div>
          <div
            style={{
              fontSize: "84px",
              fontWeight: 700,
              color: "#5A4634",
              letterSpacing: "-0.02em",
            }}
          >
            Syllabuddy
          </div>
        </div>
        <div
          style={{
            fontSize: "44px",
            color: "#7A6249",
            maxWidth: "880px",
            lineHeight: 1.25,
          }}
        >
          Extract assignments and due dates from your course syllabi.
        </div>
        <div
          style={{
            position: "absolute",
            bottom: "60px",
            left: "80px",
            fontSize: "28px",
            color: "#A38E72",
          }}
        >
          syllabuddy-pi.vercel.app
        </div>
      </div>
    ),
    { ...size }
  );
}
