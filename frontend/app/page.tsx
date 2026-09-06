import { PlannerForm } from "@/components/planner-form";

export default function HomePage() {
  return (
    <main>
      <section className="hero-shell">
        <div className="hero-copy">
          <p className="eyebrow">Crystal Palace · Europa League 2026/27</p>
          <h1>The away end starts with a better way there.</h1>
          <p className="hero-intro">
            Choose your Palace away fixtures. We&apos;ll piece together transport and stays,
            including less-obvious routes when the direct options get expensive.
          </p>
          <div className="promise-row" aria-label="Service promises">
            <span>One short form</span>
            <span>No booking fees</span>
            <span>Itinerary by email</span>
          </div>
        </div>
        <PlannerForm />
      </section>
      <section className="how-it-works" aria-labelledby="how-title">
        <div>
          <p className="eyebrow">Durable by design</p>
          <h2 id="how-title">You can close the tab. We keep planning.</h2>
        </div>
        <ol>
          <li>
            <strong>Tell us the away days</strong>
            <span>Pick fixtures, your starting point, party, flexibility, and travel style.</span>
          </li>
          <li>
            <strong>Compare the whole trip</strong>
            <span>We balance route, stay, transfers, timing, and realistic trade-offs.</span>
          </li>
          <li>
            <strong>Refine, then take it with you</strong>
            <span>Ask for changes or let us email the latest plan after ten quiet minutes.</span>
          </li>
        </ol>
      </section>
    </main>
  );
}

