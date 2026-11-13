# brain-learning-loop

The part of the workspace that learns. Every night it reads the day's Claude Code sessions and keeps what is
worth keeping; every Friday it counts the evidence and puts the decisions in front of you. **Only you promote a
rule.**

## Install

```
/plugin install brain-learning-loop --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

```
session work
   -> nightly consolidate -> MEMORY.md (newest first) + hypotheses ledger + improvement proposals
   -> weekly system review -> promotion candidates (3 distinct sessions), demotion, stale, drift
   -> you -> RULES.md
```

## Skills

| Skill | What it does |
|---|---|
| `consolidate` | Nightly. Extracts the day's transcripts, writes learnings to the top of `MEMORY.md`, records **hypotheses and patterns** with evidence counted in distinct sessions, and files **improvements** as `inbox/proposals/PRP-NNN-*.md` through `brain kb propose`. Also records one structured line per session. |
| `system-review` | Weekly. One report in `system/reviews/`: items at three or more sessions of support, items to demote, stale entries, proposals awaiting an answer, drift, vault health, and `brain doctor`. |

Transcripts are found at run time in `~/.claude/projects/<encoded workspace path>/` (the folder name is computed
from the workspace root). Sessions that touched a confidential path are digested as "content withheld".

## Outputs

`MEMORY.md` (top insert), `system/learning/ledger.json` (state) and `system/learning/hypotheses.md` (generated
view), `inbox/proposals/PRP-*.md`, `system/sessions/YYYY/MM.jsonl`, `system/reviews/_system-review-YYYY-Www.md`.

## Connectors

None. Everything is local.

## Scheduled tasks proposed at setup

- `brain-session-consolidate`, daily 19:00.
- `brain-system-review`, Fridays 15:00.

## Configuration

`skills/system-review/references/review-config.json` holds the thresholds (promotion at 3 sessions, demotion at
2 refutations, stale windows). Extra hook-noise phrases to ignore in transcripts can be listed in
`.claude/brain.json` under `learning.noise_markers`.

## Rules of the loop

- The nightly job never edits `RULES.md`, and the weekly review never edits anything but its own report.
- Evidence counts distinct sessions, so one long session cannot fire a pattern three times.
- Proposals are never auto-applied: you answer with `brain kb confirm PRP-NNN` or `--reject`.

See the [module contract](../../docs/module-contract.md).
