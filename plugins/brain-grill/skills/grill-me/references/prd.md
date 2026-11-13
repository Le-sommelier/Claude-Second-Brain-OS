# Mode: PRD or feature

Grill a requirements draft until a team could build the right thing without a meeting.

**Context to pull:** the project briefing (risks, hypotheses, decisions, people). Also read the project's
earlier PRDs in `projects/<slug>/artefacts/` if any, to catch silent reversals.

## Branches to walk (skip the ones already answered)

1. **Problem.** Who has it, how often, what do they do today, what is the evidence (a meeting id, a data point, a
   support theme)? Is the problem stated without the solution inside it?
2. **Why now, why us.** What changed, what does waiting cost, who is asking? Check the decisions log for an
   earlier "not now".
3. **Success.** One primary metric, its baseline, its target, the date, and who reads it. What number would make
   you kill the feature? Guardrail metrics.
4. **Scope.** What is explicitly out? What is the smallest version that tests the riskiest assumption? Where is
   scope creep most likely?
5. **Users and edge cases.** Which segment loses out? What happens on failure, empty states, permissions,
   migration of existing users?
6. **Assumptions.** List every "will" in the draft. Which are tested, which are guesses, which would sink the
   plan? Compare with the hypotheses log.
7. **Dependencies and people.** Which team or system must change, who decides, who is the single owner? Compare
   with the members list and the open dependencies in the risks log.
8. **Delivery risk.** What breaks the date? What is the rollout, the rollback, the communication?
9. **Trade-offs taken.** What was rejected and why? If nothing, the draft has no trade-offs, which is itself a hole.

## Questions that tend to break a PRD

- "If this shipped and the metric did not move, what would you conclude?"
- "Which sentence in this draft would an engineer have to ask you about?"
- "Who said no to this before, and what changed?"
- "What is the cheapest experiment that would tell you in two weeks you are wrong?"

## Where holes go

Untested assumption: `hypotheses` facet, kind `assumption`. A delivery, dependency or scope risk: `risks`,
kind `risk`, `unowned` or `gap`. A claim the log contradicts: `risks`, kind `contradiction`, with the entry in `refs`.
