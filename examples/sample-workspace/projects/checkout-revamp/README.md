---
title: Checkout revamp
owner: alex-morgan
status: active
sensitivity: internal
last_reviewed: 2026-11-10
---

<!-- generated -->
## Current state

- **RAG**: amber since 2026-11-04 (entry `STA-004`)
- **Latest status** (`STA-004`, 2026-11-10): at-risk. Holding the 50% rollout until the tax quotes land. Early read on the 10% cohort: upgrade rate
- **Open risks** (RSK): 1; open dependencies/blockers (DEP): 1
  - RSK-002: Payment provider sandbox went down twice this week; load testing for the payment step is b (due 2026-11-12)
- **Next milestones**: MS-002 (at-risk, 2026-12-02); MS-003 (open, 2027-01-15)
- **Decisions awaiting confirmation**: 1: DEC-checkout-revamp-002
- **Last activity**: 2026-11-10

<!-- /generated -->

# Checkout revamp

<!-- human -->
> Self-serve plan upgrades for Fernhill trials and small teams: a new plan picker, a one-page
> payment step and in-app invoices. Today 4.1% of trials upgrade without talking to sales; the
> goal is 6% by the end of Q1 without hurting checkout completion.

## Goal

Trial-to-paid self-serve upgrade at 6% by 2027-03-31, checkout completion at or above 92%.

## Links

| Resource | Where |
|---|---|
| Channel | `#proj-checkout` |
| PRD | `[[conf-2026-10-27-checkout-revamp-prd]]` (Confluence space PROD) |
| Weekly sync | Wednesdays, summaries under `raw/meetings/` |
<!-- /human -->

## How this folder works

- Facet logs (`status.md`, `risks.md`, `milestones.md`, `resources.md`, `hypotheses.md`) are
  append-only. Add entries with `brain kb append`, or by hand in the same grammar
  (`system/schema/entry-grammar.md`).
- `teams.md` lists the people on the project; it drives the trust tier of every source.
- `decisions/` holds one file per decision. `rollups/` holds monthly rollups.
- The block between the `generated` markers is rewritten by `brain kb index`. Everything between
  `human` fences is Alex's and is never rewritten by an agent.
