---
name: doctor
description: Health check for a claude-second-brain-os workspace. Runs `brain doctor` (config, path map, modules, pipeline, schema, context-layer references, stale READMEs, kb validation), then checks what the filesystem can't see (connectors, scheduled tasks), and explains each finding with its fix. Use for "check my setup", "is everything wired", "why didn't the ingest run", or when the session hook reports config drift.
allowed-tools: Bash(brain *) Read
---

# Doctor

Silent failure is the expensive kind: a wrong path or a task that never registered errors
nowhere. This skill makes the drift loud. It is read-only.

## Steps

1. Run `brain doctor`. It prints one JSON object: `status` (`ok`, `warn`, `error`), `checks`
   (each with `check`, `level`, `detail`) and `verify_in_session`.
2. For each `verify_in_session.scheduled` entry, list the scheduled tasks with this session's
   scheduled-task tool (if it has one) and check the task exists and is enabled. A task a module
   proposes that isn't registered is fine if the owner declined it; say so, don't register it.
3. For each `verify_in_session.connectors` entry with `required: true`, check this session has
   tools for that connector (for example Slack search tools for Slack). Don't call anything that writes.
4. Report, errors first:

   ```
   Workspace health: <ok|warn|error>
   Errors
   - <check>: <detail> → <fix>
   Warnings
   - ...
   Not checkable here
   - ...
   ```

## Fixes to suggest

| Check | Fix |
|---|---|
| `config` placeholders / owner fields | re-run `/brain-core:setup` |
| `paths` missing key | create the folder, or add the value to `_notes.create_on_demand` in `.claude/paths.json` |
| `modules` enabled but not installed | install the plugin, or remove it from `modules` in `.claude/brain.json` |
| `module-paths` / installed but not set up | re-run `/brain-core:setup` |
| `pipeline` module roots no longer exist | re-run `/brain-core:setup` (plugin updates move cache paths) |
| `schema` version differs | copy the plugin's `templates/workspace/system/schema/kb.sql` over the workspace copy after reading the diff with the owner |
| `python` PyYAML missing | `python3 -m pip install pyyaml` |
| `kb` validation errors | open each `file:line`; fix the entry grammar (`system/schema/entry-grammar.md`). Never delete an entry to make it pass |
| `stale-readmes` | review the project README and bump `last_reviewed` |

Never fix anything yourself in this skill. Offer to, and do it only after a yes.
