# SearchApi proof of concept

**Decision update — 6 September 2026:** feasibility spike accepted as successful. The user
accepts Google Flights search/itinerary pages as flight handoffs; direct airline checkout and
exact seller POST replay are not MVP requirements. SearchApi is selected for initial flight,
hotel, and train results. Earlier incomplete-status assessments below describe the validation
stage at the time; remaining gaps now belong to integration and launch readiness, as recorded
in the [updated MVP plan](mvp-plan.md#selected-provider-and-spike-evidence).

Run: 6 September 2026, approximately 17:27 UTC. Synthetic travel dates: 4–6 October 2026.
Two adults were requested for flights and accommodation; rail passenger pricing was not specified.

## Result

All six live HTTP requests returned 200 with useful structured result blocks. SearchApi is a
credible candidate for the first integration, including UK and cross-border rail. This establishes
API feasibility for these examples, not verified supplier prices, complete coverage, or permission
to publish the data.

| Scenario | Result | Wall time |
| --- | --- | --- |
| London airports → Lyon, round-trip flight discovery | 8 flight options | 1.69 s |
| Booking.com Lyon search, two nights, two adults, one room | 25 properties on page one; 838 total reported | 2.46 s |
| Booking.com detail for the first property | 5 room entries | 3.02 s |
| London → Manchester train search | 40 results; returned date and every departure date matched 4 October | 2.54 s |
| London → Paris train search | 19 results; returned date and every departure date matched 4 October | 1.80 s |
| Lyon airport → Part-Dieu transit | 6 routes; no `buy_ticket` blocks | 1.31 s |

Evidence: the ignored local run directory
`scripts/.data/searchapi-spike/20260906T172719255839Z/` contains redacted responses and `summary.json`.
No retries, pagination, supplier-page visits, or bookings were performed during the API run. The
subsequent Chrome checks are documented below. Six requests were sent
to SearchApi; the account's billing-credit consumption was not independently checked. An earlier
sandbox-blocked run recorded five connection failures in a separate directory and is not part of
these live results.

## Findings affecting implementation

1. **Dated rail searches worked in both examples.** Natural-language queries produced the intended
   future date, explicit timezone offsets, fares, operators, and purchasing URLs. London–Paris
   results included Eurostar and Omio links. Keep validating the returned date rather than assuming
   a date in the query is always honored.
2. **Use the selected seller's price.** One Eurostar service had a headline £58 fare, but its
   Eurostar offer was £65 while Omio was £58. Pair each displayed price with that offer's link;
   do not attach the cheapest headline price to an arbitrary seller. These are API observations,
   not browser-verified quotes.
3. **Transit timing needs investigation.** We requested Unix timestamp `1791100800`, equivalent to
   4 October at 10:00 Europe/Paris. Returned windows were labelled Europe/Paris but started at
   08:07 through 09:22. The response echoed the requested timestamp but the windows lacked calendar
   dates. We have not established whether this comes from request interpretation, source behavior,
   or parsing. Do not use this response to enforce arrival/departure constraints yet. None of the
   six routes had a purchasable fare, so their cost remains unknown.
4. **Accommodation suitability follows the user's preferences.** The search included a dormitory
   and a room with shared shower/toilet: both are valid candidates for a "cheapest" request and
   should remain eligible unless the user specifies otherwise. Clearly label dorm beds versus
   private rooms, shared versus private bathrooms, review scores, and whether the quoted total
   covers the whole party. The first property's 5.6 review score is information to show, not an
   automatic exclusion. Apply room, bathroom, or review-score filters only when the user asks for
   those constraints. The current spike preserves all returned accommodation categories.
5. **Hotel detail linked successfully to discovery.** The first listing's £59 twin-room price
   appeared again in its room details for the same dates and party. Search separately returned £9
   in taxes/charges. Verify the meaning of included/excluded taxes before computing a payable total.
   Property links were bare URLs without stay parameters, and room entries did not establish an
   exact-rate checkout link. Build and verify the dated, occupied handoff separately.
6. **Flights remain discovery-only.** This spike did not select an outbound flight, retrieve its
   returns, or resolve booking options. The eight results are not eight fully verified round trips.

## Running the spike

The script is `scripts/searchapi_spike.py`. Set `SEARCHAPI_API_KEY` in the root `.env`; the
script declares its own dependencies for `uv run`. The old application and environment template
were removed during the rebuild reset; set `SEARCHAPI_API_KEY=...` in `.env` or the environment.

```bash
# No SearchApi requests or credits; uv may fetch dependencies on first use.
uv run scripts/searchapi_spike.py

# Same scenarios with at most six HTTP requests.
uv run scripts/searchapi_spike.py --live --date 2026-10-04 --nights 2

# Focused later runs, each with a separate timestamped output directory.
uv run scripts/searchapi_spike.py --live --scenario hotels --max-requests 2
uv run scripts/searchapi_spike.py --live --scenario trains --max-requests 2
```

Defaults are 28 days ahead and two nights. Past dates are rejected. Credentials are sent in an
Authorization header, removed from persisted response fields/echoes, and never printed. `.env`
and `scripts/.data/` are Git-ignored. Account errors and rate limits stop further requests.
Before the rebuild reset, seven offline tests covered request caps, account-error stopping, credential redaction, train-date mismatch, and
non-JSON errors. Ruff passed on that implementation.

## Chrome handoff validation — 6 September 2026

Used the user's Chrome to check one hotel and one Eurostar offer from the saved run, through
the price summaries available without supplying personal details. No purchase was completed,
personal details entered, or payment submitted. Eurostar automatically created a temporary
ticket hold when advancing into checkout. These are observed quotes, not guaranteed future prices.

| Sample | API quote | Browser result | Validation boundary |
| --- | --- | --- | --- |
| Loft ViaRhôna, Grand loft en Centre-Ville, Lyon; Twin Room; 4–6 October; two adults, one room | £59 plus separately reported £9 taxes/charges | £68.59 including taxes and fees; payable in property currency **€79.80** | Booking.com “Your Details” checkout price summary; stopped before submitting guest information |
| Eurostar 9008; London St Pancras → Paris Gare du Nord; 4 October, 08:01–11:42; Standard | Eurostar seller offer £58 | **€67 total for one adult**, unchanged through the payment page | Guest checkout displayed total beside the payment button; no payment action taken; GBP parity remains unverified |

### Hotel: matching room, but the headline is not the total

The [original property link](https://www.booking.com/hotel/fr/loft-viarhona-grand-loft-en-centre-ville.en-gb.html)
opened successfully but asked for dates. Adding `checkin=2026-10-04`, `checkout=2026-10-06`,
`group_adults=2`, `group_children=0`, and `no_rooms=1` restored the intended stay. Adding
`selected_currency=GBP` did not initially override this browser's USD display; selecting GBP
through the visible currency control did.

The availability table showed the same £59 Twin Room for two nights and two adults, excluding
10% VAT and 5.5% city tax. Selecting one room produced a checkout total of £68.59, including
£9.20 in taxes and fees. Its individually displayed tax components were £5.94 VAT and £3.27
city tax; those rounded components differ by a penny from the displayed tax subtotal. Preserve
the supplier's authoritative total rather than reconstructing it from rounded display values.
The API's rounded £59 + £9 would give £68, understating this checkout by £0.59.

Booking.com explicitly described GBP as an approximate conversion and EUR as the payment
currency. Breakfast was optional and not selected. The rate was partially refundable; bed
preference remained unselected. The next step required guest details, so the later “Finish
booking” screen was not inspected.

### Eurostar: exact service carried through, currency and party require care

The saved Eurostar purchasing URL used `/google/redirect` with the service date, stations,
times, and train identifier. It selected the correct 08:01 service and date, with **one adult**.
The spike's train query did not specify a passenger count; the two-adult flight/hotel setting
does not make this a two-adult rail quote.

The redirect chose Eurostar's global `rw-en` storefront, with US country metadata, and priced
the Standard ticket at €67. The extras step and guest payment page both retained €67, with no
optional upgrade selected. Selecting United Kingdom on Eurostar's homepage and reopening the
same original referral still redirected to `rw-en` and €67. Thus the link works, but the API's
£58 has not been reproduced as a GBP checkout total. Do not label this as a confirmed price
mismatch or assume an exchange rate explains it without a matching-currency comparison.

### Integration consequences and remaining checks

- Carry dates, room count, and occupancy into hotel handoffs, then verify the destination state.
- Track quoted currency separately from payment currency, plus whether tax is included and
  whether a price is rounded. Show approximate converted totals as approximate.
- Make rail passenger count explicit and validate the selected seller, train, date, and fare
  class. Do not multiply a single-adult fare and present it as a verified group quote.
- Keep a quote timestamp and verification stage; an API discovery price and a checkout total
  provide different levels of evidence.

These checks cover two sampled offers only. London–Manchester seller links, other hotel room
types, and flight booking links remain unverified. Next: reproduce Eurostar in GBP, complete
one flight selection, and isolate the transit timezone discrepancy before broadening coverage
or integrating the provider into the planner. No additional SearchApi requests were made for
this browser validation.

## Flight selection and handoff — 6 September 2026, 17:40–17:45 UTC

**Status: a complete round-trip flight sample now reaches an airline with matching itinerary
and occupancy. The overall spike remains incomplete against the fidelity criteria below.**

Following [SearchApi's Google Flights documentation](https://www.searchapi.io/docs/google-flights-api),
the same `google_flights` engine supports discovery, `departure_token` for return selection,
and `booking_token` for the selected itinerary and seller offers. All stages retained the
original airports, 4–6 October dates, two adults, economy, GBP, and UK search localization.

The script now offers an explicit bounded follow-up mode:

```bash
uv run scripts/searchapi_spike.py --live --scenario flights --flight-followups --date 2026-10-04 --nights 2 --max-requests 3
```

It chooses the cheapest token-bearing outbound and then return, breaking ties by provider
order. This is a reproducible API experiment, not a recommendation algorithm. All requests
share the existing cap, account-error stopping, and credential redaction. Missing tokens or
empty offers must be treated as incomplete evidence, even if HTTP responses succeed.

Five additional live requests all succeeded: three for easyJet and two follow-ups using the
British Airways outbound from the same discovery response. Evidence directories:

- `scripts/.data/searchapi-spike/20260906T174028466134Z/`: discovery, returns, booking, summary.
- `scripts/.data/searchapi-spike/20260906T174158197727Z/`: BA returns and booking responses.

| Sample, two adults, round trip | API seller quote | Chrome comparison | Outcome |
| --- | --- | --- | --- |
| easyJet U2 8429, LGW→LYS, 4 Oct 08:15–10:55; U2 8430, LYS→LGW, 6 Oct 06:55–07:35 | £148 | Google Flights showed the same legs and two adults, but £153; easyJet then displayed an error page | Itinerary reproduced at Google; airline price/handoff not verified |
| BA 356, LHR→LYS, 4 Oct 11:40–14:25; BA 357, LYS→LHR, 6 Oct 11:20–12:10 | £440 with British Airways | Google Flights BA offer £440; airline flight summary **£439.30** for two adults, Economy Basic | Exact itinerary and party reproduced at airline; supplier summary price verified |

All times above are local airport times. BA's price breakdown showed £219.65 per adult:
£130 fare, £25 carrier charge, and £64.65 itemized taxes/fees. The £0.70 difference from the
integer API quote is consistent with display rounding, but no universal rounding rule has
been established. This was the airline's flight-summary stage, before passenger details,
seats, extras, final review, or payment. No personal information or payment was submitted.
Checked baggage was not included in the selected API offer; optional extras remain additional.

The BA booking response returned six sellers. Chrome additionally showed an Opodo offer at
£434 that was absent from that response. Seller coverage and prices can differ between API
and browser observations. Match the intended seller, not Google's cheapest headline.

### Handoff implementation detail

The API's seller `booking_request` is a Google URL plus **POST form data**, not necessarily a
plain airline GET link. In this browser check we opened the response's Google Flights
`search_metadata.request_url`, verified the selected trip, and clicked its airline Continue
button. This proves that browser-assisted route. It does **not** independently prove that
replaying the exact API-returned POST payload works. Preserve the distinction in the adapter;
do not render the bare `/travel/clk/f` URL as a usable seller link.

The initial easyJet price discrepancy (API £148 versus browser £153) and airline error remain
unexplained. We did not infer that the cause was cache age, regional pricing, or SearchApi
parsing. BA offers an independently successful sample but does not resolve easyJet reliability.

### Completion criteria for the spike

For each mode, require dates, local times where relevant, endpoints/property, party size,
fare/room category, price currency and scope, taxes/baggage treatment, and a usable handoff.
Record exactly which stage was verified. An HTTP 200 or discovery result alone is insufficient.

| Mode | Evidence established | Remaining fidelity gap |
| --- | --- | --- |
| Flights | Both selected legs and seller offers via API; BA exact itinerary and two adults at airline summary | Exact API POST handoff untested; easyJet error and £5 drift unresolved; connecting-flight and baggage variants not tested |
| Hotels | Correct room, dates, two adults; checkout total and payment currency | Parameterized handoff needed; rounded API fields cannot reproduce pennies; exact rate link not established |
| Trains | Correct Eurostar service/date; one-adult €67 at payment page | GBP API quote not reproduced; two-adult/group pricing not proven |

For an initial feasibility milestone, BA demonstrates that SearchApi can supply a faithful
flight itinerary with a browser-assisted airline handoff. Do not mark the three-mode spike
complete until the remaining party, price, and handoff gaps have either passed explicit tests
or have an agreed product fallback. Wider route coverage remains a separate readiness step.

Validation: added an offline test that ensures both flight follow-ups preserve party/date/
currency constraints and replace the departure token with the booking token. Ruff passes;
all 24 Python tests pass.

## Repository reset — 6 September 2026

The old application, dependency manifests, and test suite were removed for a fresh implementation.
Historical checks above remain evidence of the spike at the time. The retained script now has
inline dependencies and runs with `uv run scripts/searchapi_spike.py` independently of the app.
Local raw responses were moved unchanged from `.data/` to `scripts/.data/`, which remains
Git-ignored. All evidence-directory references above point to the new location.
