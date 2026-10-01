import { Suspense } from "react";
import { PlanExperience } from "../../components/plan-experience";
export default function Plan() { return <Suspense fallback={<p>Loading your trip…</p>}><PlanExperience /></Suspense>; }
