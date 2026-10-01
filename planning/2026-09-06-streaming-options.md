# Response delivery before the rebuild

Research checked: 6 September 2026 using Exa and primary documentation.
Status: approved and incorporated into the main MVP plan on 6 September 2026. Use direct Temporal Query polling with a minimum of one Cloud Run Worker instance per pool serving active sessions. The transport comparisons below retain the research behind this choice; they are not additional MVP requirements. Removal of concierge operations is also approved and reflected in the main plan.

## Recommendation

For the expected few-minute planning conversations, adopt **direct Temporal Query polling with
progress updates and completed assistant messages** for MVP. FastAPI authorizes each request
and queries the session Workflow; there is no
separate live polling projection to synchronize. Short sessions help limit request volume;
peak concurrent sessions still determine load. This supersedes this note's earlier preference
for PostgreSQL-backed polling, which remains an optional future response to measured read-load
or availability problems.

If live assistant text remains an MVP requirement, use **Redis Streams → FastAPI SSE** as the
next choice. Keep Temporal authoritative for planning, revisions, final messages, and email.
Treat the text stream as a recoverable presentation channel: losing provisional chunks can
interrupt the typing effect, but must not lose the itinerary or rerun a paid model call.

The Redis alternative below is based on the documented design and this project's requirements,
not a performance benchmark. Its tradeoff is less dependence on preview Temporal APIs and
less per-chunk Workflow traffic in exchange for a separate Redis service and application-owned
reconnect, deduplication, and reconciliation logic.

## How polling-only would work

1. **Accept the request.** The browser submits the form or a chat message. FastAPI starts the
   Workflow or sends a short, duplicate-safe Update that queues the turn, then returns an
   acceptance receipt. The HTTP request does not wait for travel research or answer generation.
2. **Show real progress.** The Workflow maintains curated states such as researching routes,
   comparing stays, and checking feasibility. These updates reflect work actually reached;
   they are neither model reasoning nor an invented percentage-complete indicator. While a
   model/tool Activity runs, the Query sees the latest state the Workflow has recorded; it
   does not inspect the Activity's private memory or automatically reveal token-level progress.
3. **Fetch the latest snapshot.** While work is pending, the browser calls the authorized
   `GET /api/sessions/{id}/snapshot?after_revision=N` endpoint every one or two seconds. FastAPI
   invokes the Workflow's read-only `get_snapshot(after_revision=N)` Query and returns the
   latest revision, or `204` if unchanged. Comparing revisions inside the handler can avoid
   serializing an unchanged itinerary, but still requires a Query round trip and worker execution.
   Polling does not start another search or model call.
4. **Display the completed turn.** Once validated, the Workflow commits the full assistant
   message and any itinerary revision together. The next poll replaces the
   progress indicator with the complete answer and atomically updates the cards. During a
   revision, keep the previous valid itinerary visible until its replacement is ready.
5. **Adapt to activity.** Poll quickly during research, revisions, or finalization. While waiting
   for the user, slow to roughly 15–30 seconds so an open page still notices the inactivity email
   and terminal state. Pause in hidden tabs, fetch immediately on return, and stop at terminal
   states. Browser polling must never reset the ten-minute meaningful-interaction timer.
6. **Recover by reading.** A reload or reconnect fetches the current authorized snapshot.
   Temporal work and email continue if the browser leaves. A transient poll failure backs off
   and preserves the last displayed result; it does not resubmit the turn.

For example, a user asks for a cheaper stay. Their message appears immediately, followed by
“Comparing cheaper stays.” When the answer is ready, the complete explanation and updated hotel
card appear together. There is no token-by-token typing in this version.

### What it means for a Worker to process a Query

The request path is browser → FastAPI → Temporal Cloud → compatible Workflow Worker, with the
answer returned along the reverse path. Temporal stores the Workflow's Event History; our
Python `@workflow.query` handler defines how to turn its current application state into the
snapshot. Temporal Cloud does not execute that application handler itself.

