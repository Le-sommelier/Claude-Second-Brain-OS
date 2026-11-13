# brain-core

The required module of claude-second-brain-os. It creates and checks your workspace, ships the `brain`
CLI every other module calls, keeps a SQLite index over your markdown, scaffolds projects,
topics and people, injects your context at session start, and carries the rules, output styles
and personas that make Claude behave like a PM's chief of staff instead of a chat window.

Module rules for contributors: [`docs/module-contract.md`](../../docs/module-contract.md).

## Install

```
/plugin marketplace add <this repo>
/plugin install brain-core@claude-second-brain-os
/brain-core:setup
```

Setup interviews you (name, role, company, timezone, modules, confidential patterns), shows
every folder and file it will create, and writes only after you say yes. It never overwrites a
file: templates are copied only when missing, and JSON config is merged add-only. Re-run it
whenever you install or remove a module. Needs Python 3.11+ and PyYAML (`python3 -m pip install pyyaml`).

## How it's shaped

The bet: **the agent works on a structure, not on prompts in a chat window.** A well-shaped
folder plus a few deterministic scripts persist between sessions; a clever prompt doesn't.

| Layer | Files | Owner |
|---|---|---|
| Anchor | `CRITICAL_FACTS.md` (~150 tokens, loaded every session) | you |
| Contract | `CLAUDE.md`, `RULES.md` | you |
| Identity | `SOUL.md`, `BRAND.md` (guided templates) | you |
| Map | `INDEX.md`, `.claude/paths.json` | setup, checked by `brain doctor` |
| Behaviour | `.claude/rules/`, `.claude/output-styles/`, hooks, agents | brain-core |
| Content | `projects/`, `people/`, `topics/`, `raw/`, `todos/` | ingest bricks, `brain kb`, you |

Principles carried over from a setup that has run daily for months:

- **One owner per fact.** Paths live only in `paths.json`; what runs lives only in the
  scheduled-task registry; the folder map lives only in `INDEX.md`. Restating a fact is how this
  kind of system rots.
- **Markdown is the source of truth; the index is generated.** `brain kb build` validates every
  entry first and writes nothing on any error.
- **Append-only, sourced, provenance-tagged logs.** Every entry says who wrote it (`human`, `ai`,
  `ai-confirmed`), where it came from, and a trust tier computed from who attended. AI decisions
  start `proposed`; only HIGH-trust, non-hedged ones auto-confirm.
- **Silent failure is the expensive kind.** `brain doctor` and the session hook make drift loud.
- **Nothing is published without a per-artifact yes.**

## Commands: the `brain` CLI

`bin/brain` is on the Bash PATH while the plugin is enabled. Other modules call core only through it.

| Command | What |
|---|---|
| `brain root` | print the workspace root (`$BRAIN_ROOT`, else the nearest parent of the cwd holding `.claude/brain.json`) |
| `brain doctor [--quick]` | config, paths, modules, pipeline roots, schema, context-layer references, stale READMEs, kb validation; JSON out, exit 1 on error |
| `brain pending --flag wiki_processed [--source-type T] [--max-age-days N]` | the pending queue |
| `brain flag --set wiki_processed=true --file <rel> \| --files-from <payload.json>` | flip queue flags (payload consumed on success) |
| `brain kb build [--check] [--force]` | validate and rebuild `system/kb.db` |
| `brain kb index` | regenerate `_index.md` files and each project README's current-state block |
| `brain kb query "<sql>"`, `brain kb show <id>` | read the index (JSON lines) |
| `brain kb attention [--today D]` | named queries from `system/schema/attention.yaml` into `inbox/attention.md` |
| `brain kb trust <slug> [--raw ID]` | trust tier of raw items for a project |
| `brain kb append --project <slug> --file <payload.json> [--dry-run]` | validated, numbered, sourced entries and decisions |
| `brain kb propose --title T --source ID [--audience system\|owner] [--body … \| --body-file …]` | a proposal in `inbox/proposals/` |
| `brain kb confirm <DEC-id \| slug/ID \| PRP-NNN> [--reject]` | the owner's confirmation |
| `brain new project\|topic <slug>`, `brain new person <first-last>` | scaffold from templates; never overwrites |
| `brain run plan [--today D] [--catch-up N]` | ingest window and dispatch list in `system/run/run-context.json` |
| `brain run finalise --returns system/run/returns.json` | run status, partial dates, run log, summary |

