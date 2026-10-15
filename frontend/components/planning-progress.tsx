"use client";
import { useEffect, useState } from "react";
import type { Snapshot } from "../lib/api";
import { type Stage, stageFor, tickerLines } from "../lib/planning";

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return reduced;
}

// Rotates only while active; pauses when the tab is hidden so no timer runs unseen.
function useTicker(active: boolean, count: number): number {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => { if (!document.hidden) setIndex(n => (n + 1) % count); }, 3500);
    return () => clearInterval(timer);
  }, [active, count]);
  return active ? index : 0;
}

// Decorative, phase-anchored progress. The .status live region in PlanExperience
// announces actual phase changes without repeating the rotating copy visually.
export function PlanningProgress({ snapshot, city, origin = "London", variant = "hero", forceDone = false }: {
  snapshot: Snapshot | null;
  city?: string;
  origin?: string;
  variant?: "hero" | "preview";
  forceDone?: boolean;
}) {
  const reduced = useReducedMotion();
  const stage: Stage = forceDone ? "done" : stageFor(snapshot, { ignoreItinerary: variant === "preview" });
  const lines = variant === "preview" ? [
    city ? `Checking places to stay in ${city}…` : "Checking places to stay…",
    "Comparing available rooms and prices…",
    "Looking for better journey options…",
  ] : tickerLines(stage, city, origin);
  const index = useTicker((stage === "preferences" || stage === "searching") && !reduced, lines.length);
  const rotatingText = lines[index];

  if (variant === "preview") {
    return <p className="ticker inline" aria-hidden="true"><span key={reduced ? "static" : index} className={reduced ? undefined : "tfade"}>{rotatingText}</span></p>;
  }

  const destination = city ?? "the away end";
  const routeMessage = stage === "done" ? "Your route is ready."
    : stage === "searching" ? "We’re weighing travel and stays against your preferences."
    : "We’re turning your trip brief into an away day.";

  return <div className="plan-progress panel" aria-hidden="true">
    <p className="ticker hero"><span key={reduced ? "static" : `${stage}-${index}`} className={reduced ? undefined : "tfade"}>{rotatingText}</span></p>
    <div className={`journey-card ${stage}`}>
      <div className="journey-card-heading"><span className="card-label">YOUR AWAY DAY</span><span className="journey-card-badge">{stage === "done" ? "READY" : "IN THE MAKING"}</span></div>
      <div className="journey-route">
        <div className="journey-city"><span className="journey-pin" /><small>STARTING FROM</small><strong>{origin}</strong></div>
        <div className="journey-arc"><svg viewBox="0 0 320 90" preserveAspectRatio="none" focusable="false"><path d="M 10 72 Q 160 -35 310 72" /></svg><span className="journey-plane">✈</span></div>
        <div className="journey-city destination"><span className="journey-pin" /><small>HEADING TO</small><strong>{destination}</strong></div>
      </div>
      <p className="journey-note">{routeMessage}</p>
    </div>
  </div>;
}
