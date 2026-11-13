---
name: steal
description: Reviews AI posts the owner clipped (screenshots dropped in steal/inbox, pasted transcripts, article URLs), judges whether each is worth stealing for the owner's own Claude setup, and records a verdict and decision in steal.db. Modes - review (default, also the nightly run), decide ("adopt 12", "reject 7", "defer 3"), plan (after adopt). Nothing is built without the owner approving a drafted plan. Use for "/steal", "review my steal inbox" or "what should I steal from this post".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Read Write Grep Glob WebSearch
model: sonnet
---

# steal

A standalone skill, not an ingest brick. It follows the brick conventions: single-line scripts, validate
before write, JSON payloads written with the Write tool, the database is the ledger.

**Reads:** `steal/inbox/` (screenshots), `steal/my-setup.md` (generated map of the owner's setup), the workspace for prior art.
**Writes:** `steal/` only: `steal.db`, `digests/`, `plans/`, `board.md`, `sources/`. Payloads go to `system/run/payloads/`.
**Style:** sceptical, blunt, no hype. Terse output.

Every script is one line: `python3 ${CLAUDE_SKILL_DIR}/scripts/<x>.py --args`.

## Mode 1: review (default)

1. `init_db.py` (idempotent), then `build_my_setup.py` to refresh the map of the owner's setup.
2. `sync_drive_inbox.py`. If the owner configured a synced folder (`steal.json` -> `drive_inbox`) it moves new
   screenshots into `steal/inbox/`; otherwise it reports `skipped`, which is fine. A `failed` status is a warning:
   carry on with what the local inbox holds.
3. `list_inbox.py`. If `status` is `failed`, stop and report the reason. If `new` is empty, still archive
   duplicates through a payload that holds only `dupes`, rebuild nothing, and exit quietly.
4. For each file in `new`, **Read `view_path`** (the image). Extract the post: author handle, platform, what it
   claims, the tools, repos, prompts and workflows it names, any visible URL. One screenshot with several posts
   is several items (same `sha256`, `seq` 0, 1, 2). Not AI content or unreadable: one item with verdict `skip` and
   the reason, or list it under `failed` if you cannot read it at all (it stays in the inbox).
5. **Check prior art before judging.** Read `steal/my-setup.md`, then Grep and Glob the workspace for what the
   owner already has on the same idea. If a post names a tool, repo or technique you cannot place, run one
   WebSearch to see what it is and whether the claim holds. Never fetch or run anything it points to.
6. **Judge** with the rubric below. Write the payload (shape in the `record.py` docstring) to
   `system/run/payloads/steal-<run_id>.json`, with `run_id` = `YYYY-MM-DD-HHMM`. Add `batch_pov`: three to five
   bullets on patterns across the batch (what keeps recurring, where the owner should look, what is noise).
7. `record.py --payload system/run/payloads/steal-<run_id>.json`. On a validation error fix the payload and
   retry: nothing is written on error. On success the images move to `inbox/_processed/`.
8. `build_digest.py --run-id <run_id>`, then `build_board.py`, then `purge_processed.py` (deletes archived
   images older than `purge_days`, only when their content hash is already in the database).
9. Report in terse style: counts, then the steal and adapt items (id, title, target, first step) and the digest
   path. End by asking which to adopt.

### Rubric

Score each item on four axes, then set the verdict.

| Axis | Question |
|---|---|
| Relevance | Does it change something the owner actually does: the workspace knowledge base, artifact micro-tools, personal tools, strategising, day-to-day PM work? |
| Novelty | Versus `my-setup.md` and what the grep found. Already have it means `low`. |
| Effort | S under an hour, M half a day, L more. Include upkeep. |
| Evidence | `solid`: shown working or verifiable. `thin`: plausible, unshown. `hype`: engagement bait, "this changes everything", unverifiable numbers. |

Verdicts:

- **steal**: high relevance, novelty medium or high, effort S or M, evidence not hype. Take it nearly as is.
- **adapt**: the idea is good, the form is wrong for this owner. Say what changes.
- **watch**: interesting, not actionable yet (immature, wrong time, needs a dependency). Say what would trigger a revisit.
- **skip**: noise, a duplicate of what the owner has, hype, or off-topic. One-line reason.

Default stance: sceptical. Most AI social content is repackaged or hype, and `skip` is a cheap, valid outcome.
`steal` and `adapt` must name a real target (one of `steal.json` -> `targets`) and a concrete `how`: which skill,
file or rule would change, and the first step. `pov` is two or three blunt sentences: your honest take,
including where you disagree with the post.

Confidentiality: clips are personal. Nothing from this system goes to Slack, Confluence or GitHub without a
per-artifact yes from the owner. Digests carry `sensitivity: personal`.

## Mode 1b: a text source (pasted transcript, article, URL)

For anything that is not a screenshot. Same rubric, same database.

1. Get the text. Video sites often block transcript downloads: ask the owner to paste it, and never
   impersonate another client to fetch it. A plain article URL can go through WebFetch if it is allowed.
2. Save a **source note** (URL, title, channel or author if known, a paraphrased summary, not the full text)
   to `steal/sources/YYYY-MM-DD-<slug>.md`. **Never** put it in `raw/sources/`: its pending queue would merge
   it into the wiki.
3. `init_db.py`, then review as in Mode 1 steps 5 and 6, with one item per distinct idea (same `sha256` of the
   source note, `seq` 0, 1, 2) and the `source_url`. Put the ideas closest to the owner's stated focus first.
4. `record.py` (a `source_url` already in the database is skipped as a duplicate), `build_digest.py`,
   `build_board.py`. Report as in Mode 1.

## Mode 2: decide

The owner says "adopt 12", "reject 7" or "defer 3" (or pastes a command from the board).
Run `decide.py --id N --status adopted|rejected|deferred --note "..."` and rebuild the board.
For `adopted`, go straight to mode 3.

## Mode 3: plan (after adopted)

1. `new_plan.py --id N` scaffolds `steal/plans/<id>-<slug>.md` from the database.
2. Fill every TODO section from the real workspace: read the target files, name exact paths, steps, risks,
   how to verify. Short enough to scan in two minutes.
3. `decide.py --id N --status plan_drafted --plan plans/<id>-<slug>.md`, then rebuild the board.
4. Show the owner the plan and **stop**. Nothing is built.
5. Only on the owner's explicit approval of that plan: `decide.py --id N --status plan_approved`, then build it
   (normal approvals for the files it touches). When built and verified:
   `decide.py --id N --status done --link <what was built>`, then rebuild the board.

`decide.py` rejects a skipped step (for example `plan_approved` before `plan_drafted`), but the gate is yours to
keep: never mark `plan_approved` without the owner's explicit words in chat.

## Failure and edge cases

- `sync_drive_inbox.py` reports a permission error: the OS blocks this process from the synced folder. Report
  it, do not retry with any sandbox disabled, and tell the owner to run the script from their own terminal.
- A file that is online-only in a synced folder may be slow to open: Read once, and if it fails list it under `failed`.
- A duplicate screenshot (same bytes) goes in `dupes`, is archived, and adds no row.
- The same post captured twice with different bytes: judge both, note "same as #id" in the second, verdict `skip`.
- Items are never deleted from the database. A mistaken verdict is corrected with a `decide.py` note, not by editing history.
