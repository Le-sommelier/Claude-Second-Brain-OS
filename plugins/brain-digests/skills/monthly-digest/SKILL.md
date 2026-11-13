---
name: monthly-digest
description: Generate the per-project monthly rollups (projects/<slug>/rollups/YYYY-MM.md) and the monthly digest (digests/monthly/YYYY-MM.md) deterministically from the project logs. No model in the loop. Trigger on "monthly digest", "monthly rollup", or the scheduled task on the 1st.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
model: haiku
---

# Monthly digest: deterministic rollups

Lists what was logged in a month, with IDs, so any line can be verified with `brain kb show <id>`. Pure file parsing: a rollup never states a fact that is not in a log.

**Reads:** `projects/<slug>/{status,risks,milestones,resources,hypotheses}.md`, `projects/<slug>/decisions/*.md`, `projects/<slug>/README.md` (title).
**Writes:** `projects/<slug>/rollups/YYYY-MM.md` per project with activity, and `digests/monthly/YYYY-MM.md`. Only files carrying the generated marker are replaced; a hand-written file at the same path is skipped and counted. Unchanged content is not rewritten.

## Steps

1. **Run.** Default window is the previous and current month:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/rollup.py
   ```
   Other forms: `--month 2026-10` for one month, `--backfill` for every month that has data, `--dry-run` to preview, `--today YYYY-MM-DD` to fix the clock.
2. **Return** the script's counts (`written`, `unchanged`, `skipped_handwritten`) and the output paths. If the owner wants a narrative, read `digests/monthly/YYYY-MM.md` and write it in chat only; do not edit the generated file.

## Confidential entries

An entry or decision tagged `sensitivity: confidential` is listed by id, date and state with its body replaced by "(confidential, see source)". The rollup never carries names, amounts or quotes from it.

## Failure modes

- No `projects/` folder or no activity in the window: success with zero counts.
- A malformed log line is ignored by this reader; `brain kb build` is the validator and reports file and line.
