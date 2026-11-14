# {{OWNER_FIRST_NAME}}'s workspace

{{OWNER_NAME}}'s product-management second brain ({{OWNER_ROLE}}, {{COMPANY}}), built on
claude-second-brain-os. Read this file first.

## Read order (every session)

The brain-core session-start hook injects this automatically, tiered by model (Haiku: anchor and
todos; Sonnet: adds rules, voice and the head of memory; Opus: the full bundle). If it didn't
run, read manually in this order:

1. `CRITICAL_FACTS.md`: the anchor. Always.
2. `RULES.md`: confirmed conventions (must-follow).
3. `SOUL.md`: who {{OWNER_FIRST_NAME}} is, what they own, who they write for.
4. `BRAND.md`: voice, tone, banned words, format defaults.
5. `INDEX.md`: map of the workspace.
6. Head of `MEMORY.md`: **newest entries are at the top**.
7. `.claude/CLAUDE.md`: agent-only behaviour.

A folder-local `CLAUDE.md` wins over this file for its own subtree.

## Hard rules (the ones with real downside)

- **Secrets** live in `.secrets/apis.env`. Load env vars before an external call. Never hardcode, never echo the file.
- **Confidential content** ({{CONFIDENTIAL_GLOBS}}, any file with `sensitivity: confidential`, Slack channels matching {{CONFIDENTIAL_CHANNELS}}) is never quoted into a shared artifact. Full posture: `.claude/rules/confidential.md`.
- **Never publish without a per-artifact approval**: Confluence, Slack, email, GitHub. Drafting is always fine; persisting where other people can see is not.
- **Never overwrite populated content**: project pages, meeting summaries, wiki pages. Append or update a section.
- **Logs are append-only.** Use `brain kb append`; a change is a new entry with the same ID.

## Where things live

`.claude/paths.json` is the canonical path map: **read it, never hardcode a path.** `brain doctor`
checks that every key resolves. For the folder map and "where do I find X", read `INDEX.md`.

## Automation

The scheduled-task registry is the only source of truth for what runs. Read it at runtime. If a
document disagrees with the registry, the document is wrong.

## How this workspace evolves

- `MEMORY.md` is the single learning store. Append inline only to flag something worth keeping;
  if the learning-loop module is installed, its nightly job does the routine capture.
- A pattern promotes from `MEMORY.md` into `RULES.md` after it fires 3 times across distinct
  sessions, and only with {{OWNER_FIRST_NAME}}'s nod.
- A structural change means `INDEX.md` and `.claude/paths.json` are updated in the same session.
  `brain doctor` catches it if you forget.
