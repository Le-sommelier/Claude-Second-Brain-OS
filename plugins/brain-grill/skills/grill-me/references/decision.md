# Mode: decision (pre-mortem)

Grill a choice that is about to be made, or was just made, by assuming it failed and working backwards.

**Context to pull:** the project briefing; read the decisions log for precedent and anything the new choice
supersedes. Use `brain kb show DEC-...` for the full text of relevant decisions.

## Branches to walk

1. **The decision, stated.** One sentence: we will X rather than Y, by date Z, owned by W. If it cannot be
   said in a sentence, the decision is not yet made.
2. **Alternatives.** Which options were seriously considered, including "do nothing" and "do less"? Why was
   each rejected? Is the chosen option compared like for like?
3. **Pre-mortem.** "It is six months out and this went badly." Make the owner generate the failure stories, then
   rank them by likelihood and by damage. Push past the first three: the interesting ones come after.
4. **Assumptions it rests on.** Which are facts, which are bets? Which bet, if wrong, makes the whole choice wrong?
5. **Reversibility.** What does undoing it cost, and after what point is it no longer possible? One-way doors get
   more scrutiny than two-way doors.
6. **Who is affected and who has been told.** Who decides, who must agree, who will be surprised? Compare with the
   members list and the stakeholders in the log.
7. **Signals and tripwires.** What early evidence would show it going wrong, who watches it, and what is the
   pre-agreed response?
8. **Precedent.** Does it contradict or quietly supersede an earlier decision? Cite the id.

## Questions that tend to break a decision

- "What is the strongest argument for the option you rejected, in its owner's words?"
- "If you had to make this decision again with half the information, would you?"
- "What would have to be true for you to reverse this in a month?"
- "Who would you least like to explain this to?"

## Where holes go

Each plausible failure with no mitigation: `risks`, kind `risk`. An unproven load-bearing assumption:
`hypotheses`, kind `assumption`. A missing owner or approver: `risks`, kind `unowned`. A clash with an earlier
decision: `risks`, kind `contradiction`, earlier decision in `refs`.
