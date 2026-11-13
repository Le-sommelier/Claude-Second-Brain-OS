---
name: mentoring-prep
description: Prepare for a mentoring session from the last session note, the open actions and recent relevant evidence. Use for "prep my session with X", "mentoring prep", "what should I cover with my mentee/mentor".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
---

# mentoring-prep

A one-page prep, ten minutes. Read-only: writes nothing unless the owner asks to save it.

## Steps

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/mentoring_prep.py --person <id>`. You get goals, cadence and whether a session is due, the last session
   note, open actions (overdue flagged), recent non-confidential meetings mentioning them, and objectives that mention them.
2. Write the prep in chat, in this shape, no longer than a page:
   - **Since last time:** what happened on each open action. Overdue ones first, framed as a question, not a reproach.
   - **One goal to move:** the goal (G1, G2...) that has had least attention in recent sessions, and why now.
   - **Their topic / your stretch** (mentor mode): the topic they raised last time that was not finished, and one stretch question for you to bring.
     In **mentee mode** swap it: what you want to ask for, and what to bring as evidence of progress.
   - **Evidence worth mentioning:** items from `recent_mentions` that illustrate progress or a pattern. Paraphrase; never quote confidential notes into anything shared.
   - **Close:** agree the next date and who owns which action.
3. Offer to save it as `growth/mentoring/<id>/sessions/prep-<date>.md` (inside confidential markers). Otherwise leave it in chat.

## Rules

- `session_due: true` with `days_since_last` well over the cadence is worth saying out loud: the cadence slipped.
- Do not read files outside what the script lists and `growth/mentoring/<id>/`.
