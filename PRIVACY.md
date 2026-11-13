# Privacy

claude-second-brain-os has no server and collects nothing. Everything it fetches lands as files in a folder
you own. What leaves your machine is what Claude Code itself sends to the model while working,
plus any connector calls (Slack, Microsoft 365, Atlassian) made with your own credentials.

If you keep your workspace in git, keep that repo private: it will hold your meetings, Slack
messages and career notes. The workspace template ships a `.gitignore` for secrets and generated files.
