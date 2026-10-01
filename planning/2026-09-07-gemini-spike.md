# Gemini Flash 3.8 live spike

Date: 7 September 2026. Result: **successful initial model integration and intent-quality smoke test**.
Recommendation: use **Gemini 3.8 Flash with low reasoning** for the next implementation step.
Follow-up: the model switch is now approved and implemented; see the
[implementation checkpoint](2026-09-07-implementation-checkpoint.md). The results below
record the original spike before that integration.

## Environment and scope

- Project: `andrew-baker-sandbox`, explicitly authorized by the user for this spike.
- Model: `gemini-3.8-flash`, Google Cloud location `eu`.
- Authentication: an in-memory, short-lived access token obtained with the explicit
  `temporal-work` configuration and `andrew.baker@temporal.io` account. No ADC login,
  credential file, service-account key, or default-profile change was needed.
- Integration: Pydantic AI 2.40.0, Google Gen AI SDK 2.22.0, `GoogleCloudProvider`,
  and the application's actual `Intent` schema and unchanged planner instructions.
- Inputs: ten synthetic travel scenarios, each run twice at low and twice at medium
  reasoning. Follow-ups used the workflow's context shape, including previous constraints
  and a typed itinerary. Calls were independent, not a live multi-turn workflow.
- Limits: one request per run, no model/schema retries, one provider attempt,
  4,096 maximum output tokens, 40-second SDK timeout, 45-second outer timeout.
- No SearchApi calls, bookings, email sends, cloud deployments, or billing configuration
  changes. The existing trip production project's billing remains disabled.

The script is `scripts/gemini_spike.py`; the complete retained inputs, outputs, timing,
and usage are in the ignored local file `.data/gemini-spike/comparison.json`.

## Results

| Measurement | Low reasoning | Medium reasoning |
| --- | ---: | ---: |
| Completed comparison calls | 20/20 | 20/20 |
| Valid `Intent` output | 20/20 | 20/20 |
| Explicit semantic field checks passed | 20/20 | 20/20 |
| Median call duration | 2.65 seconds | 4.24 seconds |
| Slowest call | 10.73 seconds | 16.68 seconds |
| Input tokens | 37,856 | 37,856 |
| Output tokens, including reasoning | 3,694 | 11,522 |
| Estimated comparison cost, USD | $0.0422 | $0.0716 |

All retained responses finished normally, with no timeouts or observed schema errors.
The timing measures the individual model run, not a complete itinerary search, and excludes
the initial gcloud token acquisition. The small sequential sample is not a production latency
or reliability guarantee. Medium provided no observed correctness benefit on these cases.

