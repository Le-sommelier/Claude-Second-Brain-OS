---
name: meeting-summarise
description: Transform brick. Turns every raw meeting transcript that has no summary yet into a structured note (purpose, updates, decisions, actions, risks, leadership feedback) beside it in raw/meetings/YYYY/YYYY-Www/, queued for the wiki and todo bricks. Also usable on demand - "summarise the meetings I just dropped in".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write
model: haiku
---

# Meeting summarise: transform brick

Follows the brick contract in `docs/module-contract.md` section 4 (stats-only return, pending-queue flags, single-line commands).

**Reads:** `raw/meetings/YYYY/YYYY-Www/mtg-*.txt` or `mtg-*.md` transcripts with no summary beside them, `people/_org.yaml` (names, aliases, tier), the project list (`projects/*/README.md`, titles and tags), `.claude/brain.json` (owner).
**Writes:** `raw/meetings/YYYY/YYYY-Www/<id>.summary.md`, where `<id>` is the transcript's file stem (`mtg-YYYY-MM-DD-<slug>`), using [`references/meeting-note-template.md`](references/meeting-note-template.md) exactly.
**State:** none. "Already summarised" means a `.summary.md` sits beside the transcript, or some note's `source_transcript` points at it.

## Steps

1. **Detect.** Run:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/detect_new_meetings.py
   ```
   If `count` is 0, return `skipped` with reason `"no new transcripts"`. A manual run for a wider window passes `--lookback-weeks N`.

2. **Summarise.** A fetched `.md` transcript already carries `participants`, `attendance` and `origin` in its frontmatter: reuse them rather than re-deriving.
   - **Small batch** (`fan_out` false): do the meetings yourself, one at a time.
   - **Large batch** (`fan_out` true): split into batches of up to 8 and spawn one Haiku subagent per batch, in parallel. Give each this file, the template and its transcript paths. Subagents write notes and return the note paths. They write nothing else.

3. **Hand over the queue.** The summary becomes the queue item for the wiki and todo bricks. For every meeting with `raw_has_flags: true`, write the raw paths to `system/run/payloads/raw-done.json` (a JSON array) and run, one command per line:
   ```bash
   brain flag --set wiki_processed=true --files-from system/run/payloads/raw-done.json
   brain flag --set todo_processed=true --files-from system/run/payloads/raw-done.json
   ```
   Do this only after the summary files are on disk. Otherwise the same meeting would be extracted twice.

4. **Return** exactly one JSON object:
   - `counts`: `{"transcripts": N, "notes_written": N, "raw_flags_flipped": N}`
   - `outputs`: the note paths
   - `observations`, when you saw any of these (one line each, no meeting content):
     - a speaker missing from `people/_org.yaml` (name and meeting id)
     - a project name, mentioned in 2+ meetings, with no `projects/<slug>/`
     - contradictory RAG for the same workstream on the same day
     - an unusual transcript format

## Writing a note

**Attendees and attendance**
- `attendees` is a list of person ids (`first-last`) from `people/_org.yaml`. Match speaker labels against names and `aliases`; drop room or device names and surname-less tokens. Unknown speakers are kept out of `attendees` and reported as an observation.
- **1:1s:** the title or folder names the other person. Resolve it through aliases, then add the owner.
- `attendance` describes the **owner**: `attended` when the owner speaks or is listed as present; `invited-absent` when the transcript header lists the owner as invited but they never speak; `not-invited` otherwise. The wiki brick turns this into a trust tier, so never guess upwards.

**Frontmatter**
- `id`: the transcript stem. `title`: the clean meeting title. `date`, `week` (`YYYY-Www`) from the transcript name.
- `project`: the one project slug the meeting is mostly about (a folder under `projects/`), else `null`. Cross-project meetings pick the dominant one and mention the others in Key Updates.
- `meeting_type`: one of `steerco`, `program-sync`, `project-sync`, `1-1`, `discovery`, `kickoff`, `workshop`, `retro`, `other`.
- `tags`: project slugs and topic words from the tag list in `.claude/brain/summarise.json` if the owner created one, else slugs only.
- `sensitivity`: `confidential` for performance or career 1:1 content, compensation, or people issues, and for any meeting whose title or channel matches the confidential patterns in `.claude/brain.json`. Otherwise `internal`. A confidential note wraps the whole body in `<!-- CONFIDENTIAL: redact-on-share -->` ... `<!-- /CONFIDENTIAL -->`.
- `source_transcript`: the transcript's workspace-relative path.
- `wiki_processed` and `todo_processed`: both `false`.

**Content**
- **Be specific, not balanced.** "Leadership wants earlier proof points before the next review" beats "constructive discussion".
- **Drop chit-chat.** A mostly social meeting still gets a short note with `signal_quality: low`. Never skip a meeting.
- **Leadership Feedback.** Fill it only when someone senior (by `tier` in `_org.yaml`) challenged, redirected or reset expectations. Never invent it. Delete the section if there is nothing.
- **Actions.** Name an owner on every action (a person's name, "the owner", or `unclear`). The todo brick depends on it. Write them as `- <owner>: <action> (due YYYY-MM-DD)`, due only when stated.
- **In-room captures.** One speaker label in a meeting that clearly had several people means a laptop-mic recording. Add `capture_mode: in-room`, summarise the full content, attribute nothing to individuals, and say so in Purpose.
- **Rewrites.** If a note with the same `source_transcript` exists, update it in place; never create a second one.
- **Never edit the transcript.** Raw is immutable.

## Failure modes

- Unreadable or empty transcript: skip it, add a warning, keep the rest of the batch.
- Unknown `project`: write `project: null` and add an observation. Do not invent a slug.
- A subagent returns no note path: count it as not written and warn.
