---
title: Partner API
owner: alex-morgan
status: active
sensitivity: internal
last_reviewed: 2026-11-07
---

<!-- generated -->
## Current state

- **RAG**: green since 2026-10-15 (entry `STA-002`)
- **Latest status** (`STA-002`, 2026-11-05): on-track. Booking endpoint in review. Rate limits agreed with Riley: 600 requests a minute per partner for launch.
- **Open risks** (RSK): 2; open dependencies/blockers (DEP): 1
  - RSK-002: Second design partner has not made a sandbox call in ten days; their launch date may slip.
  - RSK-001: Webhook retries are not idempotent; a partner could double-book on a retry. (due 2026-11-08)
- **Next milestones**: MS-001 (open, 2026-11-28); MS-002 (open, 2027-01-31)
- **Decisions awaiting confirmation**: none
- **Last activity**: 2026-11-05

<!-- /generated -->

# Partner API

<!-- human -->
> The public REST API that calendar and HR-system partners use to read availability and book
> slots in Fernhill. Two design partners are in the sandbox; the goal is both live by January
> with a self-serve onboarding checklist instead of a kickoff call each.

## Goal

Two partners live in production by 2027-01-31; median partner time-to-first-booking under five days.

## Links

| Resource | Where |
|---|---|
| Channel | `#partner-api` |
| Sync | Thursdays, summaries under `raw/meetings/` |
| Onboarding idea | `[[note-2026-10-29-partner-onboarding-checklist-idea]]` |
<!-- /human -->

## How this folder works

Facet logs are append-only (`brain kb append`); `teams.md` drives trust; `decisions/` holds one
file per decision; the `generated` block is rewritten by `brain kb index`.
