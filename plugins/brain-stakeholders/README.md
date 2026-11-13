# brain-stakeholders

People pages, the org chart, a stakeholder map and 1:1 prep and drafts. Notes about people are confidential.

## Install

```
/plugin install brain-stakeholders --marketplace YOUR-ORG/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

| Skill | What it does |
|---|---|
| `person` | Update a people page from evidence (ratings, confidential notes, dated evidence), keep `_org.yaml` valid; never touches human-fenced text |
| `stakeholder-map` | Influence/interest grid with relationship health and who is overdue, as markdown (mermaid chart plus table) |
| `one-on-one-prep` | Agenda for a 1:1 from the last entries, open actions and recent mentions |
| `one-on-ones` | Detect roster 1:1s, draft short notes, queue them locally, push onto the person's page only on your yes per draft |

**Connectors:** none. Transcripts arrive through the ingest modules; this module reads `raw/meetings`.

## Files

- `people/<first-last>.md` pages, created with `brain new person`. Shape and who-writes-what: [references/page-shape.md](references/page-shape.md).
- `people/_org.yaml` the org chart (`org.py check|add|tree`).
- `.claude/brain/one-on-one-roster.json` whom to draft 1:1s for (copied from a template; edit it).
- `growth/one-on-ones/{ledger.json, queue/, payloads/}` local state, confidential.
- `people/_stakeholder-map.md` generated, confidential.

**Scheduled tasks:** none proposed. The `one-on-ones` draft mode is registered as a `derive` brick, so the orchestrator runs it when installed. Pushing is always interactive.

Scripts are stdlib Python 3.11+. See the [module contract](../../docs/module-contract.md).
