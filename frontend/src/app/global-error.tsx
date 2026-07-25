"use client";

import { useEffect } from "react";

// Next.js App Router requires a DEFAULT export for special framework files
// (global-error.tsx). This is the one exception to our named-export
// convention. global-error replaces the root layout when an error is thrown
// in the layout itself, so it must render its own <html> and <body>. Styling
// is inlined because globals.css may not be applied in this fallback path.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          background: "#e8f5ee",
          color: "#1f1e1b",
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: 0,
          fontFamily:
            '"Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif',
        }}
      >
        <div style={{ maxWidth: "32rem", padding: "1.5rem", textAlign: "center" }}>
          <h1
            style={{
              fontSize: "2rem",
              fontWeight: 600,
              color: "#4a4740",
              fontFamily: '"Trebuchet MS", "Avenir Next", "Segoe UI", sans-serif',
              margin: 0,
            }}
          >
            Something went sideways
          </h1>

          <p style={{ marginTop: "1rem", fontSize: "1.125rem", color: "#78746b" }}>
            Sorry about that! Syllabuddy ran into an unexpected problem. Please
            try again.
          </p>

          <button
            type="button"
            onClick={() => reset()}
            style={{
              marginTop: "2rem",
              borderRadius: "9999px",
              border: "none",
              padding: "0.75rem 2rem",
              fontSize: "1rem",
              fontWeight: 600,
              color: "#ffffff",
              cursor: "pointer",
              background: "linear-gradient(to bottom, #4ade80, #22c55e)",
              boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
