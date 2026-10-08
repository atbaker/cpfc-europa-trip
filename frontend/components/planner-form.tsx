"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Brief, Fixture, londonDayBoundary, request } from "../lib/api";

const stepNames = ["Match & dates", "Travel preferences", "Your details"] as const;

export function PlannerForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const attempt = useRef<{ id: string; token: string; body: string } | null>(null);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [originCities, setOriginCities] = useState<string[]>(["London"]);
  const [railCities, setRailCities] = useState<string[]>(["London"]);
  const [origin, setOrigin] = useState("London");
  const [transport, setTransport] = useState<Brief["transport_mode"]>(null);
  const [selected, setSelected] = useState("");
  const [step, setStep] = useState(0);
  const [hasNavigated, setHasNavigated] = useState(false);
  const [budget, setBudget] = useState<Brief["budget_tier"]>("value");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sample, setSample] = useState(false);

  useEffect(() => {
    let cancelled = false;
    request<{ fixtures: Fixture[]; origin_cities: string[]; rail_cities: string[]; development_mode: boolean }>("/api/catalog")
      .then(data => {
        if (cancelled || !data) return;
        const upcoming = data.fixtures.filter(f => new Date(f.kickoff_at) > new Date());
        setFixtures(upcoming);
        setOriginCities(data.origin_cities ?? ["London"]);
        setRailCities(data.rail_cities ?? ["London"]);
        setSelected(upcoming[0]?.id ?? "");
        setSample(data.development_mode);
      })
      .catch(() => { if (!cancelled) setError("The planner is unavailable. Please reload to try again."); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (hasNavigated) headingRef.current?.focus();
  }, [step, hasNavigated]);

  function moveTo(next: number) {
    setHasNavigated(true);
    setError("");
    setStep(next);
  }

  function nextStep() {
    if (step === 0 && !originCities.some(city => city.toLowerCase() === origin.trim().toLowerCase())) {
      setError("Choose a UK departure city from the suggestions.");
      return;
    }
    if (step === 0 && !selected) {
      setError("Choose an away match to continue.");
      return;
    }
    const page = formRef.current?.querySelector<HTMLElement>(`[data-form-step="${step}"]`);
    const invalid = Array.from(page?.querySelectorAll<HTMLInputElement | HTMLSelectElement>("input, select") ?? [])
      .find(field => !field.checkValidity());
    if (invalid) { invalid.reportValidity(); return; }
    if (step === 0 && selected && (() => {
      const start = formRef.current?.elements.namedItem(`start-${selected}`) as HTMLInputElement | null;
      const end = formRef.current?.elements.namedItem(`end-${selected}`) as HTMLInputElement | null;
      return Boolean(start?.value) !== Boolean(end?.value) || Boolean(start?.value && end?.value && start.value > end.value);
    })()) {
      setError("Enter a departure and return date in order, or leave both blank.");
      return;
    }
    moveTo(step + 1);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (step !== 2 || !selected) return;
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const brief: Brief = {
      fixture_ids: [selected],
      origin_city: originCities.find(city => city.toLowerCase() === origin.trim().toLowerCase()) ?? origin,
      travellers: { adults, child_ages: children, rooms: Number(form.get("rooms")) },
      budget_tier: budget,
      flexibility: form.get("flexibility") as Brief["flexibility"],
      windows: (() => {
        const start = String(form.get(`start-${selected}`) ?? "");
        const end = String(form.get(`end-${selected}`) ?? "");
        return start && end ? [{ fixture_id: selected, earliest_departure: londonDayBoundary(start), latest_return: londonDayBoundary(end, true) }] : [];
      })(),
      private_room: form.get("private_room") === "on",
      private_bathroom: form.get("private_bathroom") === "on",
      transport_mode: transport,
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
        const chosen = fixtures.find(f => f.id === selected);
        try { if (chosen) sessionStorage.setItem(`cpfc-city-${result.public_session_id}`, chosen.city); } catch { /* ignore */ }
        router.push(`/plan/?session=${result.public_session_id}`);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Please retry."); }
    finally { setBusy(false); }
  }

  const railAvailable = railCities.includes(origin) && fixtures.find(f => f.id === selected)?.city === "Lyon";
  return <form ref={formRef} className="brief panel" onSubmit={submit}>
    {sample && <div className="notice">Development preview · Synthetic trips and prices · No email is sent</div>}
    <div className="section-heading"><span className="eyebrow">PLAN YOUR AWAY DAY</span><span className="tag">From {origin || "your city"}</span></div>
    <nav aria-label="Trip brief progress"><ol className="form-progress">{stepNames.map((name, index) => <li key={name} aria-current={step === index ? "step" : undefined} className={index < step ? "complete" : ""}><span className="step-number">{index < step ? "✓" : index + 1}</span><span>{name}</span></li>)}</ol></nav>
    {error && <p className="error" role="alert">{error}</p>}
    <fieldset disabled={busy} className={hasNavigated ? "form-pages transitioning" : "form-pages"}>
      <section className="form-page" data-form-step="0" hidden={step !== 0} aria-labelledby={step === 0 ? "form-step-heading" : undefined}>
        <h2 id={step === 0 ? "form-step-heading" : undefined} ref={step === 0 ? headingRef : undefined} tabIndex={-1}>Which match are you going to?</h2>
        <p className="form-help">Choose where you’ll start and the away match you’re going to.</p>
        {!sample && <p className="fine">Live planning covers these four away matches for adults sharing one room. Routes depend on dated travel results.</p>}
        <label>Starting from<span className="select-wrap"><select name="origin_city" value={origin} onChange={event => { setOrigin(event.target.value); setTransport(railCities.includes(event.target.value) ? null : "flight"); }} required={step === 0}>{originCities.map(city => <option key={city} value={city}>{city}</option>)}</select><span className="select-chevron" aria-hidden="true">⌄</span></span></label>
        <p className="fine">Choose a UK city. We’ll search its supported airport and any available train route.</p>
        <fieldset><legend>Choose your away match</legend><div className="fixtures">{fixtures.map(f => <label key={f.id} className={`fixture ${selected === f.id ? "selected" : ""}`}><input type="radio" name="fixture" value={f.id} checked={selected === f.id} onChange={() => { setSelected(f.id); setTransport(railCities.includes(origin) && f.city === "Lyon" ? null : "flight"); }} /><span><strong>{f.opponent}</strong><small>{new Date(f.kickoff_at).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "Europe/London" })} · {f.venue}, {f.venue_location || f.city}</small><small>UEFA Europa League</small></span></label>)}</div></fieldset>
        <label>Time around the match<span className="select-wrap"><select name="flexibility" defaultValue="day_either_side"><option value="day_either_side">A day either side</option><option value="two_days">Up to two days either side</option><option value="tight">A short trip</option></select><span className="select-chevron" aria-hidden="true">⌄</span></span></label>
        <details><summary>Choose specific travel dates instead</summary><p className="fine">Enter both dates for the match. Otherwise, we’ll use the time you chose above. Dates use London time.</p>{fixtures.filter(f => f.id === selected).map(f => <fieldset key={f.id} className="date-group"><legend>{f.opponent}</legend><div className="grid-two"><label>Earliest departure<input type="date" name={`start-${f.id}`} /></label><label>Latest return<input type="date" name={`end-${f.id}`} /></label></div></fieldset>)}</details>
        <div className="form-actions"><button type="button" className="primary" onClick={nextStep}>Continue to travel preferences <span className="arrow">→</span></button></div>
      </section>

      <section className="form-page" data-form-step="1" hidden={step !== 1} aria-labelledby={step === 1 ? "form-step-heading" : undefined}>
        <h2 id={step === 1 ? "form-step-heading" : undefined} ref={step === 1 ? headingRef : undefined} tabIndex={-1}>How do you like to travel?</h2>
        <p className="form-help">These choices help us compare routes and places to stay.</p>
        <div className="grid-two"><label>Adults<input type="number" min="1" max="8" value={adults} onChange={e => setAdults(Number(e.target.value))} required={step === 1} /></label><label>Rooms<input name="rooms" type="number" min="1" max={sample ? 4 : 1} defaultValue="1" required={step === 1} /></label></div>
        {sample && <label>Children<span className="select-wrap"><select value={children.length} onChange={e => setChildren(Array.from({ length: Number(e.target.value) }, (_, i) => children[i] ?? 8))}>{Array.from({ length: 7 }, (_, i) => <option key={i} value={i}>{i}</option>)}</select><span className="select-chevron" aria-hidden="true">⌄</span></span></label>}
        {!!children.length && <div className="grid-two">{children.map((age, i) => <label key={i}>Child {i + 1} age<input type="number" min="0" max="17" value={age} onChange={e => setChildren(children.map((a, n) => n === i ? Number(e.target.value) : a))} required={step === 1} /></label>)}</div>}
        <label>Travel by<span className="select-wrap"><select name="transport" value={transport ?? ""} onChange={event => setTransport((event.target.value || null) as Brief["transport_mode"])}><option value="">{railAvailable ? "Compare flights and trains" : "Flights"}</option><option value="flight">Flights</option>{railAvailable && <option value="rail">Trains</option>}</select><span className="select-chevron" aria-hidden="true">⌄</span></span></label>
        <fieldset className="budget"><legend>Your travel style</legend>{([ ["budget", "£", "Keep it cheap", "Dorms and shared bathrooms can be included"], ["value", "££", "Best value", "Balance price, comfort and journey time"], ["comfort", "£££", "Comfort first", "Fewer changes and more comfortable stays"] ] as const).map(([value, price, title, help]) => <label key={value} className={budget === value ? "selected" : ""}><input type="radio" name="budget" value={value} checked={budget === value} onChange={() => setBudget(value)} /><b>{price}</b><span>{title}<small>{help}</small></span></label>)}</fieldset>
        <p className="fine">Travel style changes which options we recommend. It doesn’t guarantee the lowest price.</p>
        <div className="grid-two preference-checks"><label><input type="checkbox" name="private_room" /> Private room required</label><label><input type="checkbox" name="private_bathroom" /> Private bathroom required</label></div>
        <div className="form-actions"><button type="button" className="text-button" onClick={() => moveTo(0)}><span className="arrow">←</span> Back</button><button type="button" className="primary" onClick={nextStep}>Continue to your details <span className="arrow">→</span></button></div>
      </section>

      <section className="form-page" data-form-step="2" hidden={step !== 2} aria-labelledby={step === 2 ? "form-step-heading" : undefined}>
        <h2 id={step === 2 ? "form-step-heading" : undefined} ref={step === 2 ? headingRef : undefined} tabIndex={-1}>Where should we send your plan?</h2>
        <p className="form-help">We’ll show your trip here first. You can change it before taking it with you.</p>
        <label>Email address<input name="email" type="email" autoComplete="email" required={step === 2} placeholder="you@example.com" /></label>
        <p className="fine">We’ll use this address to send this itinerary once. No account and no marketing. <Link href="/privacy/">How we use your data</Link>.</p>
        <label>Anything else? <span className="muted">Optional</span><textarea name="instructions" maxLength={2000} rows={3} placeholder="Gatwick preferred, step-free stations, no shared rooms…" /></label>
        <div className="form-review"><strong>Before you start</strong><p>{origin === "London" ? railAvailable ? "We’ll search flights from Heathrow, Gatwick, Stansted or Luton, plus supported St Pancras routes." : "We’ll search flights from Heathrow, Gatwick, Stansted or Luton." : railAvailable ? `We’ll search flights from ${origin} and dated trains through London and Paris. Allow time to change stations in both cities.` : `We’ll search flights from the supported airport near ${origin}.`} We check nonstop flights first, then suitable one-stop flights if needed.{fixtures.find(f => f.id === selected)?.city === "Białystok" ? " For Białystok, we’ll check a train from Warsaw and leave time for the airport transfer. Train fares may be unavailable." : ""} Routes and prices depend on what the provider can verify. Your journey to the departure point and match tickets are outside this plan.</p></div>
        <div className="form-actions"><button type="button" className="text-button" onClick={() => moveTo(1)}><span className="arrow">←</span> Back</button><button className="primary" disabled={!selected || busy}>{busy ? "Starting your session…" : <>Plan my away day <span className="arrow">→</span></>}</button></div>
      </section>
    </fieldset>
  </form>;
}
