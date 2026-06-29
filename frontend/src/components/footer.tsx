import Link from "next/link";

export function Footer() {
  return (
    <footer className="py-6 text-center text-sm text-warm-400">
      <Link
        href="/privacy"
        className="transition-colors hover:text-warm-600"
      >
        Privacy Policy
      </Link>
      <span className="mx-2 text-warm-300">·</span>
      <Link
        href="/terms"
        className="transition-colors hover:text-warm-600"
      >
        Terms of Service
      </Link>
    </footer>
  );
}
