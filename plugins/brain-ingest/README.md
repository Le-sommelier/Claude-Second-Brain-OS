# brain-ingest

The orchestrator. It owns no source logic: it plans a date window, runs every installed ingest
brick, and records what happened.

## Install

```
/plugin install brain-ingest --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

## How it works

1. `brain run plan` (in `brain-core`) writes `system/run/run-context.json` from the pipeline: the dates to process (catching up missed days, up to `max_catchup_days`), per-source windows, and a `dispatch` list.
2. The `orchestrator` skill walks the dispatch list stage by stage (**fetch, transform, index, derive**). Skill bricks run as subagents on their configured model; script bricks run directly. Fetch bricks on Haiku, synthesis on Sonnet.
3. `brain run finalise` computes the run status, writes the run log, and the orchestrator writes brick observations to `MEMORY.md` (the only place an ingest run writes memory).

The pipeline is not hardcoded. `templates/pipeline.base.json` defines the four empty stages and
settings; setup merges in the `bricks` of every installed module. Install `brain-ingest-slack` and
its bricks appear in the fetch stage's `slack` lane.

## Skills

| Skill | What |
|---|---|
| `/brain-ingest:ingest` | Run now. "catch up N days" forces the window |
| `brain-ingest:orchestrator` | The dispatcher itself (used by the above and by the scheduled task) |

## Scheduled task (proposed at setup, registered only on a yes)

`brain-ingest-daily`, weekdays 07:00, prompt in `scheduled/ingest-daily.md`.

## Connectors

None of its own. Each brick's module declares what it needs; `brain doctor` reports gaps.

## Outputs

`system/run/{run-context,returns,run-log}.json`, `system/run/payloads/` (transient), and an
observations block in `MEMORY.md`.
