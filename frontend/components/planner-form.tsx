"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Brief, Fixture, londonDayBoundary, request } from "../lib/api";

const stepNames = ["Matches & dates", "Travel preferences", "Your details"] as const;

export function PlannerForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const hasChangedStep = useRef(false);
  const attempt = useRef<{ id: string; token: string; body: string } | null>(null);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [step, setStep] = useState(0);
  const [budget, setBudget] = useState<Brief["budget_tier"]>("value");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sample, setSample] = useState(false);

  useEffect(() => {
    let cancelled = false;
    request<{ fixtures: Fixture[]; development_mode: boolean }>("/api/catalog")
      .then(data => {
        if (cancelled || !data) return;
        const upcoming = data.fixtures.filter(f => new Date(f.kickoff_at) > new Date());
        setFixtures(upcoming);
        setSelected(upcoming.slice(0, 1).map(f => f.id));
        setSample(data.development_mode);
      })
      .catch(() => { if (!cancelled) setError("The planner is unavailable. Please reload to try again."); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (hasChangedStep.current) headingRef.current?.focus();
  }, [step]);

  function moveTo(next: number) {
    hasChangedStep.current = true;
    setError("");
    setStep(next);
  }

  function nextStep() {
    if (step === 0 && !selected.length) {
      setError("Choose at least one away match to continue.");
      return;
    }
    const page = formRef.current?.querySelector<HTMLElement>(`[data-form-step="${step}"]`);
    const invalid = Array.from(page?.querySelectorAll<HTMLInputElement | HTMLSelectElement>("input, select") ?? [])
      .find(field => !field.checkValidity());
    if (invalid) { invalid.reportValidity(); return; }
    if (step === 0 && selected.some(id => {
      const start = formRef.current?.elements.namedItem(`start-${id}`) as HTMLInputElement | null;
      const end = formRef.current?.elements.namedItem(`end-${id}`) as HTMLInputElement | null;
      return Boolean(start?.value) !== Boolean(end?.value) || Boolean(start?.value && end?.value && start.value > end.value);
    })) {
      setError("For each match, enter a departure and return date in order, or leave both blank.");
      return;
    }
    moveTo(step + 1);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (step !== 2 || !selected.length) return;
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const brief: Brief = {
      fixture_ids: selected,
      travellers: { adults, child_ages: children, rooms: Number(form.get("rooms")) },
      budget_tier: budget,
      flexibility: form.get("flexibility") as Brief["flexibility"],
      windows: selected.flatMap(id => {
        const start = String(form.get(`start-${id}`) ?? "");
        const end = String(form.get(`end-${id}`) ?? "");
        return start && end ? [{ fixture_id: id, earliest_departure: londonDayBoundary(start), latest_return: londonDayBoundary(end, true) }] : [];
      }),
      private_room: form.get("private_room") === "on",
      private_bathroom: form.get("private_bathroom") === "on",
      transport_mode: (form.get("transport") || null) as Brief["transport_mode"],
      extra_instructions: String(form.get("instructions") ?? ""),
    };
    const content = JSON.stringify({ email: form.get("email"), brief });
    if (!attempt.current || attempt.current.body !== content) {
      attempt.current = { id: crypto.randomUUID(), token: [...crypto.getRandomValues(new Uint8Array(32))].map(x => x.toString(16).padStart(2, "0")).join(""), body: content };
    }
    try {
      const result = await request<{ public_session_id: string }>("/api/sessions", {
        method: "POST", headers: { "X-Submission-Token": attempt.current.token },
        body: JSON.stringify({ submission_id: attempt.current.id, ...JSON.parse(content) }),
      });
      if (result) {
        const chosen = fixtures.filter(f => selected.includes(f.id));
        try { if (chosen.length === 1) sessionStorage.setItem(`cpfc-city-${result.public_session_id}`, chosen[0].city); } catch { /* ignore */ }
        router.push(`/plan/?session=${result.public_session_id}`);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Please retry."); }
    finally { setBusy(false); }
  }

  return <form ref={formRef} className="brief panel" onSubmit={submit}>
    {sample && <div className="notice">Development preview · Synthetic trips and prices · No email is sent</div>}
    <div className="section-heading"><span className="eyebrow">PLAN YOUR AWAY DAY</span><span className="tag">From London</span></div>
    <nav aria-label="Trip brief progress"><ol className="form-progress">{stepNames.map((name, index) => <li key={name} aria-current={step === index ? "step" : undefined} className={index < step ? "complete" : ""}><span className="step-number">{index < step ? "✓" : index + 1}</span><span>{name}</span></li>)}</ol></nav>
    {error && <p className="error" role="alert">{error}</p>}
    <fieldset disabled={busy} className="form-pages">
      <section className="form-page" data-form-step="0" hidden={step !== 0} aria-labelledby={step === 0 ? "form-step-heading" : undefined}>
        <h2 id={step === 0 ? "form-step-heading" : undefined} ref={step === 0 ? headingRef : undefined} tabIndex={-1}>Which match are you going to?</h2>
        <p className="form-help">Choose an away match. We’ll plan a separate London trip for each one.</p>
        {!sample && <p className="fine">The live planner currently supports Lyon for adults sharing one room.</p>}
        <fieldset><legend>Choose your away matches</legend><div className="fixtures">{fixtures.map(f => <label key={f.id} className={`fixture ${selected.includes(f.id) ? "selected" : ""}`}><input type="checkbox" checked={selected.includes(f.id)} onChange={e => setSelected(e.target.checked ? [...selected, f.id] : selected.filter(id => id !== f.id))} /><span><strong>{f.opponent}</strong><small>{f.city} · {new Date(f.kickoff_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "Europe/London" })}</small></span><span aria-hidden="true">↗</span></label>)}</div></fieldset>
        <label>Time around the match<select name="flexibility" defaultValue="day_either_side"><option value="day_either_side">A day either side</option><option value="two_days">Up to two days either side</option><option value="tight">A short trip</option></select></label>
        <details><summary>Choose specific travel dates instead</summary><p className="fine">Enter both dates for a match. Otherwise, we’ll use the time you chose above. Dates use London time.</p>{fixtures.filter(f => selected.includes(f.id)).map(f => <fieldset key={f.id} className="date-group"><legend>{f.opponent}</legend><div className="grid-two"><label>Earliest departure<input type="date" name={`start-${f.id}`} /></label><label>Latest return<input type="date" name={`end-${f.id}`} /></label></div></fieldset>)}</details>
        <div className="form-actions"><button type="button" className="primary" onClick={nextStep}>Continue to travel preferences →</button></div>
      </section>

      <section className="form-page" data-form-step="1" hidden={step !== 1} aria-labelledby={step === 1 ? "form-step-heading" : undefined}>
        <h2 id={step === 1 ? "form-step-heading" : undefined} ref={step === 1 ? headingRef : undefined} tabIndex={-1}>How do you like to travel?</h2>
        <p className="form-help">These choices help us compare routes and places to stay.</p>
        <div className="grid-two"><label>Adults<input type="number" min="1" max="8" value={adults} onChange={e => setAdults(Number(e.target.value))} required={step === 1} /></label><label>Rooms<input name="rooms" type="number" min="1" max={sample ? 4 : 1} defaultValue="1" required={step === 1} /></label></div>
        {sample && <label>Children<select value={children.length} onChange={e => setChildren(Array.from({ length: Number(e.target.value) }, (_, i) => children[i] ?? 8))}>{Array.from({ length: 7 }, (_, i) => <option key={i} value={i}>{i}</option>)}</select></label>}
        {!!children.length && <div className="grid-two">{children.map((age, i) => <label key={i}>Child {i + 1} age<input type="number" min="0" max="17" value={age} onChange={e => setChildren(children.map((a, n) => n === i ? Number(e.target.value) : a))} required={step === 1} /></label>)}</div>}
        <label>Travel by<select name="transport" defaultValue=""><option value="">Compare flights and trains</option><option value="flight">Flights</option><option value="rail">Trains</option></select></label>
        <fieldset className="budget"><legend>Your travel style</legend>{([ ["budget", "£", "Keep it cheap", "Dorms and shared bathrooms can be included"], ["value", "££", "Best value", "Balance price, comfort and journey time"], ["comfort", "£££", "Comfort first", "Fewer changes and more comfortable stays"] ] as const).map(([value, price, title, help]) => <label key={value} className={budget === value ? "selected" : ""}><input type="radio" name="budget" value={value} checked={budget === value} onChange={() => setBudget(value)} /><b>{price}</b><span>{title}<small>{help}</small></span></label>)}</fieldset>
        <p className="fine">Travel style changes which options we recommend. It doesn’t guarantee the lowest price.</p>
        <div className="grid-two preference-checks"><label><input type="checkbox" name="private_room" /> Private room required</label><label><input type="checkbox" name="private_bathroom" /> Private bathroom required</label></div>
        <div className="form-actions"><button type="button" className="text-button" onClick={() => moveTo(0)}>← Back</button><button type="button" className="primary" onClick={nextStep}>Continue to your details →</button></div>
      </section>

      <section className="form-page" data-form-step="2" hidden={step !== 2} aria-labelledby={step === 2 ? "form-step-heading" : undefined}>
        <h2 id={step === 2 ? "form-step-heading" : undefined} ref={step === 2 ? headingRef : undefined} tabIndex={-1}>Where should we send your plan?</h2>
        <p className="form-help">We’ll show your trip here first. You can change it before taking it with you.</p>
        <label>Email address<input name="email" type="email" autoComplete="email" required={step === 2} placeholder="you@example.com" /></label>
        <p className="fine">We’ll use this address to send this itinerary once. No account and no marketing. <Link href="/privacy/">How we use your data</Link>.</p>
        <label>Anything else? <span className="muted">Optional</span><textarea name="instructions" maxLength={2000} rows={3} placeholder="Gatwick preferred, step-free stations, no shared rooms…" /></label>
        <div className="form-review"><strong>Before you start</strong><p>We’ll search from Heathrow, Gatwick, Stansted, Luton or supported St Pancras routes. Your journey to the London departure point and match tickets are outside this plan.</p></div>
        <div className="form-actions"><button type="button" className="text-button" onClick={() => moveTo(1)}>← Back</button><button className="primary" disabled={!selected.length || busy}>{busy ? "Starting your session…" : "Plan my away days →"}</button></div>
      </section>
    </fieldset>
  </form>;
}
