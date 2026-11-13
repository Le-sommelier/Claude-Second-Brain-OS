---
name: consolidate
description: Nightly self-learning pass. Reads the day's Claude Code session transcripts for this workspace and turns real learnings into MEMORY.md entries, tracked hypotheses with evidence counts, and improvement proposals (PRP files). Use for the scheduled nightly run, or when the owner says "consolidate today's sessions" or "what did we learn this week".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write Edit
model: sonnet
---

# consolidate

## Why this exists

A learning loop that depends on the agent remembering to append to `MEMORY.md` at the end of a
session starves: sessions rarely end cleanly. This skill makes capture deterministic. Claude Code
always writes a transcript, so a nightly job reads those transcripts and extracts what is worth
keeping. No hook has to fire.

It produces three kinds of output, each with its own bar and its own owner of the write:

| Output | Where | Written by |
|---|---|---|
| Learnings (decided, rejected, pattern, gap) | top of `MEMORY.md`, newest first | you, with Edit |
| Hypotheses and patterns with an evidence count | `system/learning/ledger.json` (+ generated `hypotheses.md`) | `ledger.py`, from your payload |
| Improvement proposals | `inbox/proposals/PRP-NNN-*.md` | `brain kb propose` |

It never edits `RULES.md`. Promotion is the owner's call, surfaced weekly by the `system-review` skill.

## The bar

`MEMORY.md` is signal, not a session log. **A routine day produces no entry: silence is information.**
Write a MEMORY entry only when a session shows one of:

- a **decision** about how the workspace, a project or the system should work;
- a **rejected approach** and why, so it is not retried;
- a **pattern that fired correctly** (a candidate for `RULES.md` once seen in three distinct sessions);
- a **bug or gap** in a skill, script or hook, and how it was resolved.

Do not write entries for routine ingest or digest runs, pure Q&A, or anything another skill already
captures (meeting summaries, todos, wiki updates).

### Hypotheses (a lower bar, tracked separately)

A **hypothesis** is something that might be true about how the owner works or what the system
should do, and that one session hints at but does not prove. Example: "the owner rewrites every
AI-drafted stakeholder message by hand, so drafts should be shorter". Hypotheses are cheap to
record and expensive to promote: they live in the ledger with a count of **distinct sessions**
that support or refute them, and nothing happens until the weekly review sees enough evidence.

Record an observation when a session shows behaviour that supports or refutes an existing
hypothesis or pattern, or suggests a new one. Never invent evidence. One session counts once,
however long it ran.

### Improvements (proposals)

An **improvement** is a concrete change to a skill, rule, hook or template, backed by evidence from
at least one session (for example "the same manual step was repeated in three sessions, so
script it"). Propose at most **three per night**. Each one must name its evidence (a session
prefix or a ledger id) and must not repeat an open or rejected proposal.

## Procedure

1. **Extract.** One command, no pipes:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/extract_sessions.py`
   The JSON gives `input_file`, `sessions`, `session_ids` and `proposed_watermark`. For a backfill add
   `--since 2026-11-01T00:00:00Z`. If it fails, report the reason and stop. Do not hand-roll extraction.

2. **Read** `input_file`. Each `### Session` block is the opening ask, the steering turns and the final
   assistant note. That is enough to judge intent and outcome. A block marked "content withheld" touched
   a confidential area: do not infer or quote anything from it.

3. **Judge** each session against the bar. Most days zero to three sessions clear it. If nothing
   clears any bar, skip to step 7 and say "routine day, no entry" in your report.

4. **MEMORY.md.** Insert one dated block above the first existing `## ` entry (newest first):

   ```
   ## YYYY-MM-DD - <topic>

   - **Decided:** ...
   - **Rejected:** ... (why)
   - **Pattern:** ... (candidate for RULES.md if seen in 3 sessions)
   - **Gap:** ... (what was found, how it was resolved)
   _(auto-consolidated)_
   ```

   Group related sessions under one topic. Apply the confidentiality rules: never quote or detail
   confidential content, abstract it ("a leadership-channel discussion about sequencing").

5. **Hypotheses and patterns.**
   1. `python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py list` to see existing ids, so evidence attaches to
      the right item instead of creating a duplicate.
   2. Write the observations payload with the Write tool to
      `system/run/payloads/learning-observations-YYYY-MM-DD.json` (shape in the `ledger.py` docstring).
      Statements are one sentence, free of names and confidential detail.
   3. `python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py observe --payload system/run/payloads/learning-observations-YYYY-MM-DD.json`
      Copy `crossed` (items that just reached three supporting sessions) into your report.
   Validation errors write nothing: fix the payload and retry once.

6. **Improvements.**
   1. Check history: `brain kb query "select id, state, title from proposals order by id"`.
   2. For each new improvement, one command:
      `brain kb propose --title "<imperative, specific>" --source <session prefix or ledger id> --audience system --body "<why, in 1-3 lines>"`
      Use `--audience owner` for a clean-up or decision only the owner can make.

7. **Session records.** Write `{"<8-char session prefix>": "<what the session did, 120 characters or fewer, no confidential detail>"}`
   with the Write tool to `system/run/payloads/session-summaries-YYYY-MM-DD.json`, then:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/session_records.py --summaries system/run/payloads/session-summaries-YYYY-MM-DD.json`
   This records every new session (not only those that cleared the bar) in `system/sessions/YYYY/MM.jsonl`.
   A failure here is a warning, not a stop.

8. **Advance the watermark, always, even on a no-entry day**, with the exact `proposed_watermark` from step 1:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/extract_sessions.py --commit "<proposed_watermark>"`

## Hard rules

- Only `MEMORY.md` (top insert), the ledger (through `ledger.py`) and proposals (through `brain kb propose`) change.
  Never edit `RULES.md`, never run `ledger.py set-status`, never accept or reject a proposal.
- Never quote confidential content (see `brain.json` confidential globs and channel patterns).
- Never invent evidence or sessions. If you are unsure a session supports a hypothesis, do not count it.

## Report (5 bullets at most)

Sessions scanned, MEMORY entries written (0 is a valid answer), ledger items new and updated, items
that crossed the promotion threshold, proposals created (ids).
