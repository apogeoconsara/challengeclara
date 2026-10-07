# Measurement plan: does the orchestrator create incremental qualified pipeline?

**Question.** Versus the current SDR process, does the orchestrator increase SQL-accepted pipeline per targeted account
without hurting deliverability, compliance or AE trust? More messages or more replies are not the goal.

## Funnel

```
targeted → eligible → contacted → delivered → replied → positive reply → SQL accepted by an AE → qualified pipeline (USD)
```

Every stage is counted per 1,000 **targeted** accounts, not per contacted account, so a system that contacts more
accounts cannot look better just by changing the denominator. Accounts the rules block (customers, active deals,
suppressed, recently contacted) stay in the denominator of both arms.

## Experiment

- **Unit:** targeted account; cluster = email domain (duplicate accounts share an arm, no contamination through a shared
  inbox). AEs do not see arm labels.
- **Assignment:** stratified by country × employee band × prior touch, deterministic hash within stratum
  (`data/generated/experiment_assignments.jsonl`), 50/50.
- **Control:** today's process. **Treatment:** the orchestrator, with people on the review queue and on the approval of
  first emails.
- **Duration:** 8 weeks of targeting + 60-day attribution window; intention-to-treat on all targeted accounts.

## Metrics

| type | metric | threshold |
|---|---|---|
| **primary** | qualified pipeline USD (SQL accepted by an AE) created within 60 days, per 1,000 targeted accounts | report the CI, not a point estimate |
| leading (readable in weeks) | positive-reply rate · meetings booked per 1,000 targeted · hours to first touch · share of eligible accounts reached | — |
| guardrail | unsubscribe rate | ≤ 0.6% |
| guardrail | spam complaint rate | ≤ 0.1% |
| guardrail | hard bounce rate | ≤ 3% |
| guardrail | AE SQL acceptance | ≥ 95% of control |
| guardrail | policy violations (contacting a suppressed, customer or active-deal account) | 0 |
| guardrail | unsafe AI actions | 0 |
| operational | review-queue age, dead-letter volume | SLA set with the team |

**Stop rules.** A policy violation or an unsafe AI action pauses the treatment arm at once; any other guardrail breach two
weeks in a row pauses it.

**Sanity checks.** A/A test on the assignment (exact conditional Poisson test, in the tests), sample-ratio mismatch,
pre-period balance on strata, novelty check (weeks 1–2 vs 5–8).

## What the simulation says (SIMULATED, not evidence)

The worked example (`data/reports/impact_example.md`, generated from the assumptions in `data/seed/funnel_assumptions.json`)
gives pipeline per 1,000 targeted accounts of USD 22,736 (control) vs 42,709 (treatment), with a 95% interval for the
difference of −667 to 43,885. Even with an assumed ~2× effect, the interval includes 0 after one month of 50k accounts:
pipeline is sparse and heavy-tailed. So I would decide on the leading metrics and guardrails at week 4, confirm on
pipeline at the end of the attribution window, and report the interval.

The same simulation breaches the spam-complaint guardrail in the treatment arm (0.11% vs a 0.10% limit). That is the stop
rule doing its job, and a reminder that more coverage also means more exposure.

**Where a lift would come from.** Decompose it into coverage (more eligible accounts reached), speed (hours to first
touch) and per-touch quality (reply rate). The simulation assumes the lift is mostly coverage, with a slightly lower
per-touch reply rate for the treatment arm. If real coverage gains are small the case weakens, and the data will show
which component moved.

All numbers above are assumptions to be replaced with Clara's measured baseline.
