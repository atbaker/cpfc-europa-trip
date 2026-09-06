import { Suspense } from "react";

import { PlanExperience } from "@/components/plan-experience";

export default function PlanPage() {
  return (
    <main className="plan-page">
      <Suspense fallback={<PlanLoading />}>
        <PlanExperience />
      </Suspense>
    </main>
  );
}

function PlanLoading() {
  return (
    <section className="plan-shell" aria-live="polite">
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-card" />
      <p className="status-line">Opening your planning session…</p>
    </section>
  );
}

