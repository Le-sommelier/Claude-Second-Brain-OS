---
name: publish-digest
description: Draft a finished digest for the destination you configured (Confluence page, Slack message draft or email draft), show it, and send it only after your explicit yes for that artifact. Trigger on "publish the weekly digest" or "send the digest". Never runs on a schedule and never publishes on its own.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Read
model: haiku
---

# Publish digest: draft first, send on a per-artifact yes

No synthesis here: this skill moves an already-reviewed digest to one place. It is never scheduled and never triggered by another skill.

**Reads:** `digests/<kind>/<period>.md` and `.claude/brain/digests.json` (`publish`).
**Writes locally:** nothing. The digest file is never modified.
**Writes externally:** only after the explicit yes in step 4, and only the single artifact that was shown.

## Steps

1. **Resolve** the digest: default is this week's weekly digest. Accept `--period 2026-W45` and `--kind monthly`.
2. **Pre-flight.** Run:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/check_publishable.py --period 2026-W45
   ```
   On `ok: false`, stop and report the errors: digest missing, placeholders left in it, confidential content in it, or no destination configured. Do not guess a destination, and never pick one the owner did not configure. Confidential content never leaves the workspace through this skill.
3. **Draft and show.** Print the destination, the title from the pre-flight (`title`), the target (space and parent page, channel, or recipients), and the full body that would go out. For Slack and email, create the connector's **draft** (a Slack message draft, an Outlook draft): drafts are private and reversible. For Confluence, which has no draft step here, show the full preview in chat and create nothing yet.
4. **Ask once, per artifact:** "Publish this digest to <destination/target>? (yes/no)". Wait for a clear yes in chat. A yes for an earlier digest, another destination or "always publish" is not a yes. Silence, an edit request or a question is not a yes: revise the draft and ask again.
5. **Send only on yes**, using the one connector path:
   - Confluence: create the page under `parent_page_id` in `space` with `title`, or update the page with the same title in place (never overwrite a page whose content you did not create; show the diff first).
   - Slack: send the drafted message to the configured channel.
   - Email: send the draft to the configured recipients.
6. **Report** the URL or message reference and nothing else. If the owner says no, leave the draft or delete it on request.

## Hard rules

- Never publish without a yes for this exact artifact. Never publish from a scheduled run.
- Never publish a file with template placeholders or confidential markers.
- Never modify the local digest. Never post anywhere the owner did not configure.
- A missing connector is a stop: report it, do not fall back to another destination.
