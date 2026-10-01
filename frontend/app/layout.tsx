import type { Metadata } from "next";
import Link from "next/link";
import "./styles.css";
export const metadata: Metadata = { title: "Eagles Away · Supported by Temporal", description: "Your club. Your next away day. Plan your Palace trip from London with Eagles Away." };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en-GB"><body><header className="masthead"><Link href="/" className="wordmark"><span className="crest" aria-hidden="true">EA</span> EAGLES <span>AWAY</span></Link><span className="sponsor">Supported by <strong>Temporal</strong></span></header><main>{children}</main><footer><span>Your club. Your next away day.</span><Link href="/privacy/">Privacy & your data</Link><span>Travel planning only · Match tickets not included</span></footer></body></html>;
}
