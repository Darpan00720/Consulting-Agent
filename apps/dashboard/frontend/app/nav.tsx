"use client";

import Link from "next/link";

// Lucide "network" mark — SVG per design-system rule (no emoji icons)
function Logo() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="16" y="16" width="6" height="6" rx="1" />
      <rect x="2" y="16" width="6" height="6" rx="1" />
      <rect x="9" y="2" width="6" height="6" rx="1" />
      <path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3" />
      <path d="M12 12V8" />
    </svg>
  );
}

export function NavBar() {
  return (
    <nav className="nav">
      <Link href="/" className="brand">
        <Logo />
        StratAgent
      </Link>
      <div className="links">
        <Link href="/engagements">Engagements</Link>
        <Link href="/benchmark">Benchmark</Link>
        <Link href="/lessons">Lessons</Link>
        <Link href="/settings">API key</Link>
      </div>
    </nav>
  );
}
