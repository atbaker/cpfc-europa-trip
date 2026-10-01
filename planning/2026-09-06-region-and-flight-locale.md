# GCP region and Google Flights locale

Checked: 6 September 2026, using Exa, primary documentation, and the owner's Chrome.
The resulting region and UK flight defaults are incorporated into [the MVP plan](mvp-plan.md).

## Frankfurt default

Use GCP **`europe-west3`** for regional application resources and Temporal Cloud
**`gcp-europe-west3`** for the namespace. Temporal currently lists Frankfurt as its only
European GCP region; it also offers European AWS regions. Its documentation recommends
placing namespaces close to Workers to reduce latency.
[Temporal Cloud regions](https://docs.temporal.io/cloud/regions#europe---frankfurt-europe-west3)

Apply the region to Cloud Run API/Worker Pools, Cloud SQL, Artifact Registry, regional
networking/buckets, and deployment defaults. Global load balancing and CDN remain global.
This changes the plan, not deployed infrastructure; the repo is awaiting reimplementation.
Other providers' processing locations are not implied by our GCP region.

## Chrome observations

| URL tested | Observed behavior |
| --- | --- |
| `https://www.google.co.uk/travel/flights` | Loaded successfully with British-English language, but the location was **United States** and currency **USD**. A UK hostname alone did not select the intended market/currency. |
| `https://www.google.com/travel/flights?hl=en-GB&gl=GB&curr=GBP` | Footer showed **English (United Kingdom)**, **United Kingdom**, and **GBP**. Suggested fares displayed pounds. The default departure city remained San Francisco, so market settings do not replace explicit itinerary/origin parameters. |
| Existing SearchApi selected-itinerary URL on `google.com`, preserving `tfs`/`tfu` and setting `hl=en-GB&gl=GB&curr=GBP` | Preserved two adults and the easyJet London Gatwick–Lyon round trip, outbound 4 October 2026 at 08:15–10:55 and return 6 October at 06:55–07:35. Footer showed UK/GBP settings. Lowest displayed total was £156, with the easyJet seller at £158; Google showed a price-change notice. |

The selected URL came from the earlier spike's
`scripts/.data/searchapi-spike/20260906T174028466134Z/03-flight-booking.json`.
Only its locale query parameters were changed for this check. No new paid SearchApi requests
were made, no seller checkout was opened, and no price-tracking subscription was enabled.

These are observations in one existing Chrome profile, not an isolated all-country test.
The domains had different existing sign-in state. The test establishes that a UK hostname
was insufficient in this environment and explicit parameters worked on the sampled pages;
it does not establish which cookie, location, or account preference caused every default.
The newly observed prices are not attributed to locale changes and do not reprice the old
API result. The previous snapshot remains a separate historical observation.

Google documents that its default Flights experience depends on location and browser settings.
Users can change location, language, and currency in the page footer. Location can also affect
available booking partners and purchase options, so currency alone is not a complete market
selection. [Google Flights help](https://support.google.com/travel/answer/7378789?hl=en-GB)

## Implementation choice

- Default the product's travel market to `GB`, language to `en-GB`, and currency to `GBP`.
- For SearchApi `google_flights`, explicitly send `gl=GB`, `hl=en-GB`, and `currency=GBP`
  for discovery and token-based follow-ups. The earlier spike used `gl=uk` and `hl=en`;
  use the documented Travel-specific values for the rebuilt integration.
- For browser handoffs, prefer `google.com` and explicitly set `gl=GB`, `hl=en-GB`, and
  **`curr=GBP`**. Preserve the provider URL's itinerary tokens, path, and remaining parameters
  with a URL parser. Validate host/path before modifying a link.
- Keep dates, airports, selected legs, and passenger count explicit. Locale is separate from
  departure location, country of travel, and the Frankfurt server region.
- Use the same market/currency that produced the displayed estimate. Do not silently switch
  the seller market solely because the supporter is temporarily abroad or uses a VPN.
- Defer automatic IP geolocation, country-to-domain mappings, and a new locale-selection UI.
  Google still permits users to change settings after the handoff. If our app later supports
  user-selected markets, apply that choice consistently to acquisition and outbound links.

SearchApi documents these localization parameters and lists `GB` and `en-GB` as supported
Google Travel values. The browser tests establish handoff behavior; this turn did not perform
a new live API search with the revised localization defaults.
[Google Flights API](https://www.searchapi.io/docs/google-flights-api),
[supported countries](https://www.searchapi.io/docs/parameters/google-travel/gl),
[supported languages](https://www.searchapi.io/docs/parameters/google-travel/hl).
