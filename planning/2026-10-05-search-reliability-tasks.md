# Search reliability tasks — 5 October 2026

Scope: live SearchApi travel acquisition for one planning turn. Keep the existing
Temporal turn limits (180 seconds initially, 90 seconds for a follow-up), 64/16
request allowances, 128 session allowance, and four concurrent search jobs.

- [x] **Search in waves.** Run one route/date candidate per fixture first. After
  each wave, evaluate whether every fixture has a complete trip. Search the next
  candidate for comparison when one exists and budget/time remain; stop after a
  complete comparison or when no further candidate fits. Preserve completed
  batches and session cache, and label incomplete evidence honestly.
- [x] **Retry the failed provider request only.** Retry a transient SearchApi HTTP
  failure once with identical parameters. Do not repeat successful discovery,
  token, or property requests. Do not retry permanent 4xx or invalid responses.
- [x] **Enforce paid attempt and time bounds.** Count every HTTP attempt, including
  retries, inside each adapter's reserved maximum. Stop before the turn or session
  budget can be exceeded. Keep a finite request timeout and adapter Activity
  deadline; the Workflow's existing turn deadline remains the outer bound.
- [x] **Verify.** Cover wave ordering/early stop, one failed-request retry,
  permanent failure, request exhaustion, replay, and existing provider contracts.

This changes search breadth, so a complete first candidate may be returned with
fewer alternatives. It does not add another data provider or promise market-wide
lowest prices.

Implementation note: a flight search reserves at most six HTTP attempts, rail or
stay eight. Completed Activities release unused reservations; interrupted or
unknown outcomes keep their full reservation. Each provider request has a
20-second timeout; an adapter is capped at 80 seconds; wave results are collected
up to two seconds before the turn deadline. A slow later wave can therefore leave
an earlier complete trip intact. The 5 October local test run passed 52 tests;
two PostgreSQL tests were skipped because no test database was configured.
