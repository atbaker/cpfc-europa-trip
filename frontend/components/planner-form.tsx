"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { API_BASE_URL } from "@/lib/config";
import { FIXTURES } from "@/lib/fixtures";
import type { BudgetTier } from "@/lib/types";

const BUDGETS: readonly {
  id: BudgetTier;
  symbol: string;
  title: string;
  detail: string;
}[] = [
  {
    id: "budget",
    symbol: "£",
    title: "Keep it cheap",
    detail: "Hostels and simple stays; indirect or overnight routes are fair game.",
  },
  {
    id: "value",
    symbol: "££",
    title: "Best value",
    detail: "Mid-range or boutique stays; balance price, time, and changes.",
  },
  {
    id: "comfort",
    symbol: "£££",
    title: "Comfort first",
    detail: "Four/five-star stays; favour direct routes and convenient times.",
  },
] as const;

export function PlannerForm() {
  const router = useRouter();
  const [selected, setSelected] = useState<string[]>([FIXTURES[0].id]);
  const [origin, setOrigin] = useState("London");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [childAges, setChildAges] = useState<number[]>([]);
  const [rooms, setRooms] = useState(1);
  const [flexibility, setFlexibility] = useState(1);
  const [budget, setBudget] = useState<BudgetTier>("value");
  const [email, setEmail] = useState("");
  const [instructions, setInstructions] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedLabel = useMemo(
    () => `${selected.length} fixture${selected.length === 1 ? "" : "s"} selected`,
    [selected.length],
  );

  function toggleFixture(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((fixtureId) => fixtureId !== id) : [...current, id],
    );
  }

  function updateChildren(next: number) {
    const count = Math.max(0, Math.min(6, next));
    setChildren(count);
    setChildAges((current) =>
      count > current.length
        ? [...current, ...Array.from({ length: count - current.length }, () => 8)]
        : current.slice(0, count),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selected.length === 0) {
      setError("Choose at least one away fixture.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: crypto.randomUUID(),
          email,
          fixture_ids: selected,
          origin,
          adults,
          child_ages: childAges,
          rooms,
          flexibility_days: flexibility,
          budget_tier: budget,
          extra_instructions: instructions || null,
        }),
      });
      if (!response.ok) {
        const problem = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(problem?.detail ?? "We couldn't start your plan. Please try again.");
      }
      const result = (await response.json()) as { public_id: string };
      router.push(`/plan/?session=${encodeURIComponent(result.public_id)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <form className="planner-card" onSubmit={submit}>
      <div className="form-heading">
        <span className="step-number">01</span>
        <div>
          <p className="eyebrow">Build your trip brief</p>
          <h2>Which away days are calling?</h2>
        </div>
      </div>

      <fieldset className="form-section fixture-fieldset">
        <legend>
          Away fixtures <span>{selectedLabel}</span>
        </legend>
        <div className="fixture-grid">
          {FIXTURES.map((fixture) => {
            const active = selected.includes(fixture.id);
            return (
              <label className={`fixture-option ${active ? "selected" : ""}`} key={fixture.id}>
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggleFixture(fixture.id)}
                />
                <span className="check-mark" aria-hidden="true">
                  {active ? "✓" : ""}
                </span>
                <strong>{fixture.opponent}</strong>
                <span>{fixture.destination}</span>
                <small>
                  {fixture.date} · {fixture.kickoff}
                </small>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="field-grid">
        <label className="field">
          <span>Starting from</span>
          <input
            required
            value={origin}
            onChange={(event) => setOrigin(event.target.value)}
            placeholder="Town, city, airport or station"
            autoComplete="address-level2"
          />
        </label>
        <label className="field">
          <span>Travel flexibility</span>
          <select value={flexibility} onChange={(event) => setFlexibility(Number(event.target.value))}>
            <option value={0}>Exact dates</option>
            <option value={1}>A day either side</option>
            <option value={2}>Two days either side</option>
            <option value={3}>Three days either side</option>
          </select>
        </label>
      </div>

      <div className="traveller-panel">
        <span className="field-label">Who&apos;s travelling?</span>
        <Counter label="Adults" value={adults} min={1} max={8} setValue={setAdults} />
        <Counter label="Children" value={children} min={0} max={6} setValue={updateChildren} />
        {children > 0 && (
          <div className="age-grid">
            {childAges.map((age, index) => (
              <label key={index}>
                Child {index + 1} age
                <select
                  value={age}
                  onChange={(event) =>
                    setChildAges((current) =>
                      current.map((currentAge, ageIndex) =>
                        ageIndex === index ? Number(event.target.value) : currentAge,
                      ),
                    )
                  }
                >
                  {Array.from({ length: 18 }, (_, childAge) => (
                    <option value={childAge} key={childAge}>
                      {childAge}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        )}
        <details className="room-details">
          <summary>Room preference</summary>
          <Counter label="Rooms" value={rooms} min={1} max={4} setValue={setRooms} />
        </details>
      </div>

      <fieldset className="form-section budget-fieldset">
        <legend>
          Travel style <span>This changes how we search and rank—not a price guarantee.</span>
        </legend>
        <div className="budget-grid">
          {BUDGETS.map((option) => (
            <label className={`budget-option ${budget === option.id ? "selected" : ""}`} key={option.id}>
              <input
                type="radio"
                name="budget"
                value={option.id}
                checked={budget === option.id}
                onChange={() => setBudget(option.id)}
              />
              <span className="budget-symbol">{option.symbol}</span>
              <strong>{option.title}</strong>
              <small>{option.detail}</small>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="field email-field">
        <span>Email address</span>
        <input
          required
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          autoComplete="email"
        />
        <small>We&apos;ll use this address to send this itinerary once. No account. No marketing.</small>
      </label>

      <label className="field">
        <span>
          Extra instructions <em>optional</em>
        </span>
        <textarea
          value={instructions}
          onChange={(event) => setInstructions(event.target.value)}
          placeholder="No overnight coaches, step-free stations, must be home Friday by 18:00, or no shared rooms…"
          rows={3}
          maxLength={2000}
        />
      </label>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="primary-button" type="submit" disabled={submitting}>
        {submitting ? "Starting your planner…" : "Plan my away days"}
        <span aria-hidden="true">→</span>
      </button>
      <p className="submit-note">No payment or booking. We&apos;ll link you out when you&apos;re ready.</p>
    </form>
  );
}

function Counter({
  label,
  value,
  min,
  max,
  setValue,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  setValue: (value: number) => void;
}) {
  return (
    <div className="counter">
      <span>{label}</span>
      <div>
        <button type="button" onClick={() => setValue(Math.max(min, value - 1))} disabled={value <= min}>
          <span className="sr-only">Remove one {label.toLowerCase()}</span>−
        </button>
        <output aria-live="polite">{value}</output>
        <button type="button" onClick={() => setValue(Math.min(max, value + 1))} disabled={value >= max}>
          <span className="sr-only">Add one {label.toLowerCase()}</span>+
        </button>
      </div>
    </div>
  );
}
