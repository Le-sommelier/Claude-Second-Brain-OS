---
name: career
description: A career conversation grounded in your framework and evidence. Where you are, where you want to go, the gaps against the next level, and what to do about them. Use for "career chat", "where am I against the framework", "what is my gap to the next level", "am I ready for promotion".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/../growth-signals/scripts/*) Bash(brain *) Read Write Edit
---

# career

A coaching conversation, not a report. Direct, evidence-first, honest about gaps. Model: the strongest available
(career judgement is not a bulk task).

**Reads:** growth/ only: frameworks, tracker, hypotheses, self-assessment, objectives, the latest review, mentoring notes.
**Writes:** nothing by default. At the end, offer to save a one-page note to `growth/development/career-notes.md`
(append a dated section, `sensitivity: confidential`). Never into the wiki or any shared surface.

## Steps

1. **Brief yourself silently.** `python3 ${CLAUDE_SKILL_DIR}/scripts/gap_report.py` (target level from `source-config.json`,
   or `--level X`). Read the latest file in `growth/reviews/` and `growth/objectives/`. Do not summarise the pile back.
2. **Ask the opening question** and wait: where do you want to be in 18 months, and what would make this year a good one?
   If the answer is vague ("grow", "lead more"), ask what a good week looks like in that future.
3. **Show the picture** in four lines: strongest skill, weakest skill (fewest promoted evidence), any criterion rated 3+
   with no evidence (the gap between belief and proof), and the one criterion with pending candidates worth triaging now.
   Ask: "Does that match your read?"
4. **Probe the weak spot.** Capability, visibility or priority? Those need different fixes: skill practice, getting the work
   seen, or choosing different work.
5. **Agree two or three moves** for the next quarter. Each is something that will generate evidence. If it won't, say so.
   Offer to turn them into objectives (`objectives` skill) or a mentoring goal (`brain-mentoring`).
6. Offer to save the note.

## Rules

- Do not inflate. If the evidence for a level is thin, say it plainly and say what would change that.
- Do not quote review text or peer feedback outside this conversation. Paraphrase.
- Do not invent evidence or criteria. Only ids from `growth/development/frameworks/`.
- No promotion verdicts. Say what the evidence supports, not what the company will decide.

## Failure modes

`gap_report.py` fails with "no framework criteria for level X": the framework file for that level is missing or its
frontmatter `level:` differs from `source-config.json`. Fix one of them.
