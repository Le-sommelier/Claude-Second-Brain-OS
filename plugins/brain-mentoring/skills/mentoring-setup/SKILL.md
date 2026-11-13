---
name: mentoring-setup
description: Start a mentorship, as mentor or mentee. Creates growth/mentoring/<person-id>/ with goals, an agreement, a cadence, a sessions folder and an actions log. Use for "start mentoring X", "I am mentoring X", "X is going to mentor me", "set up a mentorship".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Edit
---

# mentoring-setup

**Writes:** `growth/mentoring/<person-id>/{README.md, sessions/, actions.md}`. All confidential
(`sensitivity: confidential`, bodies wrapped in redact-on-share markers). Never overwrites an existing folder.

## Steps

1. Ask, one at a time and only what is missing: **who** (full name, to derive `first-last`), **which way** (`mentor`: you mentor them;
   `mentee`: they mentor you), **cadence** (weekly, fortnightly, monthly, quarterly), and **1 to 3 goals** in the mentee's words.
   Push for goals that can be observed ("present a roadmap to the Director unaided by January"), not themes ("grow in confidence").
2. If `people/<person-id>.md` does not exist, run `brain new person <person-id>` so the person is in the workspace.
3. `python3 ${CLAUDE_SKILL_DIR}/scripts/mentoring_setup.py --person <id> --mode <mentor|mentee> --cadence <c> --goal "..." --goal "..." [--name "Full Name"]`
4. Show the README and ask whether the default agreement fits (confidentiality, cancelling, who brings what). Edit it with them; keep
   it inside the confidential markers.
5. Suggest the first session date and offer `mentoring-prep` for it.

## Rules

- A mentorship with no goals drifts: the script refuses `--goal`-less setups.
- What the mentee says in sessions is theirs. In your own growth notes use themes, never specifics, unless they agree.

## Failure modes

"already exists": the mentorship was set up; edit the README instead. "person id must look like first-last": use lowercase with a hyphen.
