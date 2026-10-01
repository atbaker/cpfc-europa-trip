# Travel provider options

Research date: 6 September 2026. Research used Exa searches and full-page retrieval of primary provider documentation, pricing, and terms. Direct web retrieval was used for the latest SearchApi announcement and Google documentation after Exa returned older snapshots. This supplements the [project review](2026-09-06-plan-and-implementation-review.md). The initial research involved no live API calls or supplier outreach. A subsequent user-authorized six-request SearchApi experiment is documented in the [spike results](2026-09-06-searchapi-spike.md).

## Recommendation

Start with a **SearchApi feasibility trial spanning flights, hotels, and ground travel**, following its September 3 announcement of Booking.com engines and Google train results. Use **FlightAPI** and **Makcorps** as targeted comparisons where SearchApi falls short. Keep **Omio's Meta Search API** as a possible ground-transport partnership if actual coverage requires it. **SerpApi** offers a larger visible organization but has direct Google litigation exposure. Treat **Duffel as requiring a negotiated agreement**, rather than assuming its excess-search fee permits this product. This changes the order of investigation; it does not yet select a production provider.

The product is a public travel planner. It will recommend options and send users elsewhere to complete purchases; it will not take payment or issue tickets. The owner accepts paid data and browser-assisted steps, and has early partnership discussions but no confirmed access. Off-site purchases through referral links can fit this product; a contractual obligation to generate bookings remains a separate commercial decision.

## Shortlist

Published monthly prices below are in USD. Credits and searches are billing units, not completed user itineraries. Coverage and reliability claims remain untested.

| Provider | Role | Published starting price | Assessment |
| --- | --- | --- | --- |
| FlightAPI | Flight prices and itinerary data | $49 for 30,000 credits | Strongest explicit search-only fit among the examined self-service options. |
| SearchApi | Google Flights, Google Hotels, Booking.com, and Google transit results | $40 for 10,000 searches; $100 for 35,000 | First integrated trial across all three travel categories; verify new-engine entitlement and request costs. |
| SerpApi | Google Flights and Google Hotels results | $25 for 1,000 searches; $75 for 5,000 | Useful alternative; compare actual completeness and handoff behavior. |
| Omio Meta Search API | Rail, coach, and flight search with off-site checkout | Custom commercial agreement | Closest match to the intended ground-transport referral journey; access is unconfirmed. |

