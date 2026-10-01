"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Brief, Fixture, request, londonDayBoundary } from "../lib/api";

export function PlannerForm() {
  const router = useRouter();
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [budget, setBudget] = useState<Brief["budget_tier"]>("value");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sample, setSample] = useState(false);
  const attempt = useRef<{ id: string; token: string; body: string } | null>(null);
  useEffect(() => { let cancelled = false;
    request<{ fixtures: Fixture[]; development_mode: boolean }>("/api/catalog").then(data => {
      if (cancelled || !data) return;
      const upcoming = data.fixtures.filter(f => new Date(f.kickoff_at) > new Date());
      setFixtures(upcoming); setSelected(upcoming.slice(0, 1).map(f => f.id)); setSample(data.development_mode);
    }).catch(() => { if (!cancelled) setError("The planner is unavailable. Please reload to try again."); });
    return () => { cancelled = true; };
  }, []);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    if (selected.some(id => Boolean(form.get(`start-${id}`)) !== Boolean(form.get(`end-${id}`)))) {
      setError("Enter both travel dates, or leave both blank for flexible dates."); setBusy(false); return;
    }
    const brief: Brief = { fixture_ids: selected, travellers: { adults, child_ages: children, rooms: Number(form.get("rooms")) },
      budget_tier: budget, flexibility: form.get("flexibility") as Brief["flexibility"], windows: selected.flatMap(id => {
        const start = String(form.get(`start-${id}`) ?? ""); const end = String(form.get(`end-${id}`) ?? "");
        return start && end ? [{ fixture_id: id, earliest_departure: londonDayBoundary(start), latest_return: londonDayBoundary(end, true) }] : [];
      }), private_room: form.get("private_room") === "on", private_bathroom: form.get("private_bathroom") === "on",
      transport_mode: (form.get("transport") || null) as Brief["transport_mode"], extra_instructions: String(form.get("instructions") ?? "") };
    const content = JSON.stringify({ email: form.get("email"), brief });
    if (!attempt.current || attempt.current.body !== content) attempt.current = { id: crypto.randomUUID(), token: [...crypto.getRandomValues(new Uint8Array(32))].map(x => x.toString(16).padStart(2, "0")).join(""), body: content };
    try {
      const result = await request<{ public_session_id: string }>("/api/sessions", { method: "POST", headers: { "X-Submission-Token": attempt.current.token }, body: JSON.stringify({ submission_id: attempt.current.id, ...JSON.parse(content) }) });
      if (result) router.push(`/plan/?session=${result.public_session_id}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Please retry."); }
    finally { setBusy(false); }
  }
  return <form className="brief panel" onSubmit={submit}>
    {sample && <div className="notice">Development preview · Synthetic trips and prices · No email is sent</div>}
    <div className="section-heading"><span className="eyebrow">YOUR TRIP BRIEF</span><span className="tag">From London</span></div>
    <h2>Where are we going?</h2>{!sample && <p className="fine">Live Lyon preview · Adults sharing one room. Other fixtures and group shapes are coming later.</p>}
    <fieldset disabled={busy}><legend>Choose your away matches</legend><div className="fixtures">{fixtures.map(f => <label key={f.id} className={`fixture ${selected.includes(f.id) ? "selected" : ""}`}><input type="checkbox" checked={selected.includes(f.id)} onChange={e => setSelected(e.target.checked ? [...selected, f.id] : selected.filter(id => id !== f.id))} /><span><strong>{f.opponent}</strong><small>{f.city} · {new Date(f.kickoff_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "Europe/London" })}</small></span><span aria-hidden="true">↗</span></label>)}</div>
    <div className="grid-two"><label>Adults<input type="number" min="1" max="8" value={adults} onChange={e => setAdults(Number(e.target.value))} required /></label><label>Rooms<input name="rooms" type="number" min="1" max={sample ? 4 : 1} defaultValue="1" required /></label></div>
    <label>Children<select disabled={!sample} value={children.length} onChange={e => setChildren(Array.from({ length: Number(e.target.value) }, (_, i) => children[i] ?? 8))}>{Array.from({ length: 7 }, (_, i) => <option key={i} value={i}>{i}</option>)}</select></label>
    {!!children.length && <div className="grid-two">{children.map((age, i) => <label key={i}>Child {i + 1} age<input type="number" min="0" max="17" value={age} onChange={e => setChildren(children.map((a, n) => n === i ? Number(e.target.value) : a))} /></label>)}</div>}
    <label>Time around the match<select name="flexibility" defaultValue="day_either_side"><option value="day_either_side">A day either side</option><option value="two_days">Up to two days either side</option><option value="tight">A short trip</option></select></label>
    <details><summary>Set travel dates</summary><p className="fine">Dates are measured in London time. Enter both dates for each match; otherwise we use your flexibility setting.</p>{fixtures.filter(f => selected.includes(f.id)).map(f => <fieldset key={f.id}><legend>{f.opponent}</legend><div className="grid-two"><label>Earliest departure<input type="date" name={`start-${f.id}`} /></label><label>Latest return<input type="date" name={`end-${f.id}`} /></label></div></fieldset>)}</details>
    <label>Travel by<select name="transport" defaultValue=""><option value="">Compare flights and trains</option><option value="flight">Flights</option><option value="rail">Trains</option></select></label>
    <label><input type="checkbox" name="private_room" /> Private room required</label>
    <label><input type="checkbox" name="private_bathroom" /> Private bathroom required</label>
    <fieldset className="budget"><legend>Your travel style</legend>{([ ["budget", "£", "Keep it cheap", "Dorms and shared bathrooms can be included"], ["value", "££", "Best value", "Balance price, comfort and journey time"], ["comfort", "£££", "Comfort first", "Fewer changes and more comfortable stays"] ] as const).map(([value, price, title, help]) => <label key={value} className={budget === value ? "selected" : ""}><input type="radio" name="budget" value={value} checked={budget === value} onChange={() => setBudget(value)} /><b>{price}</b><span>{title}<small>{help}</small></span></label>)}</fieldset>
    <label>Email your itinerary<input name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></label><p className="fine">We’ll use this address to send this itinerary once. No account and no marketing.</p>
    <label>Anything else? <span className="muted">Optional</span><textarea name="instructions" maxLength={2000} rows={3} placeholder="Gatwick preferred, no shared rooms…" /></label>
    <p className="fine">Choose from Heathrow, Gatwick, Stansted, Luton and supported St Pancras routes. Travel to your London hub is outside the plan.</p>
    {error && <p className="error" role="alert">{error}</p>}
    <button className="primary" disabled={busy || !selected.length}>{busy ? "Starting your session…" : "Plan my away days →"}</button></fieldset>
  </form>;
}
