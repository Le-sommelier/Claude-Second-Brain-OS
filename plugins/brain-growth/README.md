# brain-growth

Career growth for a product manager, confidential by default. Everything lives in `growth/` and never reaches digests, the wiki or any shared surface.

## Install

```
/plugin install brain-growth --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

| Skill | What it does |
|---|---|
| `growth-signals` | Weekly mining of your work for evidence against your framework; you triage, `promote.py` records what you accept; markdown evidence matrix |
| `career` | Career conversation: where you are, where you want to go, the gaps, the next moves |
| `objectives` | Set 3 to 5 outcome-first objectives, each tied to framework criteria, with a linter |
| `objective-review` | Mid-period check-in: progress per objective against mined evidence, check-in notes with your yes |
| `self-review` | Coaching session that ends with a draft in the format of your review tool |

**Connectors:** none. It reads local markdown only.

## You fill in (templates copied by `/brain-core:setup`, never overwritten)

| File | What |
|---|---|
| `growth/development/frameworks/*.md` | Your company's competency framework. One file per level or track. Format in the template |
| `.claude/brain/growth/source-config.json` | Current and target level, what to scan, look-back, hypothesis thresholds |
| `.claude/brain/growth/signal-patterns.json` | Regex patterns for the deterministic miner |
| `.claude/brain/growth/values.json` | Your company values (tag evidence, write the values paragraph) |
| `.claude/brain/growth/senior-leaders.json` | Which role titles count as senior for the senior-feedback pattern |
| `.claude/brain/growth/review-format.json` | The sections and word budgets of your review form |

The shipped files describe a fictional company (Fernhill). Replace them.

## Outputs

`growth/development/{evidence-candidates.md, level-hypotheses.md, performance-tracker.md, coverage-matrix.md, self-assessment.json, run/}`, `growth/objectives/<period>.md`, `growth/reviews/<cycle>/`.

## Scheduled task proposed during setup

`brain-growth-weekly`, Sundays 19:00: mine, classify, queue. It never promotes and never writes outside `growth/`.

## Scripts (all stdlib, Python 3.11+)

`mine_signals.py`, `append_evidence.py`, `promote.py`, `build_matrix.py` (growth-signals); `gap_report.py` (career); `lint_objectives.py` (objectives); `objective_progress.py` (objective-review); `evidence_map.py` (self-review).

See the [module contract](../../docs/module-contract.md).
