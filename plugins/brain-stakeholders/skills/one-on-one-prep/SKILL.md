---
name: one-on-one-prep
description: Prepare for a 1:1 with a manager, report, peer or stakeholder: last conversation, open actions, recent evidence, and a short agenda. Use for "prep my 1:1 with X", "what should I cover with X", "agenda for my one-on-one".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
---

# one-on-one-prep

Read-only. The prep goes in chat; the owner decides if it is saved.

## Steps

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/prep.py --person <id>`. You get the person's role, relationship, health, days since contact, the last three
   entries of their `## 1:1 log`, open (unticked) actions, queued drafts not yet pushed, and recent non-confidential meetings that mention them.
2. Write a short agenda (under 150 words), shaped by the relationship:
   - **Carry-over:** open actions and unfinished topics, oldest first. Ask for status, not blame.
   - **From the last two weeks:** at most two items from `recent_mentions` worth raising (a win to recognise, a risk to talk through).
   - **Their topic first:** leave the first slot for what they want to discuss.
   - **Manager or report only:** one growth or feedback item (what to say, what to ask). Not for peers.
   - **Ask / offer:** one thing you need from them and one thing you can give.
3. If `queued_drafts` is not empty, mention that drafts from earlier 1:1s are waiting (`one-on-ones` pushes them).
4. If `days_since_contact` is well over their cadence, say so first.

## Rules

- Never quote the 1:1 log into anything shared. The agenda is for the owner.
- Do not add anything from `growth/` about the person (reviews, feedback) unless the owner asks.
