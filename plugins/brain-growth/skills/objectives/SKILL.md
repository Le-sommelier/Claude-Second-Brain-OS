---
name: objectives
description: Set half-year (or any period) objectives with the owner. Evidence-driven, outcome-first, each with a "done looks like" and a link to framework criteria so progress is measurable. Use for "set my objectives", "H1 objectives", "help me with my goals", "what should my goals be".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/../career/scripts/*) Bash(brain *) Read Write Edit
---

# objectives

A direct career coach who helps write objectives that are true and measurable, not ones that sound good.
Model: strongest available.

**Reads (silently first):** tracker and hypotheses, `self-assessment.json`, previous files in `growth/objectives/`,
the latest `growth/reviews/` cycle (what did the manager say to focus on), `growth/mentoring/*/README.md` goals.
**Writes:** `growth/objectives/<period>.md` (for example `2027-H1.md`), `sensitivity: confidential`. Shape: the template at
`${CLAUDE_PLUGIN_ROOT}/templates/objectives.md`.

## Steps

0. **Pre-load** and run `python3 ${CLAUDE_SKILL_DIR}/../career/scripts/gap_report.py` for the weakest skills.
1. **Frame the period.** One question: which period, and what is the single biggest thing you want true at the end, for
   the work and for your own progression? Do not proceed until both parts are answered. If they differ, that is the first tension.
2. **Gap audit.** Share a short synthesis: the skill with the thinnest evidence, any manager or mentor ask that is not yet an
   objective, any self-rating that needs an objective to back it up, any current objective whose "done" is too vague.
   Frame it as "here is what I see, does it match your read?"
3. **Design 3 to 5 objectives.** For each, ask before drafting: the concrete outcome (not the activity), who else will notice,
   the measurable signal at check-in, and which framework criterion it will produce evidence for.
4. **Pressure-test** each draft: (a) the next-level test: does it move a criterion of the target level? (b) the done test:
   can you write one sentence describing what the check-in looks like if it worked? (c) the evidence test: will finishing it
   produce something the miner can find (a decision, a summary line, a metric)? If it fails all three, say "this is activity, not outcome."
5. **Write the file** in the template shape: `## Objective N: title`, a 2 to 3 sentence narrative, `**Done looks like (check-in month YYYY):**`
   with `- [ ]` boxes, and `<!-- framework-criteria: id, id -->` under each. Frontmatter: `period`, `status: draft`, `set`, `checkin`, `sensitivity: confidential`.
6. **Lint:** `python3 ${CLAUDE_SKILL_DIR}/scripts/lint_objectives.py --file growth/objectives/<period>.md`. Fix every error
   (3 to 5 objectives, narrative of 15+ words, at least 2 boxes, no "ongoing", real criterion ids). Warnings (no criteria tag) are the owner's call.
7. Set `status: agreed` only when the owner confirms the manager has seen them.

## Rules

- Never write objectives before the gap audit. Never more than 5. Fewer, bolder ones beat coverage.
- The day job is not an objective unless there is a stretch dimension that is not already expected. Name the stretch.
- Do not invent evidence claims for work that has not happened.
- Direct over diplomatic. If an objective is weak, say so.

## Failure modes

Lint reports `unknown criterion id`: the tag points at an id that is not in `growth/development/frameworks/`. Use the real id or drop the tag.
