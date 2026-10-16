import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Inter } from "next/font/google";
import { AnalyticsConsent } from "../components/analytics-consent";
import "./styles.css";
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
export const metadata: Metadata = { title: "Eagles Away · Powered by Temporal", description: "Your club. Your next away day. Plan your Palace trip from a UK city with Eagles Away." };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en-GB"><body className={inter.variable}>
    <header className="masthead">
      <Link href="/" className="wordmark"><span className="ea-mark" aria-hidden="true">EA</span><span>EAGLES <b>AWAY</b></span></Link>
      <span className="club-credit"><span>Built for</span><Image className="club-crest" src="/cpfc-primary-badge.png" alt="Crystal Palace F.C. crest" width={681} height={846} priority /></span>
      <span className="sponsor">Powered by <Image className="sponsor-logo" src="/temporal-logo.webp" alt="Temporal" width={105} height={31} priority /></span>
    </header>
    <main>{children}</main>
    <footer><span>Your club. Your next away day.</span><span><Link href="/privacy/">Privacy & your data</Link> · <a href="https://github.com/temporal-community/Eagles-Away">GitHub</a></span><span>Travel planning only · Match tickets not included</span><AnalyticsConsent /></footer>
  </body></html>;
}