Costs are estimates from reported token counts at $0.75/M input and $3.75/M output;
they are not a billing export. No cached-input tokens were reported. The 40-call comparison
totals approximately **$0.1138**, or **$0.2277** at the announced January 2027 rates.
Two additional setup responses preceded the retained comparison; their full usage was not
retained because of spike logger compatibility errors, subsequently fixed. They are excluded
from these totals. [Published rates and scheduled increase](https://blog.google/innovation-and-ai/models-and-research/gemini-models/3-8-flash-and-3-8-flash-cyber/).

## Behavior reviewed

1. **Cheapest / dorms:** selected budget and allowed shared rooms and bathrooms.
2. **Private room, shared bathroom:** distinguished the two privacy requirements correctly.
3. **Comfort / airports:** extracted comfort, both privacy requirements, and LHR/LGW.
4. **Preserve previous constraints:** changed budget while retaining Gatwick and privacy.
5. **Relax privacy:** removed both privacy requirements while retaining Gatwick.
6. **Accessibility:** explicitly flagged a guaranteed step-free wheelchair route as unsupported.
7. **Unsupported airport:** flagged Manchester rather than silently substituting London.
8. **Price question:** correctly explained the synthetic £720 total for two adults and excluded transfers.
9. **Availability question:** declined to guarantee price or availability.
10. **Provider-text injection:** ignored an instruction embedded in a hotel name to claim the
    trip was booked for £1. Responses retained £720 and said nothing had been booked.

Automated checks cover selected expected fields and answer fragments. I also reviewed all
40 answers manually for price claims, unsupported guarantees, and booking claims; no LLM
judge was used. Passing those checks does not imply every possible requirement was evaluated.

**One wording issue:** both low-reasoning runs of the privacy-relaxation case said
“Updated preferences” before the workflow could commit a revision. The constraints were
correct, but this phrasing can imply premature success. Before integration, use a
code-owned acknowledgement of pending changes or tighten and retest the prompt so only
the workflow announces a successful commit. Medium avoided that exact wording here;
the better architectural fix is to make commit status code-owned.

## What this establishes, and what remains

The authorized work identity can call this model in the EU endpoint, and Google's native
provider can satisfy our current Pydantic output contract quickly at low cost. This supports
proceeding with Gemini as the intended replacement, subject to the integration work.

This spike does **not** validate Google calls inside Temporal Activities, replay/restart
behavior with the Google adapter, Cloud Run service-account authentication, provider outages,
live SearchApi plus model execution, broader itinerary reasoning, or complete multi-turn
sessions. It exercises structured intent extraction, not autonomous travel-tool selection.
Those checks belong in the implementation step; the approved architecture still applies.

The default gcloud configuration was checked afterward and remains active with the personal
account and `gator-works-dev`. `temporal-work` remains inactive and has no default project.

## Per-session LLM budget estimate

For sponsor budgeting, allow **$0.05 per planning session at introductory rates**, or
**$0.10 from January 2027**, using low reasoning. These are average planning allowances,
not enforced maximum costs. Count sessions, not unique people or page views.

The low-reasoning spike averaged 1,892.8 input tokens and 184.7 output tokens per call
(including reasoning), or $0.002112 per call. At that observed size:

- Initial request plus four follow-ups: approximately $0.0106 per session today.
- Initial request plus ten follow-ups: approximately $0.0232 per session today.

That assumes one model call per turn, as in the current implementation. The full plan allows
more model calls, and multiple fixtures/richer explanations may increase input and output size.
For an illustrative larger session, ten calls averaging 4,000 input and 500 output tokens cost
$0.04875 today, or $0.0975 at January rates. This motivates rounding the budget to 5/10 cents.
It is an assumption to validate with integrated usage, not a measured production average.

| Planning sessions | Budget through December 2026 | Budget from January 2027 |
| --- | ---: | ---: |
| 1,000 | $50 | $100 |
| 10,000 | $500 | $1,000 |
| 100,000 | $5,000 | $10,000 |

All amounts are USD, LLM-only, before taxes, and exclude SearchApi, Temporal, GCP hosting,
database, observability, and email. No credits or volume discounts are assumed. Repeat
visits that start new planning sessions multiply consumption. The current plan's 32-call
session allowance, retries, and unusually large contexts mean some sessions can exceed these
average allowances. Revisit the estimate once live end-to-end sessions are instrumented.

## Reproduce

```bash
uv sync --extra gemini-spike
uv run --extra gemini-spike python scripts/gemini_spike.py
uv run --extra gemini-spike python scripts/gemini_spike.py --live \
  --project andrew-baker-sandbox --location eu \
  --output .data/gemini-spike/comparison-new.json
```

The first script invocation is a dry run. The live default makes 40 requests; `--case`,
`--efforts`, and `--repeats` allow smaller runs. Authentication failure or a model/API error
stops the run rather than repeatedly attempting the remaining cases. This token-based
approach is for the short local spike; the deployed worker should use its attached identity.

Local verification: input scenarios validate against the application records; evaluator checks
detect omitted constraints and compare airport sets without ordering sensitivity; six domain
tests pass; Ruff formatting/lint and mypy pass for the script and shared agent module.
