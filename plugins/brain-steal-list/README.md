# brain-steal-list

A nightly review of ideas you clipped from other people's AI setups. Each clip is judged against a generated map
of your own setup and gets a verdict: **steal**, **adapt**, **watch** or **skip**. You decide; if you adopt
something, it drafts a plan, and **nothing is built until you approve that plan**.

## Install

```
/plugin install brain-steal-list --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

## How it works

1. Screenshot a post on your phone and save it into `steal/inbox/`. Optionally point
   `.claude/brain/steal.json -> drive_inbox` at a synced folder (Google Drive, iCloud, Dropbox) and the review
   moves new images from there first. Unset, that step is skipped.
2. The nightly task (or `/brain-steal-list:steal`) reads each image, checks prior art in your workspace and in
   `steal/my-setup.md`, and records a verdict with a blunt point of view. Text sources (a pasted transcript, an
   article) go through the same rubric as notes in `steal/sources/`.
3. You read `steal/digests/<run>-steal-digest.md` or open `steal/board.md` (a markdown status board with the
   decision command on each row).
4. Decide with `/brain-steal-list:steal adopt 12`, `reject 7` or `defer 3`. Adopt drafts `steal/plans/<id>-<slug>.md`.

The decision pipeline is `proposed -> adopted -> plan_drafted -> plan_approved -> done`, or `rejected` or
`deferred`. `plan_approved` is only reachable from `plan_drafted`, and only on your explicit say-so.

## The map of your own setup is generated

`steal/my-setup.md` is written by `build_my_setup.py` from your workspace: enabled modules, the headings of
`RULES.md`, and the names and descriptions of the skills, commands, agents and hooks in the folders listed in
`steal.json -> setup_scan`. Confidential files are skipped. Nobody edits it; the review refreshes it every run.

## Connectors

None required. The optional synced-folder move is a plain file copy with a hash check.

## Outputs (all under `steal/`)

`steal.db` (SQLite: items, verdicts, decisions, decision log, runs), `digests/`, `plans/`, `sources/`,
`board.md`, `my-setup.md`. Images are archived to `inbox/_processed/` and deleted after `purge_days` (14)
once their row is in the database. Payloads go to `system/run/payloads/`.

## Scheduled task proposed at setup

`brain-steal-review-nightly`, 22:00 daily: runs mode 1 of the `steal` skill, never adopts, plans or publishes.

## Scripts

`init_db.py`, `sync_drive_inbox.py`, `list_inbox.py`, `record.py` (validate first, write second),
`decide.py` (enforces the plan gate), `new_plan.py`, `build_digest.py`, `build_board.py`,
`purge_processed.py`, `build_my_setup.py`. Each is one `python3` line.

## Confidentiality

Clips are personal: digests carry `sensitivity: personal` and nothing is published anywhere without a
per-artifact yes. See the [module contract](../../docs/module-contract.md).
