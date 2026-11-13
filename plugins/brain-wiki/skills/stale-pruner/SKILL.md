---
name: stale-pruner
description: Find log entries and decisions that look abandoned (still open or proposed long after their last mention) and turn each into a proposal for the owner. Never edits, deletes or closes anything itself. Use weekly, from the system review, or on demand - "what has gone stale in checkout-revamp?".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
model: sonnet
---

# Stale pruner: propose, never prune

Logs are append-only, so nothing here removes a line. The skill finds entries whose current state is still live but untouched, asks whether each is dead or just quiet, and records the question as a proposal. A blocker nobody mentions can still be silently blocking, so only the owner decides.

## Steps

1. **Find candidates.** One command:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/find_stale.py --days 21
   ```
   Add `--project <slug>` to limit it. A candidate is an ID whose latest entry is live (open, at-risk, off-track, proposed, slipped) and older than `--days`, or a decision still `proposed` after that long. Fenced `<!-- human -->` blocks are never read.
2. **Judge.** For each candidate, check whether anything newer touches it: `brain kb query "select id, kind, path from fts where fts match '<id or key phrase>' limit 5"`, and the project's recent summaries. Drop a candidate that something recent still mentions.
3. **Propose.** For each remaining candidate, skip if an open proposal with a similar title exists (`brain kb query "select id, title from proposals where state='open'"`), otherwise:
   ```bash
   brain kb propose --title "Stale? <project>/<ID>: <short subject>" --source <ID> --body "Last touched <date> (<age> days). Close, keep, or re-date?"
   ```
   Confidential entries: abstract the subject, no names or amounts.
4. **If the owner accepts a proposal to close**, append a new entry with the same ID and state `closed` through the `wiki-update` append payload (`by: ai`, `source` the proposal id). Never edit the old line. `brain kb confirm <PRP-id> --reject` keeps the entry live and teaches the next run.
5. **Return** a short list: candidates found, proposals raised, candidates dropped as recently touched.

## Rules

- Propose only. No edits to `projects/**`, `people/**` or `topics/**` from this skill.
- Entries in `<!-- human -->` fences are the owner's; they are skipped by the script and never proposed on.
- Rolling-window trimming of generated views (digests, rollups) is not done here: they are regenerated.
