# Non-London route audit — 5 October 2026

## Scope and method

Ran the application's live SearchApi adapters, shared 24-hour cache, default date enumeration, and `choose` feasibility check. The brief used one adult, one room, value budget, default day-either-side flexibility, and an explicit flight or rail choice. Each case tried up to three date pairs around its match. A complete result required a dated return journey **and** a matching stay. This is an adapter/planning audit, not a full browser-to-Temporal session test or a booking confirmation.

Four non-London cities were selected with Python `Random(20261005).sample(...)`: Glasgow (GLA), Inverness (INV), Edinburgh (EDI), and Birmingham (BHX). Nottingham (EMA) was added to revisit the recently failed session. Manchester (MAN) was added as a busy-airport control. Each city had a flight case for each of the four games. Lyon rail was also checked for Edinburgh, Birmingham, and Manchester, the selected cities with an enabled rail route. The 27 cases made **122 live provider HTTP requests** (102 in the initial sample, 20 for Manchester), below the respective 150- and 50-request caps. The SearchApi account counter rose from 551 to 673 of 10,000 monthly requests during these runs. Positive cache hits were reused; empty or failed results were not cached.

| Starting city | Lyon flight | Istanbul flight | Białystok via Warsaw flight/rail | Salzburg flight | Lyon rail |
| --- | --- | --- | --- | --- | --- |
| Glasgow (GLA) | No nonstop | No nonstop | No nonstop to WAW | No nonstop | Not enabled |
| Inverness (INV) | No nonstop | No nonstop | No nonstop to WAW | No nonstop | Not enabled |
| Edinburgh (EDI) | No nonstop | **Complete** | No nonstop to WAW | No nonstop | **Complete** |
| Birmingham (BHX) | No nonstop | Flight + stay; arrival too late | No nonstop to WAW | No nonstop | No connection met reviewed buffers |
| Nottingham (EMA) | No nonstop | No nonstop | No nonstop to WAW | No nonstop | Not enabled |
| Manchester (MAN) | No nonstop / one provider timeout | Flight + stay; arrival too early | No nonstop to WAW | No nonstop | **Complete (cached)** |

“No nonstop” means the provider returned no qualifying **round-trip, nonstop** flight for each of the three default date pairs. It does not establish that the city lacks all air service or a connecting itinerary. The Manchester–Lyon third pair ended with incomplete provider evidence after a timeout; the first two returned no nonstop option. The Białystok cases never reached the Warsaw onward-train stage because no qualifying round-trip flight to WAW was found.

## Feasibility findings

- Edinburgh–Istanbul completed on 21–23 October with one qualifying journey and two matching stays. Edinburgh–Lyon rail completed on 14–16 October with 12 connected journeys and two stays. Manchester–Lyon rail completed from the positive shared cache with the same counts. These checks exercise the current adapter and deterministic trip selector, not the full Temporal workflow.
- Birmingham–Istanbul had one round-trip journey and two stays on each tested pair. The 21–23 October outbound arrives at **23:35 local**, outside the route's configured 06:00–23:00 gateway-arrival window. The shorter pairs also fail the five-hour-before/after-kickoff rule. The planner correctly rejects these under current rules, but its generic “Travel and accommodation evidence is incomplete” message does not explain the timing gate.
- Manchester–Istanbul likewise had journeys and stays on all three pairs. Its 21–23 October outbound lands at **04:55 local**, before the configured 06:00 arrival floor. The shorter pairs also fail kickoff timing. An overnight flight with a prior-night hotel might be usable after confirming early arrival, transfer and hotel access; that is **unverified**, so this audit does not mark it complete.
- Birmingham–Lyon rail returned no dated connection meeting the reviewed London and Paris transfer buffers on its three date pairs. The audit saw transient provider read timeouts and retries; it cannot rule out a usable service outside these dates or after provider recovery.

## Conclusions and follow-up

**Three of 27** tested route/mode cases produced a complete trip. **Twenty** flight cases returned explicit no-nonstop results across all three date pairs. Two Istanbul flight cases had both transport and stays but failed the configured arrival-time gate. One Lyon flight case had incomplete provider evidence on its final date pair. One Lyon rail case had no connection passing transfer buffers. There is no evidence in this sample of `choose` discarding an option that satisfies every current feasibility rule.

The largest coverage constraint is the nonstop-only flight policy and the narrow default date window, not the presence of a UK city in the dropdown. A separate product decision is needed before admitting connecting flights or overnight arrivals: both require transfer, check-in and timing checks, and a clearer user-facing reason when an evidenced option is rejected. The city list should be described as searchable departure points rather than a promise that every game can be planned from each city. Recheck prices, timetables and room availability before booking; these results are a 5 October snapshot.
