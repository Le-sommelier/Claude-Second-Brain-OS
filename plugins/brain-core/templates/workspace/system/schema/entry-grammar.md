---
type: kb-entry-grammar
version: "3.1"
---

# Entry grammar

Applies to every facet log in a project (`status.md`, `risks.md`, `resources.md`,
`milestones.md`, `hypotheses.md`) and to topic logs. `teams.md` is YAML frontmatter, not a log.

```
entry      := header NL meta NL body
header     := "## " DATE " · " ID " · " STATE
meta       := "by: " BY (" · " key ": " value)*
body       := free markdown until the next "## " header or EOF
DATE       := YYYY-MM-DD
ID         := (RSK|DEP|MS|STA|RES|HYP)-NNN
STATE      := open | closed | mitigated | proposed | accepted | superseded | at-risk | on-track | off-track | done | slipped
BY         := human | ai | ai-confirmed
```

The separator is ` · ` (space, middle dot U+00B7, space).

## Which IDs go where

| File | Prefixes |
|---|---|
| `status.md` | `STA` |
| `risks.md` | `RSK` (risk), `DEP` (dependency or blocker) |
| `milestones.md` | `MS` |
| `resources.md` | `RES` |
| `hypotheses.md` | `HYP` |

Decisions are not log entries: one file each under `decisions/` (see rule 5).

## Meta keys

| Key | Required | Meaning |
|---|---|---|
| `by` | yes (first) | provenance |
| `trust` | yes if by is not human | high / medium / low, computed from the source |
| `source` | yes | raw ID, entry ID, or `owner` for the owner's direct input |
| `owner` | no | person ID from `people/_org.yaml` |
| `due` | no | YYYY-MM-DD |
| `rag` | status entries | green / amber / red |
| `refs` | no | comma-separated IDs this entry relates to |
| `sensitivity` | no | `confidential` when any source is confidential |

## Example

```markdown
## 2026-11-04 · RSK-003 · open
by: ai · trust: high · source: mtg-2026-11-04-checkout-weekly · owner: sam-patel · due: 2026-11-20
Payment provider sandbox is down twice a week; blocks MS-002 load testing.
```

## Rules

1. Append-only. Never edit or delete an existing entry; add a new one with the same ID. The latest `DATE` (then file order) is the current state.
2. Fenced `<!-- human -->…<!-- /human -->` blocks are skipped by the parser and never rewritten by agents.
3. Lines outside entries (file intro, frontmatter) are ignored by the parser.
4. Parse failures are reported by `brain kb build` with file:line and fail the build; nothing partial is written.
5. Decision files: frontmatter (`id, date, status, by, trust, source, owner, supersedes, title`) plus body sections Context / Options / Decision / Consequences. IDs are `DEC-<project-slug>-NNN`.
