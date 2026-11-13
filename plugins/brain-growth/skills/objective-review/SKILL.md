---
name: objective-review
description: Mid-period check-in on your objectives. Measures progress on each objective against evidence mined from your work, flags the ones with no proof yet, and writes the check-in notes with your agreement. Use for "check my objectives", "mid-year objective review", "how am I tracking on my goals", "prepare my check-in with my manager".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/../growth-signals/scripts/*) Bash(brain *) Read Edit
---

# objective-review

Facts first, judgement second. The script counts; you interpret and ask.
Model: strongest available when talking to the owner; the counting is deterministic.

**Reads:** the newest `growth/objectives/*.md` (or the one named), the tracker, pending candidates.
**Writes:** appends to that file's `## Check-in notes` section, only after the owner agrees the wording, and ticks `- [x]`
on boxes the owner confirms are done. Nothing else. Confidential.

## Steps

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/objective_progress.py` (add `--file growth/objectives/2027-H1.md` for a specific one).
   Per objective you get: boxes done and total, open boxes, tagged criteria, promoted evidence, pending candidates since the set date,
   and a signal: `on-track`, `thin`, `no-evidence`, `too-early` or `no-tag`.
2. **If pending candidates exist,** suggest triaging them first (`growth-signals`, triage and promote), then re-run. Evidence the owner
   has not accepted is not counted as progress.
3. **Walk each objective** in one short exchange: what the numbers say, what the owner thinks is true that the evidence does not show,
   what is blocking. Do not argue with a signal, ask what is missing from the record. A `no-tag` objective gets criteria suggested from the framework.
4. **Decide per objective:** continue, re-scope (cut a box, move a date), or drop. Re-scoping is allowed and healthy; say so.
5. **Draft the check-in notes** in 4 to 6 lines per objective: status, evidence, next step, ask of the manager. Show the draft. On the owner's yes,
   append it under `## Check-in notes` as `### Check-in YYYY-MM-DD`, and tick the confirmed boxes.
6. If the owner wants a shareable summary for the manager, produce it in chat as a draft, paraphrased, with no review quotes. Do not post it anywhere.

## Failure modes

- "no objectives file": run the `objectives` skill first.
- Every objective says `no-evidence`: the miner may not be running, or objectives are untagged. Check `run/run-log.json` and the criteria tags.
- `elapsed_fraction` looks wrong: the file's `set:` date is missing or malformed.
