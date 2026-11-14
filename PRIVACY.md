# Privacy

claude-second-brain-os has no server and collects nothing. Everything it fetches lands as files in a folder
you own. What leaves your machine is what Claude Code itself sends to the model while working,
plus any connector calls (Slack, Microsoft 365, Atlassian) made with your own credentials.

## What it stores about your own sessions

Two things read or copy your Claude Code session transcripts. Both stay on your machine.

- **brain-core** copies the full transcript of a session into
  `.claude/.session-log/transcripts/` just before Claude Code compacts it, and keeps the 30 most
  recent. It also keeps one line per session stop (time, session ID, transcript path) in
  `.claude/.session-log/sessions.jsonl`. The workspace `.gitignore` excludes that folder.
- **brain-learning-loop**, if you install it and say yes to its nightly job, reads this
  workspace's transcripts from `~/.claude/projects/` to write `MEMORY.md` entries and proposals.
  It keeps your opening ask, your steering turns and the final answer; tool output and model
  reasoning are dropped, and a session that touched a confidential path is listed without content.

Transcripts contain whatever you and the agent read during a session, including confidential
material. Delete `.claude/.session-log/` whenever you like; nothing depends on it.

## If you keep the workspace in git

Keep that repo private: it will hold your meetings, Slack messages and career notes. The
workspace template ships a `.gitignore` for secrets and generated files.
