# Changelog

## 0.1.0 — unreleased
- First public cut of Claude-Second-Brain-OS: 15 modules (core, orchestrator, Slack / Teams /
  Confluence / notes ingest, summarise, wiki, digests, growth, mentoring, stakeholders, learning
  loop, steal list, grill).
- Markdown is the only source of truth, with no HTML views. `system/kb.db` is a generated,
  git-ignored SQLite index over it. One architecture diagram in `docs/assets/`.
- Setup wizard that previews before writing and never overwrites.
- Fictional sample workspace (Alex Morgan at Fernhill) for tests and demos.
