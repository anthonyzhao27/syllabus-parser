"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

// Next.js App Router requires a DEFAULT export for special framework files
// (error.tsx). This is the one exception to our named-export convention.
export default function Error({
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
    <main className="flex flex-1 items-center justify-center px-6 pb-16 pt-24 md:px-8">
      <div className="mx-auto w-full max-w-lg text-center">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-error-light">
          <AlertTriangle className="h-7 w-7 text-error" />
        </div>

        <h1 className="text-3xl font-semibold text-warm-700 font-[family-name:var(--font-quicksand)] md:text-4xl">
          Something went sideways
        </h1>

        <p className="mt-4 text-lg text-warm-500">
          Sorry about that! Syllabuddy hit an unexpected snag. You can try again,
          and if it keeps happening, head back home.
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => reset()}
            className="inline-block rounded-full px-8 py-3 text-base font-semibold text-white shadow-md transition-all duration-200 hover:shadow-lg"
            style={{
              background: "linear-gradient(to bottom, #4ade80, #22c55e)",
            }}
          >
            Try again
          </button>

          <Link
            href="/"
            className="rounded-full border border-warm-200 bg-white px-6 py-3 text-base font-semibold text-warm-600 transition-colors hover:border-mint-300 hover:text-warm-700"
          >
            Go home
          </Link>
        </div>
      </div>
    </main>
  );
}
