---
name: growth-signals
description: Mine your recent work (meeting summaries, project decisions, digests, feedback received) for evidence against your career framework, queue it for your triage, and promote what you accept. Use for "mine evidence", "run growth signals", "what did I do this week that counts", "promote my evidence", or the weekly scheduled run. Everything it writes is confidential and stays under growth/.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write Edit
---

# growth-signals

Turns daily work into review-ready evidence. A deterministic miner finds candidate snippets, the model
classifies them against **your** framework, and **you** decide what counts. The model never promotes.

**Reads:** `.claude/brain/growth/*.json` (source config, signal patterns, values, senior leaders),
`growth/development/frameworks/*.md`, the sources the config lists, the tracker and hypotheses.
**Writes (all confidential, under `growth/development/`):** `run/candidates-<date>.json`,
`run/classified-<date>.json`, `evidence-candidates.md`, `level-hypotheses.md`, `performance-tracker.md`
(only via `promote.py`), `coverage-matrix.md`, `run/run-log.json`.
**Never writes:** MEMORY.md, the wiki, digests, any shared surface. Never quotes growth content outside `growth/`.

## Modes

### Mine (weekly, unattended-safe)

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/mine_signals.py` (defaults: look-back from `source-config.json`, 10 days;
   `--backfill` for a first run; `--since YYYY-MM-DD` for review prep). It prints counts only and writes the
   snippets to `growth/development/run/`. If `candidates` is 0, return the stats and stop.
2. **Read the framework** (`growth/development/frameworks/*.md`): criterion ids, skills, level, version.
   Read `.claude/brain/growth/values.json`.
3. **Self-ratings check:** read `growth/development/self-assessment.json`. For each criterion rated 2 or more with a
   comment, search the same sources for a snippet that backs the claim and add it as a candidate with
   `pattern_id: "self-assessment-search"` and `confidence: "Manual"`. Note claims with no support in your return stats as a count.
4. **Classify** each candidate (Sonnet is enough). Pick 1 to 3 criterion ids that it really evidences, a confidence
   (High: a senior leader said it, or an explicit led-outside-area deliverable. Medium: you are clearly the actor and
   the scope is beyond your area. Low: ambiguous or passing. Manual: from step 3), a one-line title starting with the
   date, and optionally `values_evidenced` (max 2, only when the snippet plainly shows the behaviour). Skip anything
   that does not map cleanly. **Never invent a criterion id.**
5. Write the classified list with the Write tool to `growth/development/run/classified-<date>.json`. Each item keeps
   the miner's fields plus `title`, `confidence`, `classifications: [{criterion_id, target_level}]`, `values_evidenced`.
6. `python3 ${CLAUDE_SKILL_DIR}/scripts/append_evidence.py --classified growth/development/run/classified-<date>.json`
   It validates first (unknown ids abort the run and write nothing), skips hashes already queued, writes a dated
   section at the top of `evidence-candidates.md`, and opens a hypothesis once 3 candidates hit one criterion.
7. Return stats only: files scanned, candidates, added, duplicates, hypotheses updated. No snippets, ids or names.

### Triage and promote (interactive, 2 minutes)

The owner opens `growth/development/evidence-candidates.md` and ticks **one** box per candidate:
`[x]` Accept, Reject or Defer. Then:

`python3 ${CLAUDE_SKILL_DIR}/scripts/promote.py`

Accepts are appended to the matching skill section of the tracker (tagged `<!-- crit: id -->`, deduplicated by hash),
every triaged row becomes a status line, nothing is deleted, and re-running changes nothing. The matrix is rebuilt.
Prints `{accepted, rejected, deferred, no_action, matrix_rebuilt}`.

### Matrix

`python3 ${CLAUDE_SKILL_DIR}/scripts/build_matrix.py` writes `growth/development/coverage-matrix.md`: one table per
framework file, with promoted evidence, pending candidates, hypothesis and self-rating per criterion. Rows with
nothing behind them get status `gap` (others: evidenced or in progress). Plain markdown. To tag an existing tracker bullet
by hand, append `<!-- crit: id1, id2 -->` to it.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `source-config.json missing` | setup did not copy the templates | re-run `/brain-core:setup` |
| `no framework criteria found` | `growth/development/frameworks/` is empty | add your framework (see the template there) |
| `unknown criterion id` | the classifier invented or mistyped an id | fix the classified file, rerun; nothing was written |
| 0 candidates every week | patterns too tight, or owner name not in the sources | tune `signal-patterns.json`; check `owner` in `.claude/brain.json` |
| Too many weak hits | patterns too loose | tighten regexes, add `keyword_anchors` |

## Boundaries

- Candidates are never promoted automatically, even from a senior leader. Promotion is the owner's tick.
- Files outside `growth/` that are `sensitivity: confidential` or `redact_content: true` are never mined.
- Slack is not scanned by default; add `raw/slack` globs to `source-config.json` only if you accept the noise.
- It surfaces evidence. It cannot tell you whether you have reached a level.
