# Rules — Slack

Load when working on Slack ingest, Slack-bound drafts, or anything under `raw/slack/**`.

## Truth sources

- Access is through the Slack connector. Use its tools directly; never write code against the Slack API.
- Ingested files: `raw/slack/YYYY/YYYY-Www/slack-YYYY-MM-DD-<channel-slug>.md`, one per channel per posting day. The watched-channel list lives in the Slack module's config under `.claude/brain/`.

## Hard rules

- **Don't post, react or edit in Slack** without {{OWNER_FIRST_NAME}}'s explicit approval for that message. Drafting is fine.
- **Cite permalinks**, not message text alone. A claim needs a permalink.
- **Deduplicate by permalink**, never by text. An edited message keeps its permalink.
- **No private DMs** unless explicitly asked.
- **Confidential channels** (matching {{CONFIDENTIAL_CHANNELS}}) get `redact_content: true` and `sensitivity: confidential`; their body is stored locally inside confidential markers and never quoted downstream. See `confidential.md`.

## Drafting Slack messages

- One thought per message. Threads are fine; walls of text are not.
- Slack voice = the `BRAND.md` voice, about a third shorter. Same banned words.
- Emoji sparingly.
- Match the channel: a leads channel is direct; a social channel is lighter.
