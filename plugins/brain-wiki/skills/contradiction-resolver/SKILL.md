---
name: contradiction-resolver
description: Detect log entries that contradict or duplicate each other (split RAG on one day, two accepted decisions that clash, an item still open after a later entry resolved it) and propose how to reconcile them. Never rewrites a log. Use weekly, from the system review, or on demand - "any contradictions in partner-api?".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read
model: sonnet
---

# Contradiction resolver: propose, never rewrite

The logs are append-only, so a contradiction is fixed by adding a newer entry, never by editing an old one. This skill finds the candidates, judges which are real, and proposes the reconciling entry. The owner decides.

## Steps

1. **Find candidates.** One command:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/find_conflicts.py
   ```
   Add `--project <slug>` to limit it. Kinds: `rag-split` (different RAG within a few days), `near-duplicate` (two live entries saying the same thing under different IDs), `decision-clash` (two accepted decisions, similar titles, no `supersedes`), `resolved-open` (a later closing entry cites an ID that is still open).
2. **Judge.** Open each candidate's entries (`brain kb show <project>/<ID>`). Two entries contradict when they make different factual claims about the same subject. Extra detail on the same subject is elaboration, not conflict. Drop elaboration.
3. **Decide the reconciling move**, by kind:
   - `rag-split`: the entry from the higher-trust source and the later date wins; propose a new status entry restating it with `refs` to both.
   - `near-duplicate`: propose closing the newer ID as `superseded` with `refs` to the older.
   - `decision-clash`: propose a decision that `supersedes` the older; never mark either rejected on your own.
   - `resolved-open`: propose a `closed` entry for the still-open ID, citing the resolving entry.
4. **Propose.** For each real conflict, skip if a similar open proposal exists (`brain kb query "select id, title from proposals where state='open'"`), otherwise:
   ```bash
   brain kb propose --title "Conflict: <project>/<ID> vs <ID>: <subject>" --source <ID> --body "<what disagrees, which side the rules favour, and the entry to append>"
   ```
5. **After the owner accepts**, append the reconciling entry through the `wiki-update` payload (`by: ai`, `source` the proposal id, `refs` set). Old entries stay as they are.
6. **Return** a short list: candidates, real conflicts, proposals raised.

## Rules

- Never edit, delete or strike through an existing entry. Never touch `<!-- human -->` fences.
- Do not decide what is true, only which recorded claim the recency and trust rules favour.
- Confidential entries: describe the conflict in abstract terms, no names, amounts or quotes.
