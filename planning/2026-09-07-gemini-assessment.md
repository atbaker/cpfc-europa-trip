# Gemini assessment for the travel planner

Research date: 7 September 2026. Sources discovered and retrieved with Exa.
Status: recommendation for a live model spike; no provider switch has been approved or implemented.

Follow-up: the [live Gemini spike](2026-09-07-gemini-spike.md) is now complete and supports
low reasoning for the next implementation step. The assessment below records the research
that preceded that experiment; the application provider has not yet been switched.

## Recommendation

Gemini is a credible primary model candidate. Test **Gemini 3.8 Flash through Google Cloud**, comparing low and medium reasoning on our actual structured travel requests. This could remove the dependency on obtaining an OpenAI API token while keeping Pydantic AI, Temporal, SearchApi, polling, and the storage architecture.

Google released 3.8 Flash on **2 September 2026**, following 3.7 Flash in August. Google Cloud lists 3.8 as generally available with function calling and structured output. It is only five days old, so there is not yet a mature production consensus. [Google announcement](https://blog.google/innovation-and-ai/models-and-research/gemini-models/3-8-flash-and-3-8-flash-cyber/), [Cloud model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash).

## What developers and evaluators report

- **Encouraging firsthand experience:** an August practitioner review of 3.7 describes substantial improvements in instruction following, tool sequencing, reading tool results, and recovering from failed approaches. It still reports drift in longer sessions and differences between agent environments. This is one developer's coding experience, not evidence of a travel API deployment. [Karasune review](https://karasune.vercel.app/blogs/gemini-3-7-flash-is-a-turning-point).
- **Concrete structured-output concerns:** an August developer forum report includes a reproduction of 3.7 generating repeated digits in schema-constrained JSON until exhausting its output limit. The author also reports production occurrences. This is an individual report, not a confirmed incidence rate, and does not establish whether 3.8 has the same defect. It is directly relevant to our typed intent extraction. [Report and reproduction](https://discuss.ai.google.dev/t/gemini-3-7-flash-schema-constrained-json-output-degenerates-into-repeated-0-until-maxoutputtokens-regression-vs-gemini-3-flash-preview/178681/1).
- **Early 3.8 feedback is not uniformly positive:** a developer using 3.8 high in Antigravity reports shortcuts and unsupported completion claims during ML/data work. That environment and workload differ substantially from our short, constrained conversations. [Firsthand report](https://discuss.ai.google.dev/t/gemini-3-5-3-8-flash-review-on-real-ml-and-ds-jobs/180901).
- **Independent measurements support testing it:** Artificial Analysis measures stronger agentic performance for 3.8, including a 12-point improvement over 3.7 on its cited banking tool-use evaluation. Medium reasoning scores 57 versus high's 59 on its aggregate intelligence index. High uses more tokens and costs about 40% more per benchmark task than 3.7 despite unchanged token prices. These are benchmark results, not estimates of our latency, reliability, or itinerary cost. [Artificial Analysis evaluation](https://artificialanalysis.ai/articles/gemini-3-8-flash).

The evidence supports cautious optimism, rather than a claim that developers universally prefer Gemini or that structured-output problems are solved.

## Fit with our implementation

The current `planner/agent.py` asks for a bounded `Intent`; code acquires and selects travel data. The model cannot populate the typed itinerary's prices, legs, or links. This narrower responsibility is a good fit for testing Flash. Generated explanatory prose still needs evaluation for unsupported claims.

Pydantic AI supports `GoogleModel` and `GoogleCloudProvider`, including application default credentials (ADC) and explicit project/location configuration. Our installed Pydantic AI source already recognizes 3.8 and supports EU multi-region routing. We must add the Google dependency extra, replace OpenAI-specific initialization/configuration, and adapt the durable-model tests. This has not been exercised against Google's API. [Pydantic AI Google integration](https://pydantic.dev/docs/ai/models/google/).

Cloud Run can use its attached service account through ADC, avoiding a separately provisioned LLM API key. The project still needs billing, the relevant API enabled, and authorized IAM access; Google Cloud does not eliminate organizational approval requirements. [Authentication documentation](https://pydantic.dev/docs/ai/models/google/).

**Region:** retain app infrastructure in `europe-west3` and Temporal in `gcp-europe-west3`. Configure the model separately with location `eu`: 3.8 currently lists `global`, `us`, and `eu`, not a Frankfurt-specific endpoint. EU processing does not mean Frankfurt-only processing. Explicit configuration avoids the provider's default single-region selection. [Model availability](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash), [Provider location configuration](https://pydantic.dev/docs/ai/models/google/).

**Budget:** advertised introductory pricing is $0.75 per million input tokens and $3.75 per million output tokens through 31 December 2026; standard pricing becomes $1.50/$7.50 on 1 January 2027. Budget for that change because our fixture catalog extends into January. Actual cost must include reasoning, retries, and any repeated model calls. [Official pricing announcement](https://blog.google/innovation-and-ai/models-and-research/gemini-models/3-8-flash-and-3-8-flash-cyber/).

## Proposed acceptance spike

Use recorded SearchApi evidence initially to isolate model behavior and avoid unnecessary provider charges. Compare 3.8 low and medium with repeated runs covering:

1. Initial briefs and supported revisions: budget, room/bathroom privacy, airport preferences, and combinations of constraints.
2. Unsupported requirements, ambiguous requests, and questions answered only from supplied itinerary evidence.
3. Untrusted instructions embedded in user/provider text; no invented prices, schedules, availability, or claims that an uncommitted revision succeeded.
4. Schema validation, empty/truncated responses, explicit output-token limits, bounded retries, and preservation of the last valid itinerary.
5. End-to-end latency and token cost under our existing 45-second model Activity timeout, plus durable replay and worker-restart behavior.

Record semantic correctness separately from schema validity. Choose the lowest reasoning level that meets the acceptance cases and response-time budget, then exercise live SearchApi integration. Keep the approved main plan unchanged until that evidence supports the provider decision.
