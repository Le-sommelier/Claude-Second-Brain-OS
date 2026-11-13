# Mode: roadmap or prioritisation

Grill an ordered set of bets until the order can be defended to someone who wanted their item first.

**Context to pull:** the project briefing for each project the roadmap touches (run `gather_context.py` per
project, one at a time), especially milestones, risks, resources and teams.

## Branches to walk

1. **The criterion.** What rule orders the list (impact, effort, risk, dependency, strategic theme)? Is it
   written down, or is it the owner's gut? Would a different stakeholder rank the same items differently?
2. **The evidence per bet.** For the top three: the opportunity size and how it was estimated, the confidence,
   the source. For the bottom three: why are they there and not higher?
3. **Capacity.** Does the list fit the people on it? Cross-check the resources and teams logs and the members.
   What is the named owner and engineering lead of each item?
4. **Dependencies and sequencing.** What must land first? Which external team or contract gates an item? Which
   item is quietly blocked by an open risk?
5. **What is not on the list.** What was cut, deferred or never considered, and who knows it was cut?
6. **Commitments versus bets.** Which items are promises to someone and which are experiments? Are experiments
   dressed up as dates?
7. **Reversibility and review points.** When is the plan re-read, and what would trigger a re-order?
8. **Narrative.** Can the owner say in one breath why this order beats the reverse order?

## Questions that tend to break a roadmap

- "Swap items 1 and 3. What do you lose, and who notices first?"
- "Which item on here would you drop if you lost a third of the team tomorrow?"
- "What did you rank above this one only because someone senior asked?"
- "Which date on this page is a guess?"

## Where holes go

Capacity or dependency gaps: `risks` of the affected project, kind `risk` or `unowned`. A ranking resting on an
unproven estimate: `hypotheses`, kind `evidence`. A milestone whose date conflicts with the log: `risks`,
kind `contradiction`.
