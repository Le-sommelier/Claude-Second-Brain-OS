---
id: DEC-checkout-revamp-001
date: 2026-10-21
status: accepted
by: human
source: owner
owner: alex-morgan
supersedes: null
title: Ship the plan picker behind a percentage flag
---

# Ship the plan picker behind a percentage flag

## Context

The plan picker changes the first screen every trial sees. Finance wanted proof before a full
rollout; engineering wanted to avoid a long-lived branch.

## Options

- Full launch after a two-week internal beta.
- Percentage rollout: 10%, then 50%, then 100%, with a holdout.

## Decision

Percentage rollout with a 10% holdout kept until the Q1 read-out.

## Consequences

Taylor owns the cohort dashboard. Each step needs checkout completion at or above 92%.
