---
id: PRP-005
audience: system
date: 2026-11-12
state: open
title: "Check current entries before opening a new risk ID"
source: mtg-2026-11-05-partner-api-sync
by: ai
---

# Check current entries before opening a new risk ID

Twice in two weeks the same risk was logged under two IDs (once from Slack, once from the
meeting summary). Proposal: the wiki-update step queries `current_entries` for the project and
passes an existing `id` to `brain kb append` when the body matches an open risk.

Accept with `brain kb confirm PRP-005`, or reject with `--reject`.
