---
type: system
purpose: fast-load anchor, read at every session start (~150 tokens)
last_updated: 2026-10-19
---

# Critical facts

- **Owner**: Alex Morgan (`alex-morgan`), Senior Product Manager at Fernhill. Timezone Europe/London.
- **Workspace root**: the folder holding `.claude/brain.json`. Every script finds it from there; `brain root` prints it.
- **Paths**: `.claude/paths.json` is the only path map. Never hardcode a path.
- **Knowledge base**: `projects/<slug>/` (append-only facet logs + `decisions/`), `people/`, `topics/`, cited by IDs from `raw/`. Query with `brain kb`. Schema in `system/schema/`.
- **Raw is immutable**: `raw/<kind>/YYYY/YYYY-Www/<kind>-YYYY-MM-DD-<slug>.md`.
- **Modules**: brain-core, brain-ingest, brain-ingest-slack, brain-ingest-teams, brain-ingest-confluence, brain-ingest-notes, brain-summarise, brain-wiki, brain-digests, brain-growth, brain-mentoring, brain-stakeholders, brain-learning-loop, brain-steal-list, brain-grill. The ingest run order lives in `system/run/pipeline.json`.
- **Learning store**: `MEMORY.md`, newest entries at the **top**.
- **Confidential**: `growth/**` and Slack channels matching `*-leadership*`, `*-leads`, `*-lead-*`, `*-exec*`, `exec-*`, `leads-*`. Never quoted into a shared output.
- **Scheduled tasks**: read the registry at runtime. Never trust a list in a document.
- **Secrets**: `.secrets/apis.env`. Load as env vars; never read aloud, echo or commit.
- **Publishing**: nothing goes to Slack, Confluence, email or GitHub without a per-artifact yes from Alex.
