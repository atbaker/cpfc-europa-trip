import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./styles.css";

export const metadata: Metadata = {
  title: "Crystal Palace Away Days",
  description: "Plan smarter journeys to Palace's European away fixtures.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en-GB">
      <body>
        <header className="site-header">
          <Link className="brand" href="/" aria-label="Crystal Palace Away Days home">
            <span className="brand-mark" aria-hidden="true">
              CP
            </span>
            <span>
              <strong>Palace Away Days</strong>
              <small>Europe, planned together</small>
            </span>
          </Link>
          <div className="sponsor-lockup">
            <span>Sponsored by</span>
            <strong>Temporal</strong>
          </div>
        </header>
        {children}
        <footer className="site-footer">
          <p>
            Built with Temporal in partnership with Crystal Palace Football Club. Travel
            recommendations only; we do not sell travel or match tickets.
          </p>
        </footer>
      </body>
    </html>
  );
}
