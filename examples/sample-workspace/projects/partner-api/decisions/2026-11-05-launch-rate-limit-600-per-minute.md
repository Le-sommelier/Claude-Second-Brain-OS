---
id: DEC-partner-api-001
date: 2026-11-05
status: accepted
by: ai-confirmed
trust: high
source: mtg-2026-11-05-partner-api-sync
owner: riley-chen
origin: ingest
title: Launch rate limit of 600 requests a minute per partner
---

# Launch rate limit of 600 requests a minute per partner

## Context

Partners asked for headroom for nightly syncs; infrastructure wanted a ceiling it could defend.

## Decision

600 requests a minute per partner at launch, reviewed after the first month of production traffic.

## Consequences

Sam adds per-partner rate-limit headers; the docs page lists the limit.
