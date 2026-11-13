# Rules — sources (web clips)

Load when working under `raw/sources/**` or processing an inbound web clip.

## What this folder is

External clips (articles, posts, screenshots) that may feed projects and topics. Each clip is a
markdown file with frontmatter in `raw/sources/YYYY/YYYY-Www/src-YYYY-MM-DD-<slug>.md`.

## Hard rules

- **Frontmatter required**: `clipped: YYYY-MM-DD`, `url:`, `wiki_processed: false`. The flag flips to `true` once the clip has been merged.
- **Don't modify the clip body.** Frontmatter is the only mutable part.
- **Latest first** when there's a backlog. Clips still pending after 48 hours show up in the attention list.
- **Merge target**: a clip feeds a pointer (`[[src-...]]`) in the relevant project or topic, and facts go in through `brain kb append`. Never paste the clip's text into a page.

## Capture conventions

- The slug names the topic, not the source ("agent-memory-patterns", not "someones-blog-post").
- Attribution at the top of the body: `> Source: <author>, <publication>, <date>`.

## When not to process

- `wiki_processed: true`: already done.
- Older than 30 days and still pending: ask {{OWNER_FIRST_NAME}} first; it may have been skipped on purpose.
