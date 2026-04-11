import Link from "next/link";

export function Footer() {
  return (
    <footer className="py-6 text-center">
      <Link
        href="/privacy"
        className="text-sm text-warm-400 transition-colors hover:text-warm-600"
      >
        Privacy Policy
      </Link>
    </footer>
  );
}
