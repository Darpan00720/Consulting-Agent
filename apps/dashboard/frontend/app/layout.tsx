import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import "./globals.css";
import { NavBar } from "./nav";

const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex",
  display: "swap",
});

export const metadata: Metadata = {
  title: "StratAgent — AI Consulting Engagements",
  description:
    "Run a governed, multi-agent management-consulting engagement on any business problem. Every number traceable, every conclusion stress-tested.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={plex.variable}>
      {/* suppressHydrationWarning: browser extensions (e.g. Grammarly) inject
          attributes into <body> before React hydrates — harmless mismatch */}
      <body suppressHydrationWarning>
        <NavBar />
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
