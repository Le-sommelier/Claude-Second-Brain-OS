---
name: weekly-digest
description: Build the weekly digest from the week's meeting summaries, Slack files and logged project facts already processed by the ingest. Writes a short, structured local draft to digests/weekly/ and stops. Publishing is a separate skill (publish-digest) and needs your explicit yes. Trigger on "weekly digest", "weekly recap", or the Friday scheduled task.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
model: sonnet
---

# Weekly digest

Reads what the ingest already produced and writes one short digest. No transcript summarising happens here (that is `brain-summarise`), and nothing is published here (that is `publish-digest`).

**Reads:** `raw/meetings/**/*.summary.md`, `raw/slack/YYYY/YYYY-Www/*.md`, `projects/<slug>/*.md` logs and `decisions/`, `.claude/brain/digests.json`.
**Writes:** `digests/weekly/YYYY-Www.md` (updated in place if it exists). Nothing else.

## Steps

1. **Prepare.** Run:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/run_weekly_recap.py
   ```
   Add `--week 2026-W45` for another week. The script prints a manifest: week window, output path, summaries, Slack files, and per project the current RAG, open-risk count, entries and decisions logged in the window. If it returns `requires_user_confirmation: true` (exit 3), report `stop_reason` and finish: the ingest has not run, or the tags filter excludes everything.
2. **Read.** The summaries listed in `summaries`; the Slack files in `slack_files` that are not confidential; `projects/<slug>/README.md` where a project needs more context. Confirm anything surprising with `brain kb show <id>`. The previous digest (`previous_digest_path`) shows what was promised last week.
3. **Draft** using [`references/output-template.md`](references/output-template.md): same section order, same headings.
   - **Overview:** prose only, 2-3 sentences. Explicit senior asks or steering signals belong here, not buried in the table.
   - **Project status:** one row per project in the manifest. RAG comes from `current_rag`, else `?`. Cells hold at most two short bullets. A project with no activity says "No activity this week." in This week and leaves Next and Key risk blank.
   - **Decisions and asks:** decisions logged this week (state whether `proposed` or `accepted`, `by: ai` ones are unconfirmed) and asks the owner must answer.
   - **Sources:** the real counts, the previous digest path.
   - Cite `[[id]]` (meeting ids, `DEC-...`, `<project>/<ID>`) for every claim. Synthesise to the sharpest signal; do not paste summary text. Never invent content.
4. **Confidential sources: signal level only.** For anything flagged `confidential: true` in the manifest, or any entry or decision with `confidential: true`: say that a topic was discussed or a state changed, never names, amounts, ratings or quotes, and do not name the meeting by its title. Do not read confidential bodies unless the owner asks you to think with them, and even then keep them out of the digest.
5. **Write** the digest to `output_path`, then validate:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/validate_weekly_digest.py --digest digests/weekly/2026-W45.md --week 2026-W45
   ```
   Fix every error and re-run. Warnings (vague phrases, missing citations) are worth fixing too.
6. **Present** the digest to the owner and **stop**. Do not publish. To publish, the owner asks for `publish-digest`.

## Rules

- Section order and headings exactly as the template; the validator enforces them.
- Digest frontmatter: `type: digest`, `period`, `by: ai`.
- Exact dates for commitments and milestones. "Ongoing" and "alignment continues" are not facts.
- Optional filters live in `.claude/brain/digests.json` (`projects`, `tags_filter`).

## Failure modes

- No summaries but logged facts exist: proceed, and say in Sources that no summaries were found.
- Digest already exists for the week: update it in place, keeping any section the owner marked with `<!-- human -->`.
- Validator errors you cannot fix (for example a project row for a project with no data): report them rather than weakening the check.
