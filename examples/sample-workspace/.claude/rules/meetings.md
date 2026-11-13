# Rules — meetings

Load when working under `raw/meetings/**`.

## Layout

| What | Where | Format |
|---|---|---|
| Raw meeting (transcript or notes) | `raw/meetings/YYYY/YYYY-Www/mtg-YYYY-MM-DD-<slug>.md` | markdown with frontmatter |
| Summary | same folder, `mtg-YYYY-MM-DD-<slug>.summary.md` | markdown with frontmatter |

When asked about a meeting, **start from the summary**: it already carries attendees,
decisions and actions. Open the raw item only when the summary lacks the detail.

## Hard rules

- **Never edit a raw item's body.** Raw is append-only input; only frontmatter flags change.
- **Never overwrite a populated summary.** Append a section or flag the discrepancy.
- **ISO week folders**: `2026/2026-W46/`, two-digit week, capital W.
- **Frontmatter** on every summary: `id, date, title, attendees, attendance, project, meeting_type, wiki_processed`. `attendance` maps person IDs to `attended | invited-absent | not-invited`; it drives the trust tier.
- **Don't duplicate the pipeline.** If someone asks to "summarise this meeting", check whether the summary already exists before writing one.