`kb build`, `kb index` and `kb attention` accept `--as-brick <name>` to print a brick contract
return, which is how they run as script steps in the ingest pipeline.

### The run context brain-ingest relies on

`brain run plan` reads `system/run/pipeline.json` (brain-ingest's base pipeline plus every module's
`bricks`, merged by setup) and prints:

```json
{
  "run_id": "2026-11-13T07:00:02Z", "today": "2026-11-13", "timezone": "Europe/London",
  "dates_to_process": ["2026-11-12", "2026-11-13"], "dates_dropped_by_cap": [], "catchup": true,
  "window": {"2026-11-13": {"start_iso": "...", "end_iso": "...", "oldest_ts": "...", "latest_ts": "..."}},
  "slack": {"window": {"2026-11-13": {"oldest_ts": "...", "latest_ts": "..."}}, "flagged_after": "...", "owed_after": "..."},
  "settings": {"max_catchup_days": 14, "bricks": {"<brick>": {"...": "per-brick settings from the pipeline"}}},
  "dispatch": [
    {"stage": "fetch", "mode": "lanes", "lanes": {"slack": [
      {"brick": "brain-ingest-slack:ingest-slack-channels", "kind": "skill", "skill": "brain-ingest-slack:ingest-slack-channels",
       "model": "haiku", "affects_status": true, "target_date": "2026-11-12"}]}},
    {"stage": "index", "mode": "sequential", "steps": [
      {"brick": "brain-core:kb-build", "kind": "script", "command": "brain kb build --as-brick brain-core:kb-build", "affects_status": true}]}
  ]
}
```

Each date's window runs from local midnight the day before to local midnight the day after
(owner timezone). Script bricks declared as `{"script": "skills/<s>/scripts/x.py"}` get an
absolute `command` from the module's plugin root at setup; if a plugin update moves that root,
`run plan` and `doctor` fail with "re-run /brain-core:setup to refresh module roots".
`finalise` marks a date partial when a per-date return for it is not `success`/`skipped` (or a
return lists it in `dates_partial`), so the next plan re-includes it. It never writes
`MEMORY.md` (`observations_written: false`); the orchestrator records observations.

## Skills

| Skill | Use |
|---|---|
| `/brain-core:setup` | create or update the workspace (preview, then write on a yes; proposes scheduled tasks) |
| `/brain-core:doctor` | health check, including the connectors and scheduled tasks the filesystem can't see |
| `/brain-core:new-project` | scaffold a project or topic and fill its human sections with you |
| `/brain-core:kb` | query, append, propose, confirm |

## Agents

`brain-core:pm-researcher` (cited evidence, no recommendation), `brain-core:prd-writer` (problem-first
PRDs), `brain-core:exec-update` (90-second leadership updates, Opus).

## Hooks

| Event | Does |
|---|---|
| SessionStart | injects the read order tiered by model (Haiku: anchor and todos; Sonnet: + rules, voice, memory head, health; Opus or unknown: everything), plus a stale-config guard (placeholders left, plugin version moved, module paths not merged, pipeline roots gone) |
| UserPromptSubmit | re-injects `CRITICAL_FACTS.md` each turn in Haiku sessions only |
| PostToolUse (Edit/Write) | warn-only: entry-grammar errors in facet logs, README frontmatter, `[[links]]` that don't resolve, edits under confidential globs |
| PreCompact | archives the transcript to `.claude/.session-log/transcripts/` (last 30) |
| Stop | one line per session in `.claude/.session-log/sessions.jsonl` (last 200) |

All hooks are silent outside a claude-second-brain-os workspace and never block.

## What setup writes

`.claude/brain.json` (owner, modules, confidential patterns), `.claude/paths.json`, the context
files above, `.claude/rules/{confidential,coding,meetings,slack,confluence,sources}.md`,
`.claude/output-styles/{terse,exec-update,wiki-page}.md`, `system/schema/` (the kb contract),
`todos/`, `.secrets/README.md` (never `apis.env` itself), `.gitignore`, and every enabled
module's folders, templates and ingest bricks.

## Connectors

None. brain-core reads and writes local files only.

## Scheduled task it proposes

`brain-core-weekly-doctor`, Fridays 16:00: runs `brain doctor`, rebuilds the index and attention
list, and raises proposals for anything that needs you. Registered only if you say yes.

## Tests

`python3 -m unittest discover -s tests/brain-core -v` (from the repo root) runs against a temp copy of
`examples/sample-workspace`.
