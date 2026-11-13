---
id: mtg-2026-11-05-partner-api-sync
source_type: meeting
title: "Partner API sync"
date: 2026-11-05
week: "2026-W45"
attendees: [alex-morgan, sam-patel, riley-chen]
attendance: attended
project: partner-api
meeting_type: project-sync
signal_quality: medium
tags: [partner-api]
sensitivity: internal
source_transcript: "raw/meetings/2026/2026-W45/mtg-2026-11-05-partner-api-sync.md"
wiki_processed: false
todo_processed: false
---

# Partner API sync — 2026-11-05

## Purpose
Review the v2 API design with the director, settle rate limits and webhook retries, and confirm the beta partner list.

## Key Updates
- The v2 design doc is complete; open questions are limited to rate limits and webhook retry policy (Sam).
- Three beta partners confirmed; the fourth is waiting on legal review of the data-sharing addendum.
- Developer docs are about 70% written; the quickstart is the missing piece.

## Decisions
- Default rate limit of 600 requests per minute per partner, with a documented path to raise it. Decided by Riley.
- Webhooks retry for 24 hours with exponential backoff, then land in a dead-letter queue partners can replay.

## Actions
- Alex: send the beta partner list and the addendum status to Riley (due 2026-11-09)
- Sam: write the rate-limit and retry sections of the design doc (due 2026-11-11)
- Sam: draft the quickstart for the developer docs (due 2026-11-18)
- Riley: chase legal on the addendum for the fourth partner

## Risks & Dependencies
- The fourth beta partner may slip past the November window if legal review takes longer than two weeks.
- The dead-letter queue needs infrastructure work that is not yet scheduled.

## Leadership Feedback
Riley asked that the beta communicate a stable v2 contract, and that any rate-limit change after launch go through a deprecation notice.

---

## Source transcript

[[mtg-2026-11-05-partner-api-sync]]
