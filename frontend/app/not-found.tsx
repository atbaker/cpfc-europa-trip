import Link from "next/link";

export default function NotFound() {
  return <article className="plan panel">
    <p className="eyebrow">PAGE NOT FOUND</p>
    <h1>This page isn’t here.</h1>
    <p>The link may be out of date. You can start a new trip brief instead.</p>
    <Link href="/">Start a trip brief <span className="arrow">→</span></Link>
  </article>;
}
