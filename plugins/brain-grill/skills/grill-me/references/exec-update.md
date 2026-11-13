# Mode: exec update

Grill a status note, steerco text or leadership email as the reader who has two minutes and a sceptical
instinct. The goal is that nothing in it surprises them later.

**Context to pull:** the project briefing: latest status entry and its RAG, risks, milestones, decisions,
recent meetings. The note is checked against these, claim by claim.

## Branches to walk

1. **The ask.** What does the owner want from this reader: a decision, an unblock, awareness? Is the ask in
   the first three lines, with a date? An update with no ask should say so.
2. **The headline versus the log.** Does the stated status match the latest status entry and the RAG? If the
   note is greener than the log, name the entries that disagree.
3. **Every claim has evidence.** For each statement of progress: where is the proof (shipped, measured,
   confirmed by whom)? "On track" without a date and an owner is a hole.
4. **Risks stated or buried.** Compare with open risks, especially red or overdue ones. Would the reader be
   upset to learn of one from someone else?
5. **Numbers.** Definitions, baselines, comparison periods. Would two people compute the same figure?
6. **Decisions made and needed.** What was decided since the last update (cite ids)? What is waiting on this reader?
7. **Surprises.** What changed since last time that the reader would not guess? What did the owner promise last
   time, and is it delivered?
8. **Audience fit.** Jargon, names the reader will not know, length. Would it survive being forwarded?
9. **Confidentiality.** Does anything come from a leadership-only channel or a confidential file? That must be
   abstracted, not quoted.

## Questions that tend to break an exec update

- "What is the first question this reader asks, and does the note answer it?"
- "Which sentence would you cut if you only had a third of the space?"
- "Where is the bad news, and why is it that far down?"
- "If the project were red tomorrow, which line here would look misleading?"

## Where holes go

A status claim the log contradicts: `risks`, kind `contradiction`, with the entry in `refs`. A claim with no
evidence: `hypotheses`, kind `evidence`. An ask with no owner or date: `risks`, kind `unowned`. The note
itself is not edited: the owner rewrites it with the list in hand.
