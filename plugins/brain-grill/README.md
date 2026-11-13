# brain-grill

Grill me: a relentless, one-question-at-a-time stress test of your thinking, run against what your workspace
already knows. It ends with a written list of holes, and saves nothing without your yes.

## Install

```
/plugin install brain-grill --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

## What it does

`/brain-grill:grill-me` runs one of five modes:

| Mode | You bring | It attacks |
|---|---|---|
| PRD or feature | a draft or an idea | problem, success measure, scope, assumptions, dependencies, delivery risk |
| Roadmap or prioritisation | an ordered list of bets | the ordering rule, evidence, capacity, sequencing, what was cut |
| Decision (pre-mortem) | a choice about to be made | alternatives, failure stories, reversibility, precedent, tripwires |
| Objectives | objectives for a period | outcome versus activity, measures, stretch, control, trade-offs (confidential) |
| Exec update | a status note or steerco text | claims against the status log, buried risks, the ask, surprises |

Before the first question it pulls the project's facet logs, risks, decisions and people through `brain kb`
and builds the question tree from them, so it never asks what a file already answers. It asks one question,
waits, follows the answer, and keeps a tally of open branches and holes. At the end it prints a **Holes found**
list. If you say yes, the holes are appended to the project as `by: ai`, `trust: low`, state `proposed`
entries in the risks or hypotheses log. You confirm, edit or close them like any AI-written entry.

## Connectors

None. Everything is read from the local workspace.

## Outputs

- `system/run/grill/<project>-context.md`: the briefing (generated, safe to delete).
- `system/run/payloads/grill-<project>-<date>.json` and `.entries.json`: the holes payload, only after your yes.
- Appended entries in `projects/<project>/risks.md` or `hypotheses.md`, only after your yes.

Objectives mode never writes into a project; its holes stay in chat unless you pick a confidential file.

## Scripts

| Script | Job |
|---|---|
| `gather_context.py` | assemble the briefing from `brain kb query`; skips confidential files and redacted meetings |
| `holes_payload.py` | validate the holes list against the entry grammar and preview the entries before they are appended |

## Scheduled tasks

None. This is an interactive skill.

## Attribution

The interview pattern is inspired by Matt Pocock's `grill-me` skill, published under the MIT license.
This plugin's text, its five product modes, the workspace lookups and the holes list are original. The
required notice is in [ATTRIBUTION.md](ATTRIBUTION.md).

> `grill-me` in this plugin is inspired by Matt Pocock's skills collection (MIT, Copyright (c) 2026 Matt Pocock).

See the [module contract](../../docs/module-contract.md) for how modules fit together.
