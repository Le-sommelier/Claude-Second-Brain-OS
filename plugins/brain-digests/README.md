# brain-digests

Weekly and monthly digests built from what the ingest already produced, with a publish step that never fires on its own.

## Install

```
/plugin install brain-digests --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

| Skill | What it does | Model |
|---|---|---|
| `weekly-digest` | Reads the week's meeting summaries, Slack files and logged project facts; drafts `digests/weekly/YYYY-Www.md` (overview, one row per project, decisions and asks, sources); validates it; stops. | Sonnet |
| `monthly-digest` | Deterministic rollups: `projects/<slug>/rollups/YYYY-MM.md` per project and `digests/monthly/YYYY-MM.md`. No model. | Haiku |
| `publish-digest` | Drafts the digest for the destination you configured (Confluence page, Slack draft, email draft) and sends only after your explicit yes for that artifact. | Haiku |

## Connectors (all optional, only for publishing)

Confluence (Atlassian), Slack, Microsoft 365 Outlook. Digest generation needs none.

## Commands

`/brain-digests:weekly-digest [--week YYYY-Www]`, `/brain-digests:monthly-digest`, `/brain-digests:publish-digest`.

## Confidentiality

Confidential meetings, Slack channels, entries and decisions appear at signal level only: no names, amounts, ratings or quotes. The validator rejects a digest that carries confidential markers, and the publish pre-flight refuses one. Nothing is published without a per-artifact yes.

## Configuration

`.claude/brain/digests.json` (copied once by setup, never overwritten): which projects to include (default: every folder under `projects/`), an optional tags filter, and the publish destination with fictional defaults (Confluence space `PROD`, Slack `#product-team`, an example email address) to replace with yours.

## Scheduled tasks it proposes

- `brain-weekly-digest`: Fridays 15:00, drafts and stops.
- `brain-monthly-digest`: the 1st at 08:00, runs the rollups.

Registered only if you say yes during setup. Neither ever publishes.

## Outputs

`digests/weekly/`, `digests/monthly/`, `projects/<slug>/rollups/`.

See `docs/module-contract.md`.
