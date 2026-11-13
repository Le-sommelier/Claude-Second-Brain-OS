---
name: mentoring-review
description: Quarterly review of a mentorship against its goals, from the sessions held and the actions closed. Use for "mentoring review", "how is my mentorship with X going", "quarterly check on mentoring".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
---

# mentoring-review

**Reads:** `growth/mentoring/<id>/` only. **Writes:** `growth/mentoring/<id>/review-<period>.md` (confidential), on the owner's yes.

## Steps

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/mentoring_review.py --person <id> --quarter 2026-Q4` (or `--since`/`--until`).
   You get sessions held versus expected from the cadence, the longest gap, actions opened, closed, open and overdue, the goals, and the session note paths.
2. **Read the session notes** in the window and judge each goal: moved, stalled or not touched, with the one or two moments that show it.
   Be honest about a goal nobody raised: that is a finding, not an omission.
3. Write the review (about one page): **Cadence** (held vs expected, why gaps), **Goals** (one line each with the evidence), **Actions** (closed rate, what keeps slipping),
   **What worked**, **Change for next quarter** (one thing to start, stop or reshape, including re-writing a goal that stopped being the right one).
4. Show it. On a yes, save it. In mentor mode, offer to share a paraphrased version with the mentee; they decide what leaves the folder.

## Failure modes

`--quarter must look like 2026-Q4`. A window with 0 sessions: say so plainly and ask whether the mentorship is paused or over.
