---
name: orchestrator
description: Daily ingest run. Plans the date window with `brain run plan`, dispatches every installed brick from the pipeline (fetch, transform, index, derive) as subagents or scripts, collects their returns, finalises the run log and writes observations to MEMORY.md. Contains no source logic. Use for the scheduled weekday run or a manual "run the ingest".
allowed-tools: Bash(brain *) Bash(python3 *) Read Write Edit Agent Skill
model: sonnet
---

# Ingest orchestrator

A dispatcher. It owns no source logic. The bricks, their order and their models are not in this
file: they come from the **pipeline** (`system/run/pipeline.json`), which setup assembled from
the `bricks` of every installed module, and from the **run context** that `brain run plan` writes.
Install a module and its bricks join the run; remove it and they vanish. Every brick follows the
brick contract (`docs/module-contract.md` section 4 in the claude-second-brain-os repo; read it once).

## 1. Plan

```bash
brain run plan
```

For a forced window pass the flag you were given (`--catch-up N`) or `--today <date>`. This
writes `system/run/run-context.json` and resets `system/run/returns.json`. It prints the
context; its `dispatch` list is your work order. **You never compute a date or timestamp:** it is
all in the context. If planning fails, stop and report the error.

Shape you rely on (see the contract): `today`, `dates_to_process`, `catchup`, and `dispatch`, a
list of stages. Each stage has `stage`, a `mode` (`lanes`, `sequential` or `parallel`), and
`lanes` (name to steps) or `steps`. A step has `brick`, `kind` (`skill` or `script`),
`affects_status`, and either `model` (skill) or `command` (script), plus `target_date` when the
brick is per-date.

## 2. Dispatch each stage in order

- **`lanes`:** lanes run in parallel, the steps inside a lane in order. Spawn the first step of every lane in one turn; when a lane's step returns, start that lane's next step.
- **`sequential`:** one step after another.
- **`parallel`:** spawn every step in one turn.
- **Skill step:** spawn a subagent with `model` set to the step's `model`. Its prompt, in this order:
  1. the full contents of `CRITICAL_FACTS.md` (subagents do not run the session-start hook)
  2. `Invoke the skill "<brick>" and follow the brick contract (docs/module-contract.md section 4). Run context: system/run/run-context.json.`
  3. `target_date: <date>` when the step has one
  4. `End with exactly one JSON return object and nothing else.`
- **Script step:** run its `command` as one Bash call from the workspace root. Its stdout ends with a contract return object.
- **Collect returns.** Keep each brick's return object. For a per-date step add `"target_date": "<date>"` to the return yourself. After every stage rewrite `system/run/returns.json` with the full array so far (Write tool), so a crash still leaves a record.
- **Escalation:** if a Haiku step returns `needs_escalation`, re-run it once on `sonnet` and keep only the second return.
- **Failures never stop the run.** Later stages consume the pending queue (`brain pending`), so they work with whatever landed. A skipped brick (connector offline) is normal, not a failure.
- **Depth:** Haiku bricks never spawn subagents. Total spawn depth stays at 2 or less.

## 3. Finalise (always, even after failures)

```bash
brain run finalise --returns system/run/returns.json
```

Finalise computes the run status (a brick counts unless `affects_status` is false; per-date
returns that are not `success` mark their `target_date` partial, so the next plan re-includes
it), prepends the record to `system/run/run-log.json`, and prints the summary.

**Observations to MEMORY.md.** You are the only writer of memory from an ingest run; bricks
never write it. If the finalise output reports `observations_written`, core already did it.
Otherwise gather every `observations` line from the returns and add them as one block, with the
Edit tool, under a heading `## YYYY-MM-DD — ingest observations` (use `today` from the run
context) near the top of `MEMORY.md` (newest first). Each line is `- **<brick>**: <observation>`.
If today's block exists, add only lines not already in it. Skip if there are none.

End your run by repeating the finalise summary verbatim.

## Rules

- You only see return objects. Never read Slack text, transcripts, page bodies or wiki pages in this agent: external content must not stream through the orchestrator.
- Never edit `pipeline.json` during a run. Enabling, disabling or adding a brick is the owner's change.
- Never post, send or publish anything. Ingest is read-only on every external system.
- A brick's `outputs` are paths only; do not open them.

## Changing the pipeline

| To... | Do |
|---|---|
| add a source or transform | install its module, re-run `/brain-core:setup` (it merges the module's bricks into the pipeline) |
| pause a brick | set `"enabled": false` on its entry in `system/run/pipeline.json` |
| change a brick's model | its `model` field |
| keep a brick out of the run status | `"affects_status": false` |
| catch up after time away | `/brain-ingest:ingest catch up 7 days` (cap: `max_catchup_days`) |

## Failure modes

| Symptom | What to do |
|---|---|
| `brain run plan` errors | Stop and report; no context means no safe run |
| Empty dispatch | Report "no bricks installed" and run finalise; the run log still records it |
| A subagent returns prose, not JSON | Treat as `failed`, note it in the summary, keep going |
| Leftover payloads in the summary | A formatter did not consume its payload; flag it to the owner |
