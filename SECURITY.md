# Security

This system reads your work data (Slack, Teams, Confluence, notes) into local markdown. Its
defaults are built to keep that data local:

- **Connectors are read-only.** No module posts, reacts, comments or edits in any external system.
- **Nothing publishes without a per-artifact yes** from the owner in chat.
- **Secrets** live in `.secrets/apis.env` in your workspace, git-ignored. Scripts never echo them.
- **Confidential content** (growth, leadership channels, anything marked `sensitivity: confidential`)
  is stored locally and never quoted into digests, the wiki or any shared surface.

Found a vulnerability, or a way for content to escape those boundaries? Open a private security
advisory on the repository rather than a public issue.
