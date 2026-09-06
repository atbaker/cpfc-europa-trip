"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import { ItineraryView } from "@/components/itinerary-view";
import { API_BASE_URL, EMAIL_PREVIEW_ENABLED } from "@/lib/config";
import type { SessionSnapshot, StreamEvent } from "@/lib/types";

type ProvisionalText = Record<string, { attempt: number; text: string }>;

export function PlanExperience() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session");
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [provisional, setProvisional] = useState<ProvisionalText>({});
  const [streamConnected, setStreamConnected] = useState(false);
  const [pendingTurn, setPendingTurn] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const fetchSnapshot = useCallback(async () => {
    if (!sessionId) return;
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(
        response.status === 401 || response.status === 403
          ? "This planning link is not authorised in this browser."
          : "Your planning session is temporarily unavailable.",
      );
    }
    const next = (await response.json()) as SessionSnapshot;
    setSnapshot((current) =>
      current && current.state_revision > next.state_revision ? current : next,
    );
    if (
      pendingTurn &&
      next.messages.some((entry) => entry.id === `assistant-${pendingTurn}`)
    ) {
      setPendingTurn(null);
    }
  }, [pendingTurn, sessionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchSnapshot().catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "Unable to open the session."),
      );
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchSnapshot]);

  useEffect(() => {
    if (!sessionId) return;
    const source = new EventSource(`${API_BASE_URL}/api/sessions/${sessionId}/events`, {
      withCredentials: true,
    });
    source.onopen = () => setStreamConnected(true);
    source.onmessage = (raw) => {
      const event = JSON.parse(raw.data) as StreamEvent;
      if (event.type === "status" && event.message) {
        setSnapshot((current) => (current ? { ...current, progress: event.message ?? current.progress } : current));
      }
      if (event.type === "text_delta" && event.turn_id && event.text && event.attempt) {
        setProvisional((current) => {
          const existing = current[event.turn_id!];
          if (existing && existing.attempt > event.attempt!) return current;
          const text = !existing || existing.attempt < event.attempt! ? event.text! : existing.text + event.text;
          return { ...current, [event.turn_id!]: { attempt: event.attempt!, text } };
        });
      }
      if (event.type === "retry" && event.turn_id && event.attempt) {
        setProvisional((current) => ({
          ...current,
          [event.turn_id!]: { attempt: event.attempt!, text: "" },
        }));
      }
      if (event.type === "turn_committed") {
        setProvisional((current) => {
          if (!event.turn_id) return current;
          const next = { ...current };
          delete next[event.turn_id];
          return next;
        });
        void fetchSnapshot();
      }
      if (event.type === "session_closed") void fetchSnapshot();
    };
    source.onerror = () => setStreamConnected(false);
    return () => source.close();
  }, [fetchSnapshot, sessionId]);

  useEffect(() => {
    if (!sessionId || (streamConnected && !pendingTurn)) return;
    const timer = window.setInterval(() => void fetchSnapshot(), 2_000);
    return () => window.clearInterval(timer);
  }, [fetchSnapshot, pendingTurn, sessionId, streamConnected]);

  const provisionalBody = useMemo(
    () => Object.values(provisional).map((entry) => entry.text).join(""),
    [provisional],
  );

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionId || !message.trim() || pendingTurn) return;
    const commandId = crypto.randomUUID();
    setPendingTurn(commandId);
    setError(null);
    const body = message.trim();
    setMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_id: commandId, body }),
      });
      if (!response.ok) throw new Error("That change was not accepted. Please try again.");
      await fetchSnapshot();
    } catch (caught) {
      setPendingTurn(null);
      setMessage(body);
      setError(caught instanceof Error ? caught.message : "Unable to send that message.");
    }
  }

  async function finalize() {
    if (!sessionId || sending) return;
    setSending(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/finalize`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_id: crypto.randomUUID() }),
      });
      if (!response.ok) throw new Error("We couldn't prepare your email yet.");
      await fetchSnapshot();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to finalize this itinerary.");
      setSending(false);
    }
  }

  if (!sessionId) {
    return (
      <section className="empty-state">
        <h1>No planning session found</h1>
        <p>Start with the away-day form and we&apos;ll build your itinerary.</p>
        <Link className="primary-button" href="/">
          Plan an away day
        </Link>
      </section>
    );
  }

  if (error && !snapshot) {
    return (
      <section className="empty-state">
        <p className="eyebrow">Session unavailable</p>
        <h1>We couldn&apos;t open this itinerary.</h1>
        <p>{error}</p>
        <Link className="primary-button" href="/">
          Start a new plan
        </Link>
      </section>
    );
  }

  const closed = snapshot?.phase === "emailed" || snapshot?.phase === "email_failed";
  const canChat = snapshot?.phase === "draft_ready" && !pendingTurn && !sending;

  return (
    <div className="plan-shell">
      <div className="session-status" aria-live="polite">
        <span className={`pulse ${streamConnected ? "connected" : ""}`} />
        <span>{snapshot?.progress ?? "Opening your planning session…"}</span>
        <small>{streamConnected ? "Live" : "Reconnecting"}</small>
      </div>

      {!snapshot?.itinerary && (
        <section className="working-card">
          <div className="route-animation" aria-hidden="true">
            <span>SE25</span>
            <i />
            <span>EUROPE</span>
          </div>
          <h1>Finding the route worth knowing about.</h1>
          <p>
            We&apos;re checking the whole trip—not just the first tempting fare. You can leave;
            the latest valid itinerary will still be emailed after ten minutes of inactivity.
          </p>
          <div className="skeleton skeleton-card" />
        </section>
      )}

      {provisionalBody && (
        <div className="assistant-bubble streaming" aria-live="polite">
          <span className="assistant-avatar">CP</span>
          <p>{provisionalBody}</p>
        </div>
      )}

      {snapshot?.itinerary && <ItineraryView itinerary={snapshot.itinerary} />}

      {snapshot?.itinerary && (
        <section className="conversation" aria-labelledby="conversation-title">
          <div className="conversation-heading">
            <div>
              <p className="eyebrow">Make it yours</p>
              <h2 id="conversation-title">Ask for a change</h2>
            </div>
            <span>One request at a time</span>
          </div>
          <div className="message-list">
            {snapshot.messages.slice(1).map((entry) => (
              <div className={`message ${entry.role}`} key={entry.id}>
                {entry.body}
              </div>
            ))}
            {pendingTurn && !provisionalBody && (
              <div className="message assistant typing">Reworking the relevant pieces…</div>
            )}
          </div>
          {!closed && (
            <form className="composer" onSubmit={sendMessage}>
              <label className="sr-only" htmlFor="follow-up-message">
                Ask a question or request a change
              </label>
              <textarea
                id="follow-up-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Make it cheaper, avoid self-transfers, or get me home by 18:00…"
                rows={2}
                maxLength={2000}
                disabled={!canChat}
              />
              <button type="submit" disabled={!canChat || !message.trim()} aria-label="Send message">
                ↑
              </button>
            </form>
          )}
        </section>
      )}

      {error && snapshot && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {snapshot?.itinerary && (
        <div className="finalize-bar">
          <div>
            <strong>
              {snapshot.email_status === "sent" ? "Itinerary sent" : "Happy with this route?"}
            </strong>
            <span>
              {snapshot.email_status === "sent"
                ? "A copy is ready in your inbox."
                : "We'll send the latest complete revision once."}
            </span>
          </div>
          {snapshot.email_status === "sent" && EMAIL_PREVIEW_ENABLED ? (
            <a
              className="secondary-button"
              href={`${API_BASE_URL}/api/sessions/${sessionId}/email-preview/render`}
              target="_blank"
            >
              Preview email
            </a>
          ) : snapshot.email_status !== "sent" ? (
            <button
              className="primary-button"
              type="button"
              onClick={finalize}
              disabled={sending || snapshot.phase === "finalizing"}
            >
              {sending || snapshot.phase === "finalizing" ? "Preparing email…" : "Send me my itinerary"}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
