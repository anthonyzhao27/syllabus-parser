import Link from "next/link";
import { Compass } from "lucide-react";

// Next.js App Router requires a DEFAULT export for special framework files
// (not-found.tsx). This is the one exception to our named-export convention.
export default function NotFound() {
  return (
    <main className="flex flex-1 items-center justify-center px-6 pb-16 pt-24 md:px-8">
      <div className="mx-auto w-full max-w-lg text-center">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-mint-50">
          <Compass className="h-7 w-7 text-mint-600" />
        </div>

        <p className="text-sm font-semibold uppercase tracking-wide text-mint-600">
          404
        </p>

        <h1 className="mt-2 text-3xl font-semibold text-warm-700 font-[family-name:var(--font-quicksand)] md:text-4xl">
          We can&apos;t find that page
        </h1>

        <p className="mt-4 text-lg text-warm-500">
          The page you&apos;re looking for may have moved or never existed.
          Let&apos;s get you back on track.
        </p>

        <div className="mt-8">
          <Link
            href="/"
            className="inline-block rounded-full px-8 py-3 text-base font-semibold text-white shadow-md transition-all duration-200 hover:shadow-lg"
            style={{
              background: "linear-gradient(to bottom, #4ade80, #22c55e)",
            }}
          >
            Go home
          </Link>
        </div>
      </div>
    </main>
  );
}