Pricing sources: [FlightAPI](https://www.flightapi.io/flight-price-api/), [SearchApi](https://www.searchapi.io/pricing), [SerpApi](https://serpapi.com/pricing). Omio describes its product but does not publish the relevant contract pricing on its [B2B page](https://www.omio.com/corporate/omio-b2b/).

### FlightAPI: first flight experiment

Its FAQ explicitly says booking through the API is unsupported. It offers one-way, round-trip, and multicity pricing, itinerary details, and booking links. This is a data product whose stated function fits our intended use. [Product documentation](https://www.flightapi.io/flight-price-api/)

The terms expressly grant paid subscribers commercial storage, display, analysis, and redistribution of returned data. However, the data comes from public internet sources; this is not evidence of a direct airline distribution licence. Accuracy and non-infringement warranties are disclaimed. Its permission is useful evidence of the vendor's intended customer use, but does not establish all underlying suppliers' permissions. [Terms](https://www.flightapi.io/terms-and-privacy/)

One-way and round-trip requests each cost two credits, while multicity requests cost five. Therefore the entry allowance represents up to 15,000 round-trip requests if spent entirely on that endpoint. [Credit schedule](https://www.flightapi.io/documentation/getting-started/)

The example response contains relative redirect URLs and a `max_redirect_age` field. Establish how these become working user links and what their expiry means before relying on them in emailed plans. Documentation also gives inconsistent descriptions of some error codes, so contract tests must distinguish timeout from no inventory. [Response example](https://www.flightapi.io/flight-price-api/), [error documentation](https://www.flightapi.io/documentation/getting-started/)

### SearchApi: flights and hotels together

Its flight interface supports selecting outbound and return results and obtaining booking options through tokens. Hotel property results include offers with provider links. These are useful building blocks for an itinerary with a purchasing handoff, but one complete journey can require multiple API requests. [Flights documentation](https://www.searchapi.io/docs/google-flights-api), [hotel property documentation](https://www.searchapi.io/docs/google-hotels-property-api)

This is managed extraction of public search results, rather than a first-party Google inventory feed. Its legal protection covers collection and parsing, expressly excluding the customer's subsequent use, storage, redistribution, or commercialization. The protection is available on qualifying plans, not the $40 entry plan. Obtain written confirmation covering our public display, emailed recommendations, and retained quote history. Do not treat the legal protection as permission for all these activities. [Terms](https://www.searchapi.io/legal/terms), [pricing](https://www.searchapi.io/pricing)

#### September 3 update: Booking.com and train results

The August update, published September 3, 2026, announces Booking.com Search, Property, and Autocomplete APIs, plus `train_results` in Google Search. The announcement says train fields align with Maps Directions transit output. Exa's announcement snapshot initially stopped at July; direct retrieval confirmed the new release. [Announcement](https://www.searchapi.io/announcements)

Booking search supports exact dates, adult/child occupancy, rooms, currencies, cancellation filters, and flexible dates. Results distinguish stay and nightly prices and expose taxes, room descriptions, and property links. Property detail supplies room availability when both dates are supplied. Autocomplete provides destination identifiers. This suggests a practical destination → property shortlist → room-detail flow. [Search API](https://www.searchapi.io/docs/booking-api), [Property API](https://www.searchapi.io/docs/booking-property-api), [Autocomplete API](https://www.searchapi.io/docs/booking-autocomplete-api)

Google's train example returns a resolved date, ISO departure/arrival timestamps, transfers, fares, operators, purchasing offers, and station-level instructions. It uses a natural-language search query. The example does not establish reliable future-date control, passenger/railcard pricing, or comprehensive European coverage. Treat a missing widget as missing evidence, not proof that no trains run. [Train example](https://www.searchapi.io/docs/google)

For explicit time constraints, Maps Directions accepts `travel_mode=transit`, a train preference, and `time` values for departure, arrival deadline, or last available service. It documents transit schedules and ticket links. This is a useful candidate for airport–hotel–stadium routing and post-match departures, subject to route and fare coverage tests. [Maps Directions](https://www.searchapi.io/docs/google-maps-directions-api)

Proposed acceptance checks before relying on one vendor:

1. Search a hotel stay with fixed dates, GBP, and the actual party/room configuration. Compare availability and the final payable total on the destination site. Follow the property link with dates and occupancy preserved; the example bare property URL is not a guarantee of an exact-room purchasing handoff.
2. Test domestic and cross-border rail, for example London–Manchester, London–Paris, Paris–Lyon, and Munich–Salzburg. Use future dates and verify the returned service date and timezone explicitly.
3. Test an arrival deadline and a late stadium departure using Maps Directions. Determine whether prices and purchasable offers accompany schedules and whether they cover the intended passenger mix.
4. Check next-day email links, missing train widgets, unavailable rooms, request cost, and latency. A route without a fare must not enter the trip total as a zero-cost journey.
5. Confirm paid rights and any special engine billing. These are SearchApi interfaces to third-party sites, not evidence of a direct Booking.com or Google partnership.

Assessment: the functional match is materially better than the initial shortlist captured. A single SearchApi account could potentially cover the first useful travel-planning flow. Validate that hypothesis before adding multiple provider integrations or declaring ground transport solved.

### SerpApi: comparable alternative

SerpApi documents APIs for [Google Flights](https://serpapi.com/google-flights-api) and [Google Hotels](https://serpapi.com/google-hotels-api). Its published billing is search-based. It belongs to the same managed extraction category, so supplier and downstream-use questions remain relevant.

One integration detail is particularly useful: the flight booking-options example returns a `booking_request` containing a URL **and POST data**. That is not an ordinary hyperlink that can simply be pasted into an email. A browser handoff or an alternative search link may be necessary. This should be a trial acceptance criterion rather than a late implementation discovery. [Booking-options documentation](https://serpapi.com/google-flights-booking-options)

Follow-up litigation check: Google filed its case in December 2025. After dismissal with partial leave to amend on July 20, 2026, Google filed an amended complaint on August 10. SerpApi moved to dismiss again on August 24; a September 29 hearing is listed. The public docket was last updated August 27, so this is not a live PACER verification. The requested injunction makes service continuity a concrete issue. [Case docket](https://www.courtlistener.com/docket/72059948/google-llc-v-serpapi-llc/), [amended complaint](https://storage.courtlistener.com/recap/gov.uscourts.cand.461513/gov.uscourts.cand.461513.45.0.pdf)

### SerpApi versus SearchApi: funding and business size

Funding research checked 6 September 2026 using Exa. Both companies describe themselves as profitable and bootstrapped; no verified external funding round or named institutional investor was found for either. This does not establish cash balances, debt, or litigation reserves.

| Evidence | SerpApi | SearchApi |
| --- | --- | --- |
| Funding disclosure | Its CFO vacancy explicitly describes no outside investors. | Its own hiring advertisement describes a bootstrapped business without VC pressure. |
| Profitability | Describes itself as highly profitable; unaudited company statement. | Describes itself as profitable; unaudited company statement. |
| Visible team | 53 named people counted on its official team page; includes different employment arrangements. | LinkedIn-derived profile indicates seven people and a 1–10 size band; an approximate public footprint, not verified payroll. |
| Organizational depth | Public team includes multiple engineering leaders, customer success, finance, and general counsel. | Much smaller visible organization. |

Sources: [SerpApi CFO vacancy](https://serpapi.com/careers/chief-financial-officer), [SerpApi team](https://serpapi.com/team), [SearchApi hiring advertisement](https://www.linkedin.com/jobs/view/browser-kernel-engineer-at-searchapi-4431711376), [SearchApi company profile](https://www.linkedin.com/company/searchapi).

Funding databases are inconsistent: Sacra's SerpApi page displays $100,000 in a funding header but describes no external funding in its narrative; Tracxn also contains contradictory funded/unfunded language. Neither is strong enough to override the company's explicit current statement. Revenue aggregators provide estimates without financial statements establishing them. Do not use their precise revenue or valuation figures to infer runway. [Sacra](https://sacra.com/c/serpapi/), [Tracxn](https://tracxn.com/d/companies/serpapi/__xy8FgRRfrh0vd8ot5pWavh7g-Fj3nB_8seQ6j35ZKfo), [GetLatka](https://getlatka.com/companies/serpapi.com)

Assessment: SerpApi is the larger and more established visible operation, with stronger evidence of staffing depth. Financial stability remains unverified, and its direct Google case weighs against treating scale as a guarantee of continuity. SearchApi is not a demonstrably better-capitalized alternative and was itself sued by SerpApi in January 2026 over alleged misuse of intellectual property. Those are contested allegations; the latest disposition of that separate case has not been established here. [SearchApi complaint](https://serpapi.com/documents/serpapi-v-searchapi-complaint.pdf)

For this project, compare operational response and contractual continuity protections alongside data quality. Prefer monthly commitments and an interchangeable provider integration while these uncertainties remain. Ask shortlisted vendors about cash-flow profitability, support coverage, material litigation affecting service, and remedies if a travel endpoint becomes unavailable.

### Omio: pursue for ground travel

Omio explicitly describes a Meta Search API that displays train, bus, and flight results inside a partner's product, then sends the traveller to Omio or a branded checkout. This fits our decision to leave ticketing and payments elsewhere. Its separate Booking API is aimed at a different, merchant-of-record integration. [B2B product descriptions](https://www.omio.com/corporate/omio-b2b/)

Ask about paid search access, approval criteria, minimum volume, expected referral conversion, quote retention, and email links. No public evidence reviewed here establishes that Omio will sell unrestricted search-only access to a new service. Its suitability is architectural; commercial availability remains open.

## Why Duffel is not the default

Duffel's standard agreement restricts excessive search-to-order usage and allows caps to meet supplier requirements. More directly, section 2.5(d) prohibits metasearch use unless expressly permitted under the agreement. Our intended product needs explicit acceptance of its actual use case. [Services agreement, sections 2.3 and 2.5](https://duffel.com/services-agreement)

The published excess-search policy uses a 1,500:1 ratio and a $0.005 excess-search fee. Paying that fee does not, by itself, override the restrictions above. [Excess Search explanation](https://help.duffel.com/hc/en-gb/articles/4412912264466-What-is-Excess-Search)

Recommendation: ask whether Duffel offers a written search-only/metasearch exception with workable caps and pricing. Do not build the first integration around obtaining that exception.

## Makcorps: hotel specialist worth a trial

Expanded after the owner's follow-up on 6 September 2026. This revises the earlier assessment based on the basic hotel endpoint: the room-type endpoint supplies more information, including booking URLs. Makcorps belongs in the hotel evaluation alongside SearchApi, subject to commercial clarification.

### Connection to FlightAPI

Both sites identify Manthan Koolwal as founder. FlightAPI's founder account explicitly describes launching Makcorps and subsequently developing a flight-data product. This supports a common-founder affiliation; it does not establish identical contracting entities, shared subscriptions, or transferable licence terms. [Makcorps about page](https://www.makcorps.com/about/), [FlightAPI founder account](https://www.flightapi.io/about-us/)

### Product fit and cost

Makcorps markets hotel pricing data from 200+ online travel agencies and bills for requests. The reviewed public pages do not state a minimum booking volume or search-to-book requirement; absence from these pages is not a contractual guarantee. Current published plans are $350/month for 10,000 requests and $500/month for 50,000, with five concurrent calls. A trial offers 30 calls without a credit card. [Product and pricing](https://www.makcorps.com/)

The city endpoint returns approximately 30 hotels per page, with prices from up to four vendors, coordinates, and review information. It accepts dates, adults, rooms, children, and a tax-inclusion flag. Despite the introductory claim of a city's hotels in one request, actual discovery is paginated. [City API](https://www.makcorps.com/documentation/hotel-api-search-by-city-id/)

The room-type endpoint includes room descriptions, bed counts, cancellation labels, provider names, prices, and `bookingUrl`. Its sample URLs are relative and contain session-related parameters. The documentation asks customers to contact support for hotel IDs. Confirm ID mapping, link origin/expiry, multi-night price semantics, and whether returned links work outside the collecting session. [Room-Type API](https://www.makcorps.com/documentation/room-type-api/)

My proposed flow is city discovery, filtering by stadium access and budget, then fetching room offers for a few shortlisted properties. The planner should link to the selected offer only when the handoff is verified; otherwise it should clearly offer a hotel search link. A provider supporting searches without bookings could work well for this flow.

### Permission remains unresolved

The public terms' website-material licence is restricted to personal, non-commercial viewing, while another section describes paid platform licences. These terms do not clearly grant public display or emailed redistribution of API results. This ambiguity is not proof that commercial API use is forbidden, but FlightAPI's clearer licence must not be assumed to apply here. Obtain the applicable paid API agreement or a written amendment covering our use. [Makcorps terms](https://www.makcorps.com/terms/)

Proposed questions for Makcorps, not yet sent:

1. Can our paid account display rates in a public planner, retain timestamped quotes, and email recommendations, with zero bookings through the API?
2. What source permissions and attribution conditions apply, and are there any booking-conversion obligations?
3. Can room-type booking URLs be opened by another user in a fresh browser or email, and how are they resolved and refreshed?
4. How are city-search IDs mapped to room-type IDs, what does each endpoint cost, and how are taxes, room occupancy, and whole-stay totals represented?
5. Can Makcorps and FlightAPI be purchased under one agreement or a combined plan?

Recommendation: use the small trial for a discovery-to-room-offer test and request the commercial answers before choosing a paid production plan. At the published entry tiers, FlightAPI plus Makcorps would total $399/month before taxes and other infrastructure. The higher cost than SearchApi warrants a quality comparison, but is not itself a reason to reject Makcorps given the owner's willingness to pay for suitable data.

## Trial and commercial questions

Before choosing a production provider, send this concrete use-case description:

> We operate a public football travel-planning service. We want to pay for searches, display and compare prices, retain timestamped quote snapshots in trip history, and email recommendations and purchasing links. We will not create bookings through your API. Travellers will purchase on supplier or partner sites. Does your agreement permit this use, and what source, attribution, retention, referral-conversion, search-to-book, minimum-spend, or link-expiry conditions apply?

This is proposed outreach text only; it has not been sent.

Then run the same small test set against FlightAPI and SearchApi:

1. Use representative future UK-to-Europe routes, including London–Lyon and London–Istanbul, several nearby airports, and relevant low-cost carriers. These are test routes, not assertions of current fixtures.
2. Compare the quoted total with the destination site for identical dates, passengers, currency, baggage, and room occupancy. Record taxes, missing fees, and unavailable inventory explicitly.
3. Open purchasing links in a fresh browser immediately, after 30 minutes, and the next day. Test the emailed journey. Determine when to refresh a quote or fall back to a labelled search link.
4. Measure successful requests, retries, latency, empty results, and cost per completed plan. Limit date and airport combinations before expanding searches.
5. Choose the primary provider from observed quality and agreed permissions. Keep a provider adapter boundary and a clear unavailable-result state.

An illustrative starter comparison using FlightAPI's $49 plan and SearchApi's $40 plan would cost $89/month in subscriptions before taxes, model/browser costs, or upgrades. At SearchApi's entry allowance, a plan consuming 30 paid requests uses $0.12 of included search capacity; that is an arithmetic illustration at full allowance utilization, not a measured cost per user. Multi-step searches, retries, and broad date exploration will change it.

Use managed APIs for repeatable collection if the trials succeed. Reserve browser steps for verified handoffs or specifically approved gaps. Browser access does not itself resolve a provider's permission to use and redistribute data. The immediate decision is which services to test and clear commercially; the evidence does not yet justify calling any provider production-ready for this project.
