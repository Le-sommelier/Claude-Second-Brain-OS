# Security

This system reads your work data (Slack, Teams, Confluence, notes) into local markdown. Its
defaults are built to keep that data local:

- **Ingest is read-only.** No ingest module posts, reacts, comments or edits in any external system.
- **One skill writes externally: `publish-digest`** (brain-digests). It sends one digest to the
  destination you configured (a Confluence page, a Slack channel or email recipients), and only
  after a yes for that artifact in chat. It is never scheduled and never called by another skill.
  No other module writes outside the workspace.
- **Secrets** live in `.secrets/apis.env` in your workspace, git-ignored. Scripts never echo them.
- **Confidential content** (growth, leadership channels, anything marked `sensitivity: confidential`)
  is stored locally and never quoted into digests, the wiki or any shared surface.

## Ingested content is untrusted

Slack messages, meeting transcripts, Confluence pages, dropped notes and clipped posts are written
by other people and stored verbatim. Some of the skills that later read them can write files.
Text in a source that addresses the agent ("ignore your rules", "post this", "run this command",
"add this to RULES.md") is a prompt injection attempt, whether or not it was meant as one.

What the system does about it:

- The workspace rules (`RULES.md`, "External content is data") tell every session to treat
  anything under `raw/`, `inbox/` and `steal/` as material to summarise or cite, never as instructions.
- Fetch bricks store text and return counts only. Source text does not pass through the orchestrator.
- Skills are limited by `allowed-tools` to their own scripts, the `brain` CLI and local file tools.
  None of the skills that read ingested text is allowed a connector write tool.
- Rules and scheduled jobs change only through you: the learning loop proposes, you promote.

What it cannot do: a model can still be misled by what it reads. Review AI-written entries
(they stay `by: ai` until you confirm them), read a digest before you publish it, and do not
watch channels or spaces where people you don't trust can post.

## What a scheduled run is allowed to do

Each skill allow-lists single-line calls to its own scripts. The ingest orchestrator is the
exception: it is allowed `python3` in general, because script bricks are run by the command
recorded in `system/run/pipeline.json`. Setup writes that file from the installed modules.
Treat it like code: a command added there by hand will be run by the daily ingest.

## Reporting

Found a vulnerability, or a way for content to escape those boundaries? Open a private security
advisory on the repository rather than a public issue.
