# Decision log

The four questions the challenge asks, then the smaller calls that shaped the build.

## Something I deliberately did not build

**Real sending, and any real integration.** Outreach goes to a mock ledger only: the engine's executor has no email
client, the live Netlify function has no email code, and a test fails if any module imports an SMTP/HTTP client other
than the LLM client. Real CRM / enrichment / calendar connectors are mocks with every failure mode the contracts describe
(`data/seed/mock_api_contracts.json`). Sending real email to synthetic people would prove nothing and risk a lot;
the interesting parts (eligibility, idempotency, reconciliation, AI validation) are fully exercised against the mocks.

Also not built: a queue/worker split (events are processed synchronously, one transaction each), multi-channel
sequences (email only), and a production approval queue. The site's Approval Queue page demonstrates the step on a batch of prepared emails, but its decisions live only in the reviewer's browser: no server-side queue, no reviewer identity, and no send path behind it.

## Where I deliberately did not use AI

- **Eligibility, suppression, routing, timing, caps.** These are policy and compliance; they must be explainable, testable
  and identical every time. `orchestrator/rules.py` reproduces the independent truth on 500/500 sample accounts.
- **Explicit opt-outs.** Unsubscribe events, hard bounces and an opt-out regex on replies are handled deterministically;
  when the model labels an opt-out as anything else, guard G001 overrides it to `suppress`. Opt-out is honoured even when
  the model is unavailable.
- **Which facts may be used for personalization.** `usable_facts` is a rule (verified, ≤ 1 year old, names this company,
  consistent with CRM headcount). The model only rephrases one of them into the approved template.
- **Choosing the action.** The model returns a label and evidence; `LABEL_ACTION` plus state-aware overrides choose the
  action. The model's `suggested_action` is recorded and ignored (V010 when it disagrees).

## The most important tradeoff

**Safety over automation rate.** Anything uncertain goes to a human: low confidence (< 0.75), output that fails
validation twice, a quote not found in the reply, an injection attempt, contradictory enrichment, an uncertain external
outcome that cannot be reconciled, a late fact that arrives after an email went out. This lowers the share of replies
handled automatically and adds review load, but the costly errors in outbound (emailing someone who opted out, a customer
or an active deal; double-sending; promising things legal has not approved) become structurally hard to make.
The same tradeoff shows in personalization: no usable fact → the generic approved template, never invented specifics.

## The biggest production risk

**A confident, well-formed, wrong interpretation.** Validation catches malformed, unsupported, invented and injected
outputs (219/220 recorded failure modes), but a reply that is genuinely ambiguous can still get a plausible label with
a real quote and high confidence (`EV-R-AMB-03:wrong_but_valid_overconfident` passes validation and would hand an
unclear lead to an AE). Mitigations: label-level human review at launch (100% of AI-driven handoffs), the live eval
suite as a release gate on every prompt/model change, per-label precision monitoring from reviewer corrections, and
an autonomy rollback switch. See [AI.md](AI.md#before-giving-the-ai-more-autonomy).

Second risk: **deliverability and compliance drift** — caps, windows and footers are assumptions in
`send_policy.json` and must be replaced with Clara's real rules before anything is sent.

## Smaller decisions

| decision | why | cost |
|---|---|---|
| Python stdlib + SQLite, no framework | runs anywhere in seconds, reviewers read every line | no async, no migrations tool |
| Three-way dedupe (delivery id, idempotency key, content hash) | webhook retries, replays under new ids and CRM mirrors are different failures | content hash must be defined per event type |
| Idempotency key per business effect (`send:{account}:{contact}:{step}`) | exactly-once survives retries, replays and uncertain outcomes | a legitimately repeated email needs a new step |
| Look up by key before any retry after a timeout / unknown status | a blind retry is how double-sends happen | one extra call on the failure path |
| Re-decide before sending a scheduled email | facts can change between decision and send window | one rules evaluation per send |
| Lateness = a fact older than something already acted on | out-of-order arrival is normal; earlier decisions need reconciling | flags some benign cases to humans |
| Forced tool call + strict schema, one retry on invalid structure only | structure errors are cheap to retry; semantic errors are not | up to 2 model calls per reply |
| Offline fixture for recorded runs, real model for live panel/evals | recorded demos must be deterministic; live results must be real | two modes, always labelled |
| JS port of validators for the web, parity-tested | the deployed page must validate exactly like the engine | two implementations to keep in sync (tests enforce it) |
| Account priority score (size, payment-pain hypothesis, signals) next to the rules, not inside them | the rules decide eligibility; among eligible accounts the score picks the track: tiers A and B get a personal first email, tier C goes to nurture (no first email, no model call, audited as `nurture_enrolled` with the score version) | nurture only records the enrolment: no follow-up content exists yet; weights are assumptions pending review |
| Scoring versions (`versions` + `active_version` in `scoring_policy.json`) and a compare view on the page | iterating on the weights must stay traceable: every logged score carries its version, and any two versions can be compared on the same data to see who changes group | versions edited in the browser are only saved locally until someone commits them |
| Audience check as a pass / fail / unknown checklist, fail-closed | missing data must read as "enrich first", never "assume fine"; reviewers see why an account is blocked | a second description of the rules, kept honest by a test against the engine (590 accounts) |
| Hours saved shown as an estimate from editable per-task minutes (`data/seed/time_assumptions.json`), counts from the engine's decisions on all 50,000 accounts | the value of automating is time, but the minutes are not measured; showing the assumptions keeps the number honest | a headline figure that moves when someone changes a minute |
| Page leads with plain-language views (Command Center, Live Demo, Decisions, Approval Queue, AI & Safety, Operations): seven tabs, each answering one question, with related views as sections inside a tab; the system diagram, flows and scenarios sit under "System" (Architecture) | the audience is people who run growth operations, not people who read audit logs | two descriptions of the same rules (everyday text in `orchestrator/plain.py`, tested to cover every reason code) |
| "Live Demo": curated end-to-end runs of the real engine, split into seven stages, plus a replay where a simulated model mistake meets the opt-out guard | a reviewer should see event, state, rules, model, validator, action and audit in one minute; the replay is labelled simulated because a strong model usually reads that sentence correctly, and a live button asks the real model | recorded runs, not live ones, except the live button |
| Operations page from the full 50k event stream through the engine (offline fixture model) | operating metrics (automation, review, failure, duplicates, dead letters, cost) must come from a run, not from a slide | AI failure and guard counts reflect the safety layer on fixture answers, not a live model; thresholds and cost per call are assumptions |
| The page separates automatic decision and preparation from sending: first outreach emails are "prepared automatically, pending human approval before sending" | the system automates the judgement and the drafting; an action that reaches a customer stays a human-approved step | this prototype has no send path and no approval queue: the approval step is a design rule, not a built feature (see PRODUCTION.md) |
| Approval Queue page: a batch of 200 prepared first emails drawn from the 5,702 (tiers A and B), with approve / reject (reason), bulk approve, an override-rate metric and a decision log | makes the human-approval rule visible and gives the reviewer override rate a place to come from | decisions live only in the reviewer's browser and nothing is sent: it demonstrates the step, it is not the production queue |
| Scoring changes are versions, compared before adoption: `compare-scoring` runs the whole 50k event stream through the real engine once per version and reports who changes group, first emails prepared, nurture enrolments, AI calls and estimated cost; the page shows it with a change log | a change to the weights must be explainable in operational terms, and decisions already taken must stay traceable to the version that produced them (the audit log records it) | the second version in `scoring_policy.json` is an illustrative proposal, not adopted; effects are on synthetic data and say nothing about real pipeline, which only the experiment can show |

