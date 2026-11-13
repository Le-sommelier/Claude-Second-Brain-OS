---
name: ingest-confluence
description: Fetch brick (lane atlassian). Mirrors the Confluence spaces, pages, labels and CQL queries listed in .claude/brain/confluence-watch.json into raw/confluence, fetching only new or changed page versions. A changed version rewrites the file and resets wiki_processed to false. Read-only, verbatim.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write mcp__*__searchConfluenceUsingCql mcp__*__getConfluencePage
---

# Confluence: fetch brick

Follows `docs/module-contract.md` §4. Verbatim fetch, so it runs on Haiku. It never posts, comments
or edits in Confluence, and it needs no run context: the watch list and the sync state decide the work.

**Reads:** Atlassian connector (`searchConfluenceUsingCql`, `getConfluencePage`), by their bare names. Never read `.secrets/`.
**Writes:** `raw/confluence/YYYY/YYYY-Www/conf-YYYY-MM-DD-<slug>.md`
**State:** `system/run/confluence-state.json`, written only by `scripts/sync.py`
**Config:** `.claude/brain/confluence-watch.json` (spaces, page IDs, labels, CQL, decision detection, confidential labels)

## Steps

1. **Plan.** `python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py plan` prints `{since, queries[], max_pages}`. If the config has no spaces, labels, page IDs or CQL (`queries` is empty), return `skipped` with reason `"confluence-watch.json is empty: add spaces or labels to watch"`.
2. **Search.** Run each query with `searchConfluenceUsingCql` and paginate to the end. Merge the results into one array of `{"id","title","version","lastModified","space"}` (take `version` as the integer version number when the result has it; leave it out otherwise). Write it with the Write tool to `system/run/payloads/confluence-listing.json`, then run `python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py diff --listing system/run/payloads/confluence-listing.json`. It prints `to_fetch` (reason `new`, `version_changed` or `modified`), `deferred` and `unchanged`.
3. **Fetch each page in `to_fetch`.** Call `getConfluencePage` with the body in markdown. Write `system/run/payloads/confluence-<id>.json` with `id`, `title`, `url` (web URL), `space` (key), `version` (integer), `last_modified` (ISO), `labels` (array of label names) and `body` (the page markdown, copied exactly: condense nothing, invent nothing, never fill a gap with a plausible value). Then run `python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py write --payload system/run/payloads/confluence-<id>.json`.
   - The script refuses an empty, stub or placeholder body and writes nothing. Fetch the page again and copy its real content. If you cannot get the body, skip the page and add a warning: it stays in the diff and is retried next run. Never write a page you did not fetch.
   - Never write `conf-*.md` yourself with the Write tool: only `sync.py write` touches `raw/confluence/`.
   - Every new or changed version resets `wiki_processed: false`. The same version with the same body reports `unchanged` and touches nothing.
   - Pages labelled with a configured confidential label are stored inside confidential markers with `sensitivity: confidential`; never quote them anywhere shared.
   - Pages matching the decision-page rules get a `decision-page` tag (just a tag: the wiki step decides what a decision is worth).
4. **Finish.** If every page in `to_fetch` was written (or reported unchanged) and `deferred` is 0, run `python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py finish`. Otherwise skip it so the next run re-lists the same window.
5. **Return** one brick-contract JSON object: `counts` `{"listed","fetched","created","rewritten","unchanged","deferred"}` copied from script output, `outputs` the written paths, `observations` one line per decision page found (title only). No page content in the return.

## Failure modes

Connector offline -> `skipped` with the reconnect hint. A page that fails verbatim checks or the body guard -> `warnings`, status `partial`. More than `max_pages_per_run` changed -> the rest are `deferred` and picked up next run.
