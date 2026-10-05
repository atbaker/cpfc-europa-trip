import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import "./styles.css";
export const metadata: Metadata = { title: "Eagles Away · Powered by Temporal", description: "Your club. Your next away day. Plan your Palace trip from a UK city with Eagles Away." };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en-GB"><body><header className="masthead"><Link href="/" className="wordmark"><span className="crest" aria-hidden="true">EA</span><span>EAGLES <b>AWAY</b></span></Link><span className="sponsor">Powered by <Image className="sponsor-logo" src="/temporal-logo.png" alt="Temporal" width={105} height={31} priority /></span></header><main>{children}</main><footer><span>Your club. Your next away day.</span><Link href="/privacy/">Privacy & your data</Link><span>Travel planning only · Match tickets not included</span></footer></body></html>;
}
