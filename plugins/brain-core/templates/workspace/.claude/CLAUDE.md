# .claude/CLAUDE.md — agent-only behaviour

Read **after** the root `CLAUDE.md`. Rules that apply to the agent, not to people reading the workspace.

## Path resolution

- Canonical path map: `.claude/paths.json`. Scripts read it through `brainos.workspace.path()`; skills call `brain` instead of reaching into another plugin's files.
- Never write an absolute path into a script, a skill or a doc.
- Case is real. A case mismatch works on a laptop and breaks on a case-sensitive host.

## Output style routing

Pick by the artifact's destination, not the prompt's politeness.

- Default: `.claude/output-styles/terse.md` (no preamble, no closing summary, action first)
- Exec-bound (steering group, monthly update, leadership email): `.claude/output-styles/exec-update.md`
- Wiki or Confluence-bound pages: `.claude/output-styles/wiki-page.md`

## Path-scoped rules (load on match)

| Working in... | Also read... |
|---|---|
| `raw/sources/**` or web clip processing | `.claude/rules/sources.md` |
| anything touching Confluence | `.claude/rules/confluence.md` |
| anything touching Slack | `.claude/rules/slack.md` |
| `raw/meetings/**` | `.claude/rules/meetings.md` |
| `*.py`, `*.sh`, `*.js`, `*.ts`, or any skill `scripts/` folder | `.claude/rules/coding.md` |
| {{CONFIDENTIAL_GLOBS}}, any file with `sensitivity: confidential`, confidential channels | `.claude/rules/confidential.md` |

## Persona routing

When a task matches, work as the brain-core agent named here:

| Task shape | Agent |
|---|---|
| Research, comparison, "what's the state of X", "what did we decide about Y" | `brain-core:pm-researcher` |
| Draft a PRD, feature brief, requirements doc | `brain-core:prd-writer` |
| Exec update, steering-group prep, monthly report | `brain-core:exec-update` |

Other modules add their own agents; don't invent one that isn't installed.

## Model routing (cost discipline)

Default to the cheapest model that can do the job.

| Task shape | Model |
|---|---|
| Mechanical: renames, find/replace, JSON or frontmatter edits, verbatim fetches | Haiku |
| Scoped reading and synthesis, drafting one section, most skill workflows | Sonnet |
| Real planning, cross-domain trade-offs, exec synthesis, architecture | Opus |

- Delegate down: when the next unit of work is clearly cheaper-tier, spawn a subagent on that model instead of doing it inline. Stay inline when the work is a few tool calls or needs this conversation's context.
- Brief a subagent fully (it sees only the prompt), ask for a short report, relay it.
- **Caps:** Haiku never spawns subagents. Max spawn depth is 2. A subagent that needs a smarter model returns to its parent; it never escalates itself.

## Unattended runs

Scheduled tasks run with nobody to approve a prompt. Every Bash call is one single-line,
allow-listable command (`brain ...` or `python3 <script> --args`): no heredocs, pipes, `&&`,
loops or `python3 -c`. Payloads go to `system/run/payloads/` through the Write tool.

## Session end

When {{OWNER_FIRST_NAME}} says "done", "wrap up" or "save state":

1. Update `todos/todo.md` and `todos/done.md` for the tasks touched.
2. If the folder structure changed: update `INDEX.md` and `.claude/paths.json`, then run `brain doctor`.
3. Never promote `MEMORY.md` into `RULES.md` without {{OWNER_FIRST_NAME}}'s nod.

## What this file does not contain

Secrets (`.secrets/`), voice (`BRAND.md`, `SOUL.md`), filename conventions (`RULES.md`), the
workspace map (`INDEX.md`). Keep it about agent behaviour.
