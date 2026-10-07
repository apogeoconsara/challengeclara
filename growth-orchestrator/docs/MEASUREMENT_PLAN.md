# Measurement plan: does the orchestrator create incremental qualified pipeline?

**Question.** Versus the current SDR process, does the orchestrator increase SQL-accepted pipeline per targeted account
without hurting deliverability, compliance or AE trust?

**Design.** Randomized controlled experiment, intention-to-treat.
- Unit: targeted account; cluster = email domain (duplicate accounts share an arm, no contamination through a shared inbox).
- Assignment: stratified by country × employee band × prior touch, deterministic hash within stratum
  (`data/generated/experiment_assignments.jsonl`), 50/50.
- Control: today's process. Treatment: the orchestrator with humans on the review queue.
- Duration: 8 weeks of targeting + 60-day attribution window.

**Primary metric.** Qualified pipeline USD (SQL accepted by an AE) created within 60 days, per 1,000 targeted accounts.

**Leading metrics** (readable in weeks): positive-reply rate, meetings booked per 1,000 targeted, hours to first touch,
coverage of eligible accounts.

**Guardrails** (any breach pauses the treatment arm): unsubscribe ≤ 0.6%, spam complaints ≤ 0.1%, hard bounce ≤ 3%,
AE SQL acceptance ≥ 95% of control, **0 policy violations** (contacting suppressed/customer/active-deal accounts),
**0 unsafe AI actions**; plus operational ones: review-queue SLA, dead-letter volume.

**Sanity checks.** A/A test on the assignment (exact conditional Poisson test, in the tests), sample-ratio mismatch,
pre-period balance on strata.

**Power.** The worked example (`data/reports/impact_example.md`, simulated from `funnel_assumptions.json`) shows that even
an assumed ~2× effect on pipeline gives a 95% CI that includes 0 with one month of 50k accounts — pipeline is sparse and
heavy-tailed. So: decide on the leading metric + guardrails at week 4, confirm on pipeline at the end of the
attribution window, and report the CI, not a point estimate.

**Attribution of the lift.** Decompose into coverage (more eligible accounts reached), speed (hours to first touch) and
per-touch quality (reply rate). The simulation assumes the lift is mostly coverage; if real coverage gains are small the
case weakens, and the data will show which component moved.

**Not evidence.** All numbers in the worked example are assumptions to be replaced with Clara's measured baseline.