The handler is a synchronous, read-only function that returns fields such as phase, progress,
revision, transcript, and the committed itinerary. It must not schedule Activities, make
provider calls, wait for a model response, or mutate state. Queries do not add Event History
entries and do not reset inactivity. They can run while the main Workflow awaits an Activity;
the waiting Workflow does not reserve a worker exclusively for that user.
[Temporal message passing](https://docs.temporal.io/encyclopedia/workflow-message-passing),
[Python Query handlers](https://docs.temporal.io/develop/python/message-passing#query-handlers)

When Workflow state is cached on the receiving Worker, answering can largely be a memory read
plus serialization and network travel. After restart, eviction, or rerouting, the Worker may
need to fetch History and replay Workflow code to reconstruct state first. Replay reuses
recorded Activity results rather than calling SearchApi or the model again. Larger histories
and cold Workers make reads more expensive; do not assume every poll is a cache hit or that a
Query alone always establishes a reusable sticky cache entry.
[Workflow cache and replay](https://docs.temporal.io/workflow-execution),
[Sticky Execution](https://docs.temporal.io/sticky-execution)

If no compatible Worker can answer, the snapshot request can fail or time out even though the
Workflow's history is safely retained. Python documentation explicitly describes a no-pollers
Query error. Preserve the last visible snapshot, show a reconnecting status, and retry with a
bounded RPC deadline and backoff. Do not translate transport failure into an empty itinerary
or restart planning. A worker needs CPU capacity for query handling and replay as well as the
normal Workflow work; keep blocking model/network calls out of Workflow code.
[Python Query availability and errors](https://docs.temporal.io/develop/python/message-passing)

### Implications for our Serverless Workers

Cloud Run Serverless Workers are a pool of ordinary long-lived Worker processes, each capable
of serving many Tasks, rather than a fresh container per browser poll. Temporal's controller
resizes the pool from incoming Task rates, backlog, and sync-match failures within configured
minimum/maximum bounds. The owner expects a minimum of one running instance, so the proposed
MVP does not depend on waking from zero. Active short conversations are a favorable workload
for reusing warm state, but this is an expectation to measure, not a latency guarantee.
[Cloud Run Worker lifecycle and autoscaling](https://docs.temporal.io/serverless-workers/cloud-run)

Verify the one-instance floor and test ordinary polling while model/search Activities are
active, after cache eviction/restart, and through a Worker version rollout. A minimum of one
is a capacity target rather than a guarantee against restarts, so retain bounded query timeouts
and retry/backoff. Because our Workflows are pinned to versions, maintain warm capacity for
each pool still serving active sessions during a rollout. Query-only wake-up from zero would
need separate verification only if we later choose to allow those pools to scale to zero.

Queries to completed Workflows still require worker code and retained History. The SDK supports
closed-workflow Queries within namespace retention, with documented exceptions. Therefore,
stop active polling at completion and account for compatible code availability before deleting
old worker versions. Existing final saved-itinerary persistence can support later revisits;
that is distinct from maintaining a second live polling snapshot.
[Query lifecycle](https://docs.temporal.io/develop/python/message-passing#send-a-query)

### Cost, latency, and implementation limits

- At a two-second interval, three continuous minutes of active polling is about **90 requests
  per browser**. **100 simultaneously polling browsers** produce about **50 requests/second**.
  That also means roughly 50 Temporal Queries/second. These are request-count estimates, not
  measured capacity or hosting-cost claims; no History growth does not mean no compute or API cost.
- Once the Workflow has updated its state, a one-to-two-second interval adds roughly **0.5–1 second of average
  detection delay**, plus network/API latency, assuming completion falls uniformly between polls.
  Query routing, worker startup/replay, and answer-generation time are additional.
- Use one in-flight request per page, schedule the next after completion, add slight jitter,
  and back off on network errors, throttling, or server errors. Poll duration and backoff can
  increase the effective interval; test peak fixture-announcement traffic, namespace limits,
  Query latency, cache misses/replay, and worker capacity.
- Coarse status updates keep long searches understandable, but completed-message delivery feels
  less immediate for long explanations. Polling partial text is possible later, but would add
  frequent writes and failed-attempt replacement logic. Start with complete messages.
- We still need bounded planning/retry deadlines and honest failure/partial-result UI. A progress
  indicator and frequent reads do not fix a stalled backend operation.

The main plan now removes Workflow Streams, SSE, Redis contingency, and the associated
text-delta/offset/retry-buffer schemas and tests. Its Temporal Query snapshot endpoint is the
primary display path; durable turns, atomic cards, and email remain. Verify
reload, duplicate submissions, delayed responses, worker/API restarts, minimum worker capacity,
and polling pause/resume. Authorize every read and keep private snapshots out of shared CDN
caches. No change to Serverless Workers or the accepted price-snapshot model is needed.

## Current Workflow Streams assessment

Temporal still marks Workflow Streams **Public Preview**. Its advantages are a Workflow-hosted
event log, subscriber offsets, and no separate broker. The documented target of tens of
publishers/subscribers per Workflow is adequate for individual planning sessions; fan-out
limits are not the reason to reject it here. [Temporal overview](https://docs.temporal.io/workflow-streams)

The operational complication is that every publish batch is a Signal and every subscriber
poll is an Update. Both add History events. At the documented 200 ms LLM batching example,
a 30-second answer produces roughly 150 publish Signals, plus subscriber polling. Truncating
the stream does not delete those History events. [Tuning and History behavior](https://docs.temporal.io/workflow-streams#tuning)

The UI must still reconcile failed Activity attempts and missing buffered output. The library
deduplicates publishing retries, but a retried Activity is a new publisher. Preview status
alone does not prove instability; this is a choice about which complexity we want to own.
[Delivery semantics](https://docs.temporal.io/workflow-streams#how-events-are-delivered)

## Redis Streams compared with Workflow Streams

| Concern | Advantage | Cost or limitation |
| --- | --- | --- |
| Maturity | Core `XADD` / `XREAD` stream primitives have existed since Redis 5.0. | Managed Redis adds provisioning, private connectivity, monitoring, and ongoing cost. |
| Live text | Publish chunks from Activities without a Temporal Signal/Update cycle per batch. | Redis calls and client retries need bounded timeouts; measure actual latency. |
| Reconnect | Read retained events after a cursor; browsers can resume SSE. | We own cursor validation, duplicate handling, retention gaps, and snapshot recovery. |
| Multiple API instances/tabs | Each subscriber can independently read a stream without relying on process-local state. | Connection pools and slow-client buffers need caps. |
| Workflow lifecycle | UI events do not require stream-specific Continue-As-New state or a Workflow-closing acknowledgement. | Redis events and Workflow commits are not one atomic transaction. |
| Failure isolation | Planning can complete while the display channel is down. | Redis failover can drop connections and may lose recent events; it is not the canonical itinerary store. |

Sources: [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/),
[XREAD](https://redis.io/docs/latest/commands/xread/),
[Memorystore tiers](https://cloud.google.com/memorystore/docs/redis/redis-tiers),
[Memorystore HA and asynchronous replication](https://cloud.google.com/memorystore/docs/redis/high-availability).

## Proposed implementation boundary

1. Keep the Pydantic agent executing inside a Temporal Workflow. Its Activity-side
   `TemporalDurability(event_stream_handler=...)` publishes only display-safe text/status
   events to Redis, batched initially around 100–250 ms. Do not run the agent directly in an
   API request merely to obtain streaming. [Pydantic Temporal streaming](https://pydantic.dev/docs/ai/capabilities/durable_execution/temporal/#streaming)
2. Attach session, turn, model-segment, attempt, and sequence identifiers. Deduplicate retried
   writes and discard obsolete attempts. Multiple model Activities can occur in one agent
   turn, so an attempt number alone is insufficient.
3. FastAPI authorizes each session and forwards Redis events over the existing SSE route.
   Use independent `XREAD` cursors, not a shared consumer group that distributes events
   between clients. Cap buffering and reconnect slow consumers.
4. Use SSE event IDs for reconnect and explicitly handle a full page reload via a current
   snapshot. If Redis was trimmed, restarted, or is unavailable, discard incomplete text and
   recover from the canonical snapshot; polling remains the fallback. SSE already defines
   reconnect and `Last-Event-ID`. [HTML standard](https://html.spec.whatwg.org/multipage/server-sent-events.html)
5. A successful Temporal turn commits the canonical assistant message and itinerary. Only then
   publish a commit notification through an idempotent Activity. The client fetches the saved
   revision and replaces provisional text. If the notification is lost, reconciliation polling
   finds the revision. Do not rely on Redis as the only record that a turn completed.
6. Bound stream length and lifetime for resource use. Stream cleanup is unrelated to the
   ordinary price-snapshot retention decision. A Redis outage must not cause the model Activity
   to fail solely because provisional text could not be delivered. Log the degraded stream and
   complete the durable work.

One integration caveat: Pydantic currently documents that streaming model events are buffered
back to the Workflow and subject to its Activity payload limit. Redis removes the *additional*
per-batch Signals and subscription Updates; it does not automatically remove every captured
model event from Activity results. Verify payload growth with the pinned Pydantic version.
[Pydantic payload notes](https://pydantic.dev/docs/ai/capabilities/durable_execution/temporal/)

Acceptance: kill/retry a model Activity mid-stream; reconnect the browser to another API instance;
simulate missing/duplicated chunks and Redis loss; confirm one canonical response and itinerary,
no duplicated text, and no additional paid model call caused by a display-channel outage.

## Other transport alternatives

- **Redis Pub/Sub:** useful for ephemeral notifications, but disconnected subscribers permanently
  miss messages. A saved snapshot could recover completed text, but retaining chunks for short
  reconnects is useful for this chat UX. Redis Streams supplies that without inventing a separate
  replay log. [Redis delivery semantics](https://redis.io/docs/latest/develop/pubsub/)
- **PostgreSQL events + SSE:** reasonable if avoiding another service is the priority. We already
  use PostgreSQL. Store events in a table and use polling or `LISTEN/NOTIFY` as a wake-up hint;
  notifications alone are not the replay log. This adds frequent writes/reads and cleanup to the
  application database, plus listener/reconnect management. I prefer Redis for sustained token
  delivery; this is an architectural judgment, not a measured PostgreSQL capacity limit.
  [PostgreSQL NOTIFY](https://www.postgresql.org/docs/current/sql-notify.html),
  [LISTEN startup race](https://www.postgresql.org/docs/current/sql-listen.html).
- **Polling progress and completed messages:** the smallest MVP. Query Temporal through FastAPI
  and update status/cards every second or two. It gives up live text typing, so it is a product-scope
  alternative rather than a drop-in transport replacement. This is now the approved option,
  as detailed above.

## Other plan changes to consider

**Settled:** keep Temporal Serverless Workers. The owner has used them successfully on a recent
project and is fully comfortable with them. This research does not recommend changing worker
hosting or adding an alternative worker deployment.

1. **Approved and applied: bounded planning.** The main plan now specifies initial/follow-up
   deadlines, a fixed interaction window, turn/request caps, and a partial-result/failure
   outcome. Finalization sends committed state without another research pass. Email retries
   retain their own bounded delivery policy after interactive planning ends.
2. **Approved and applied: remove concierge operations.** The main MVP plan now has one automated
   public self-serve operating model. Concierge states, evidence commands/endpoints, acquisition
   methods, launch-mode schemas, metrics, and delivery requirements are removed. Honest partial
   results and external-search fallbacks remain.

The overall-deadline change and polling-only response delivery are approved and applied.
See the [approved simplifications](2026-09-06-mvp-simplifications.md) for the final scope. Keep the accepted SearchApi provider decision, simple price snapshots, typed
itinerary validation, and atomic revisions.
