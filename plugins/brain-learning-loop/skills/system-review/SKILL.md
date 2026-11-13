---
name: system-review
description: Weekly audit of how the workspace is learning. Surfaces patterns and hypotheses that crossed the three-session promotion threshold, items to demote, stale entries, drift, proposals awaiting an answer and vault health, as one 2-minute report. Use for the Friday scheduled run, or when the owner asks "what should I promote to my rules" or "review the system".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
model: sonnet
---

# system-review

Closes the learning loop. The nightly `consolidate` skill captures learnings, hypotheses and
proposals; this skill counts the evidence and puts the decisions in front of the owner. It reports,
and it never acts.

## What the report contains

1. **Promotion candidates.** Ledger items (patterns and hypotheses) still open that are supported by
   at least three **distinct sessions** (`promotion_min_sessions`). The owner decides: promote to
   `RULES.md`, turn into a project decision, keep watching, or reject.
2. **Demotion candidates.** Open items refuted by two or more sessions and by more than support them.
3. **Stale items.** Ledger items unseen for 30 days, open project entries older than 60 days,
   projects with no entry in 30 days.
4. **MEMORY summary.** The last 7 days of `MEMORY.md` headlines, to spot cross-session patterns by eye.
5. **Proposals.** Tally by state, and open ones older than two weeks, plus AI-written project
   entries nobody confirmed.
6. **Drift.** Project folders missing their standard files.
7. **Vault health.** Broken wikilinks, orphan pages, oversized pages across `projects/`, `topics/`, `people/`.
8. **Workspace health.** The output of `brain doctor` (config, paths, modules, connectors, tasks).
9. **Scheduled-task drift** (the only part you do by hand, see step 4).

The thresholds live in `references/review-config.json`. Edit them there; the script validates the file.

## Procedure

1. Run the script (current ISO week by default; add `--week 2026-W46` to redo one):
   `python3 ${CLAUDE_SKILL_DIR}/scripts/run_system_review.py`
   It writes `system/reviews/_system-review-YYYY-Www.md` and prints the counts. If it fails, report the
   reason and stop. Do not retry blindly.
2. Read the report. Check `brain kb query "select id, audience, state, title from proposals order by id"`
   before suggesting anything new, so a rejected idea stays rejected.
3. Turn each recommended action that is not already a proposal into one, at most five:
   `brain kb propose --title "<action>" --source <ledger id or entry id> --audience system --body "<why, 1-3 lines>"`
   Stale open risks are candidates for a "propose closing" proposal, never for closing them yourself.
4. Scheduled-task drift: call `list_scheduled_tasks` and compare with the `scheduled` entries of the
   modules enabled in `.claude/brain.json`. Flag anything running but undeclared, declared but not
   registered, or registered but disabled. Add the findings to your summary (do not edit the report).

## What never happens here

- No promotion or demotion. This skill never edits `RULES.md`, `MEMORY.md`, a facet log or the ledger,
  and never runs `ledger.py set-status`. Only the owner promotes.
- No external calls. The scan is local. No Slack, Confluence, Jira.
- No confidential content in the report. Files matching the confidential globs or marked
  `sensitivity: confidential` are not read.

## Limits (deliberate)

It counts signals; it cannot tell whether a hypothesis is true. It proposes; it cannot decide.
It reviews one workspace.

## Report to the owner (at most 8 lines)

Path of the report, then the counts: promotion, demotion, stale, drift, open proposals; then the two
most actionable findings. Flag anything that needs attention before Monday.
