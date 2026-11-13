---
name: setup
description: Create or update a claude-second-brain-os workspace. Interviews the owner (name, role, company, timezone, modules, confidential patterns), previews every folder and file it will create, and writes only on a yes, never overwriting anything. Re-run it after installing or removing a module to merge that module's paths, folders, templates and ingest bricks. Use for "set up my PM workspace", "install brain-os", "I added a module", or when the session hook reports config drift.
argument-hint: "[target folder]"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/setup_workspace.py *) Bash(brain *) Read Write
---

# Setup

The wizard is a conversation; the writing is done by one deterministic script,
`${CLAUDE_SKILL_DIR}/scripts/setup_workspace.py`, which has a `--plan` mode that writes nothing
and an `--apply` mode that never overwrites. You never create workspace files by hand.

## Inputs

- The target folder: the argument, else the current directory. If the current directory already
  holds `.claude/brain.json`, this is a re-run: read that file and only ask about what changed.
- The owner's answers (below).
- Installed modules: every plugin next to brain-core that ships a `brain.module.json`. The script
  discovers them from `${CLAUDE_PLUGIN_ROOT}/..` (a marketplace checkout) and
  `${CLAUDE_PLUGIN_ROOT}/../..` (the plugin cache). If discovery finds none besides brain-core, ask
  the owner which modules they installed and pass them anyway: the plan lists any it can't find.

## Steps

1. **Interview**, one short question at a time, defaults in brackets. Skip any answer you already have.
   - Full name, and the first name to use in prose.
   - Person ID: suggest `<first>-<last>` in lowercase (this ID ties them to meetings and projects).
   - Role and company.
   - Timezone (IANA, for example `Europe/London` or `America/New_York`): it sets the daily ingest window.
   - Modules: show the installed ones with each one's one-line purpose (from the marketplace) and
     ask which to enable. Default: all installed. Mention that brain-ingest is needed for any source
     module to run on a schedule.
   - Confidential patterns: show the defaults (`growth/**`; Slack channels `*-leadership*`,
     `*-leads`, `*-lead-*`, `*-exec*`, `exec-*`, `leads-*`) and ask for additions, for example a
     private leadership channel name.
2. **Write the answers** with the Write tool to `setup-answers.json` in your scratchpad directory
   (outside the target, so the preview really writes nothing there). On a re-run, copy the owner
   block from the existing `.claude/brain.json`. Shape:

   ```json
   {"owner": {"name": "", "first_name": "", "person_id": "", "role": "", "company": "", "timezone": "", "week_starts": "monday"},
    "modules": ["brain-ingest", "..."],
    "confidential": {"globs": ["growth/**"], "channel_patterns": ["<additions only, e.g. private-exec-room>"]}}
   ```
3. **Preview.** Run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/setup_workspace.py --plan --answers <answers.json> --target <target>`.
   Show the owner a compact preview grouped by op: folders to create, files to write, files to
   merge (with what gets added), files kept as they are. Show `warnings` and `modules_missing`.
   If `status` is `error` (collisions), show them and stop: nothing was written.
4. **Ask for a yes.** "Create these N folders and M files?" Anything other than a clear yes means stop.
5. **Apply.** Run the same command with `--apply`. Report `written` and anything under
   `skipped_appeared_meanwhile`.
6. **Scheduled tasks.** For each entry in `scheduled_proposals`, propose it in one line (name,
   cron in the owner's timezone, what it does: read its `prompt_file`). Register each one only
   after a yes for that task, with the scheduled-task tool if this session has one (or `/schedule`),
   using the prompt file's contents as the task prompt. Never register a task the owner didn't approve.
7. **Connectors.** List `connectors` with `required: true` that the owner should enable, and how
   (Settings, Connectors). Don't test them here.
8. **Finish.** Run `brain doctor` from the target and show its status. Then tell the owner the
   three things to do next: fill in `SOUL.md` and `BRAND.md` (guided templates), list their first
   project with `/brain-core:new-project`, and run the first ingest if brain-ingest is enabled.

## Outputs

`.claude/brain.json`, `.claude/paths.json`, the context files (`CRITICAL_FACTS.md`, `CLAUDE.md`,
`RULES.md`, `SOUL.md`, `BRAND.md`, `MEMORY.md`, `INDEX.md`), `.claude/rules/`, `.claude/output-styles/`,
`system/schema/`, `todos/`, `.secrets/README.md`, `.gitignore`, every module's folders and
templates, and `system/run/pipeline.json` (brain-ingest's base pipeline plus every module's bricks).

## Rules

- **Never overwrite.** The script copies a template only when the target is missing, and merges
  JSON add-only. Don't work around it with Write or Edit.
- **Never ask for a secret.** If a module needs a token, point the owner at `.secrets/README.md`
  and let them create `.secrets/apis.env` themselves.
- **Never register a scheduled task, enable a connector or publish anything** without a yes for that item.

## Failure modes

| Symptom | Do |
|---|---|
| `answers are incomplete` | ask for the listed fields, rewrite the answers, re-plan |
| `collisions: nothing written` | a module wants a path key the workspace already maps differently; show both values and ask which module to drop or which key to rename |
| `module ... requested but not installed` | install it (`/plugin install <name>@claude-second-brain-os`), then re-run setup |
| doctor reports `module roots no longer exist` after a plugin update | re-run setup with the same answers; it refreshes the roots |
