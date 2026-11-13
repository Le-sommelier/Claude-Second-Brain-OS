# Rules — confidential content

**Load when working with any of:**
- paths matching {{CONFIDENTIAL_GLOBS}} (career, reviews, mentoring, manager feedback)
- any file whose frontmatter says `sensitivity: confidential` or `redact_content: true`
- Slack content from channels matching {{CONFIDENTIAL_CHANNELS}}
- `.claude/.session-log/` (operational, never for output)

The patterns live in `.claude/brain.json → confidential`; edit them there, not here. This rule
applies on top of every other rule.

## Hard rules

- **Never quote confidential content verbatim** in anything meant for someone other than {{OWNER_FIRST_NAME}}: Slack drafts, wiki pages, digests, Confluence drafts, emails, exec decks, system reviews. Summarise or abstract; no direct quotes.
- **Never put it on a shared surface**: wiki pages, digests, Confluence, Slack, GitHub.
- **No names, figures, ratings or personal details** from a confidential source in any output {{OWNER_FIRST_NAME}} hasn't pre-approved. Use generic terms ("a peer", "leadership").
- **Fresh approval per artifact.** Anything sourced from confidential content needs an explicit "publish this" for that artifact; a general go-ahead does not cover it.
- **Growth content stays in its folder.** Digests, reviews and wiki updates skip it. If a skill asks you to pull it into a shared output, refuse and say why.

## What is still fine

- Reading it, and helping {{OWNER_FIRST_NAME}} think with it.
- Drafting a self-review, a development plan or 1:1 prep **for {{OWNER_FIRST_NAME}}'s own use**, clearly marked confidential and routed nowhere.
- Comparing across review cycles to spot patterns for reflection.

## How confidential material is stored

- Ingested confidential items carry `sensitivity: confidential` (and `redact_content: true` for channels) in frontmatter.
- The body sits between `<!-- CONFIDENTIAL: redact-on-share -->` and `<!-- /CONFIDENTIAL -->`.
- Downstream skills write signal-level mentions only ("the leads channel discussed sequencing; see the source"), never quotes.
- `brain kb append` tags entries and decisions from confidential sources with `sensitivity: confidential`.

## Git

The workspace may be a local git repo. Never add a remote that would push confidential folders
anywhere, and never commit `.secrets/`.

## When in doubt

Picture the content projected in front of the wrong audience. If that makes you wince, treat it
as confidential.
