---
type: system
purpose: fast-load anchor, read at every session start (~150 tokens)
last_updated: {{TODAY}}
---

# Critical facts

- **Owner**: {{OWNER_NAME}} (`{{OWNER_PERSON_ID}}`), {{OWNER_ROLE}} at {{COMPANY}}. Timezone {{TIMEZONE}}.
- **Workspace root**: the folder holding `.claude/brain.json`. Every script finds it from there; `brain root` prints it.
- **Paths**: `.claude/paths.json` is the only path map. Never hardcode a path.
- **Knowledge base**: `projects/<slug>/` (append-only facet logs + `decisions/`), `people/`, `topics/`, cited by IDs from `raw/`. Query with `brain kb`. Schema in `system/schema/`.
- **Raw is immutable**: `raw/<kind>/YYYY/YYYY-Www/<kind>-YYYY-MM-DD-<slug>.md`.
- **Modules**: {{MODULES_LIST}}. The ingest run order lives in `system/run/pipeline.json`.
- **Learning store**: `MEMORY.md`, newest entries at the **top**.
- **Confidential**: {{CONFIDENTIAL_GLOBS}} and Slack channels matching {{CONFIDENTIAL_CHANNELS}}. Never quoted into a shared output.
- **Scheduled tasks**: read the registry at runtime. Never trust a list in a document.
- **Secrets**: `.secrets/apis.env`. Load as env vars; never read aloud, echo or commit.
- **Publishing**: nothing goes to Slack, Confluence, email or GitHub without a per-artifact yes from {{OWNER_FIRST_NAME}}.
