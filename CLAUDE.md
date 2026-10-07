# Working notes for Claude

Talk to the owner in Spanish. The project, code, docs and site are in English.

## What this is

Clara challenge: a Growth Orchestration System vertical slice (`event → state → decision → AI/rules → action → audit`),
sized for 50,000 companies a month. Everything lives in `growth-orchestrator/`; the site is `public/` plus
`netlify/functions/`, published by Netlify from `main` (https://growth-orchestration-system.netlify.app).
Start with `README.md`, `growth-orchestrator/README.md` and `growth-orchestrator/docs/DECISION_LOG.md`.

## Rules that are not negotiable

1. Never send an email. Email is a simulated log; the Netlify function has no email code. Inside the engine, no outreach email
   (first or follow-up) reaches even that log without a named person's `approve()`: drafts are held as `pending_approval`, and the
   executor refuses unapproved sends. Never make `AutoApprover` the engine's default; it exists only for tests and the scenario
   runs that check what happens after approval, and it must stay labelled as a harness.
2. Synthetic data only. Real companies must not come back (a test checks this with hash fingerprints; never list real names).
3. The API key never goes in a file or a commit: only an environment variable on the server or in the owner's terminal.
4. Do not invent results. If something was not run against the real model, say so. Recorded, simulated and live are always labelled.
5. Provenance: the reply seeds, the 89 golden scenarios, the 220 recorded outputs and the site text were drafted with an
   AI assistant, and the owner's human review is pending. Never say they were written by hand.
6. Docs speak in the owner's voice only to describe intentions; they must not read as written by Claude.
7. The model proposes, deterministic code decides: AI labels and extracts; rules choose the action, the AE, eligibility and sending.
8. Ask before anything destructive or outward-facing: deleting, force-push, publishing, touching Netlify, or touching the old
   repo (`apogeoconsara/portafolioclara`) and the old site.

## How to work

- Branch from `main`, open a PR to `main`, and let the owner merge (merging publishes the site). Never force-push.
- One PR per batch of related work. While a PR is open, keep adding to it instead of opening another; open a new one only when the
  owner asks for it. The owner wants the GitHub account clean: no PR per interaction, and no merge until the owner says so.
  Agents cannot delete branches here, so name the merged branches the owner should delete.
- Before building something big, give the route in a few lines and wait for approval. No new tabs for the sake of it.
- Style: calm and friendly, Growth Ops language (not technical), a small type scale, compact cards. Figures that are
  simulated or rest on assumptions are always marked as such.
- Every change leaves the tests green and the page JSON regenerated. Test page changes in a real browser (Chromium with Playwright).
- *.netlify.app cannot be opened from the cloud environment: check a deploy through the Netlify API, or ask the owner.
- Say honestly what is real, what is simulated and what could not be verified, and say which decision you need from the owner.

## Commands (from `growth-orchestrator/`)

```bash
python3 -m generator all --seed 42 --n 50000                 # the 50k world, ~1.5 min, 390 MB, not in git
python3 -m unittest discover -s tests -t .                   # 168 tests, ~4 min; 5 skip without the 50k world
python3 -m orchestrator export-web                           # regenerate the page data
python3 -m orchestrator export-overview                      # ~3.5 min; rewrites overview, operations, approvals, measurement, scoring_compare
python3 -m orchestrator compare-scoring v1 v2 [--write-web]
```

After changing the engine or the data, regenerate the page JSON: tests fail when it is stale. The browser test
(`tests/js/ui_persistence.test.mjs`) needs playwright-core and Chromium and skips itself without them; CI sets
`REQUIRE_BROWSER=1` so there it must run.

## Terms (keep them consistent everywhere: page, docs, code comments)

- **Outreach email**: any email the engine drafts for a `contact` decision. It is step 1 (a **first email**) or step 2 to 4
  (a **follow-up email**), depending on how many automated emails the company already got. Of the 5,897 prepared in the
  50k world, 3,161 are first emails and 2,736 are follow-ups. Never call all of them "first emails".
- **Nurture**: the slow track for eligible but weaker-fit companies. It sends no email and calls no model; it only records the
  enrolment. Do not call it a "follow-up", which is reserved for step 2 to 4 emails.
- Only steps 1 and 3 have an opening line the AI may write (and only when a verified fact exists); steps 2 and 4 are fixed text.

## Open items (owner's)

The human review of AI-drafted data and text (start with the demo flows G080, G040-42, G070/72/75, G064-67, G063/66,
G047-48); the presentation; what to do with the old repo and site. The old API keys (Customer.io, OpenAI, n8n) are revoked.
The Anthropic account holds about USD 5 of credit, which is the owner's spend cap: keep auto-reload off and check the
balance before presenting, because the live demo stops if it reaches 0. The first live eval (2026-10-07) is stored in
`evals/results/`; it must be re-run after any prompt, model or `EV-G0xx` change.

Open policy decision (not to be changed without the owner): the rules put AE ownership before the 90-day closed-lost cooldown
(see `docs/DECISION_LOG.md`). It would be validated with Sales/Growth in production.
