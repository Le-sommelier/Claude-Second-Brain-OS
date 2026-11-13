---
name: grill-me
description: Stress-tests the owner's thinking, one question at a time, against what the workspace already knows. Five modes - PRD or feature, roadmap or prioritisation, decision (pre-mortem), objectives, exec update. Pulls the project's facet logs, risks, decisions and people, hunts for holes, and ends with a written "holes found" list. Use when the owner says "grill me", "poke holes in this", "pre-mortem this", "challenge my plan" or "is this ready to send up".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
model: opus
---

# grill-me

A cross-examination, not a review. The owner brings a plan; you ask the question a sharp sceptic would ask
next, one at a time, until the plan has been walked end to end or the owner calls time. You do the homework
first, so you never spend the owner's attention on something the workspace already answers.

The interview pattern is inspired by Matt Pocock's `grill-me` skill (MIT). This one is written for product
work and is workspace-aware. See `ATTRIBUTION.md` in the plugin.

## The five modes

Pick the mode from the owner's words; if it is unclear, ask once. Then read that mode's file in full: it
holds the branches to walk, the questions that tend to break that kind of artifact, and where holes land.

| Mode | The owner brings | Reference |
|---|---|---|
| PRD or feature | a PRD draft, a feature idea, a one-pager | `${CLAUDE_SKILL_DIR}/references/prd.md` |
| Roadmap or prioritisation | an ordered list of bets, a quarter plan | `${CLAUDE_SKILL_DIR}/references/roadmap.md` |
| Decision (pre-mortem) | a choice about to be made or just made | `${CLAUDE_SKILL_DIR}/references/decision.md` |
| Objectives | personal or team objectives for a period | `${CLAUDE_SKILL_DIR}/references/objectives.md` |
| Exec update | a status note, steerco slide text, a leadership email draft | `${CLAUDE_SKILL_DIR}/references/exec-update.md` |

## Before the first question: do the homework

1. **Get the artifact.** A path, pasted text, or the owner's description. Read it fully. If the owner
   only has an idea, the first questions build the one-line statement of it.
2. **Pull the workspace context** (not for objectives mode, see that file). Name the project slug, then:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/gather_context.py --project <slug>`
   It writes `system/run/grill/<slug>-context.md` (people, decisions, current state of every facet log, recent
   meetings) and refuses a confidential project. Read the briefing. For any entry you need in full:
   `brain kb show <id>`. For something the briefing lacks:
   `brain kb query "select ... from current_entries where project='<slug>' and ..."`.
3. **Build the question tree privately.** List the branches of the mode file that apply, and mark which ones the
   workspace already answers. A question the workspace answers is not asked; it is turned into a challenge
   ("the risks log says X, your draft says Y: which holds?").
4. Tell the owner, in three lines at most: the mode, the artifact you read, and what you pulled
   ("project checkout-revamp: 14 current entries, 3 decisions, 5 people"). Then start.

## How the grilling runs

- **One question at a time.** Never a list. Ask, then stop and wait for the answer.
- **Make the question answerable.** Quote the exact line of the artifact or the log entry id you are
  attacking. Offer your own best answer or the likeliest answer where it helps ("My guess is the EM owns this:
  right?"), so a yes moves things on.
- **Follow the answer.** A good answer closes the branch; a vague one, a "we will figure it out" or a
  contradiction with the log gets a sharper follow-up on the same branch before you move on. Say plainly when
  an answer contradicts an entry, and cite its id and date.
- **Lookup first.** If a fact is in the workspace, find it. Ask the owner only for judgement, intent, and things
  no file holds.
- **Be relentless, not rude.** Hard on the plan, never on the person. No praise filler, no hedging.
- **Keep a visible tally** in one line after each answer: `Branches: 4 closed, 3 open. Holes: 2 (1 blocker).`
  Track unresolved points yourself in a running list; the owner can say "park it" on a question, and it becomes
  an unresolved hole rather than being dropped.
- **Stop conditions.** Every branch visited or parked, or the owner says stop. If the owner is clearly tired or
  repeating, offer to wrap up. Do not act on the plan: this skill never edits the artifact.

## Holes found (the end of every session)

Close with a **Holes found** list, in chat first. For each hole:

```
H1 [blocker | major | minor] <kind: assumption | risk | gap | contradiction | unowned | evidence>
   <title, one line>
   What is missing or wrong, and what would close it. Evidence: <entry ids, meeting ids, or "owner's answer">.
```

Then three short parts: what held up under pressure (so the owner knows what is solid), what is parked, and
the one hole to fix first. Keep resolved points out of the list: only what is still open.

### Saving them (only on the owner's yes)

Ask once: "Append these N holes to <project> as proposed entries?" Silence or "later" means no. On a yes:

1. Write the holes payload (shape in the `holes_payload.py` docstring) to
   `system/run/payloads/grill-<project>-<YYYY-MM-DD>.json` with the Write tool.
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/holes_payload.py --payload system/run/payloads/grill-<project>-<YYYY-MM-DD>.json --normalize system/run/payloads/grill-<project>-<YYYY-MM-DD>.entries.json`
   Fix any validation error and retry. Read the `preview` to the owner.
3. `brain kb append --project <project> --file system/run/payloads/grill-<project>-<YYYY-MM-DD>.entries.json`

The entries land as `by: ai`, `trust: low`, state `proposed`, source `grill:<mode>:<date>`, in the risks or
hypotheses facet. They are proposals: the owner confirms, edits or closes them like any AI-written entry.
Objectives mode never appends to a project: see its file.

## Hard rules

- Never append, edit or publish anything without the owner's explicit yes for that action.
- Never write holes into a confidential project or into a shared surface (Confluence, Slack, GitHub).
- Never quote confidential content from the workspace into the holes list, abstract it. The list is the
  owner's, and may be pasted elsewhere.
- Never invent a log entry, an owner or a date. If the workspace does not say, the hole is "unknown", and
  that is a finding.
- Read-only on every connector.
