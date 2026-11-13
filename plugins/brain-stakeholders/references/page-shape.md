# People page shape and ownership

A people page is `people/<first-last>.md`. Create it with `brain new person <first-last>`; the
scripts in this module only update it.

```markdown
---
id: casey-nguyen
name: Casey Nguyen
role: Product Manager
relationship: report          # self | manager | report | peer | stakeholder | exec | mentee | mentor | partner
influence: 2                  # 1-5, how much they can move your work
interest: 5                   # 1-5, how much they care about it
health: strong                # strong | ok | at-risk | unknown
last_contact: 2026-11-05
cadence_days: 14              # optional; overrides the quadrant default
sensitivity: internal
---

# Casey Nguyen

## Profile                    <- brain-wiki
## Working with them          <- the owner (put it inside human fences)
<!-- human --> ... <!-- /human -->
## Stakeholder notes          <- stakeholders (always inside a confidential wrapper)
## 1:1 log                    <- stakeholders (newest first, inside a confidential wrapper)
## Evidence log               <- stakeholders (append-only, one dated line per observation)
```

## Who writes what

| Part | Writer |
|---|---|
| `relationship`, `influence`, `interest`, `health`, `last_contact`, `cadence_days` | stakeholders (the `person` skill, the 1:1 push) |
| `## Stakeholder notes`, `## 1:1 log`, `## Evidence log` | stakeholders |
| Everything else (profile, role changes, project involvement) | brain-wiki or the owner |
| Anything between `<!-- human -->` and `<!-- /human -->` | the owner only. No script rewrites it, and scripts abort if it would change. |

Notes about a person (impressions, feedback, 1:1 content) go inside
`<!-- CONFIDENTIAL: redact-on-share -->` markers. They never reach digests, the wiki or any
shared surface.
