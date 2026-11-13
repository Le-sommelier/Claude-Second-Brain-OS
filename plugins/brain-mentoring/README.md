# brain-mentoring

Mentorships, as mentor or mentee, kept as plain markdown under `growth/mentoring/<person-id>/`. Confidential by default.

## Install

```
/plugin install brain-mentoring --marketplace Le-sommelier/Claude-Second-Brain-OS
```

Requires `brain-core`. Re-run `/brain-core:setup` afterwards so the module is wired into your workspace.

```
growth/mentoring/casey-nguyen/
├── README.md          goals (G1..), agreement, cadence, mode (mentor | mentee)
├── sessions/          one dated note per session
└── actions.md         A-001 ... with owner, due date, closed date
```

| Skill | What it does |
|---|---|
| `mentoring-setup` | Start a mentorship: goals, agreement, cadence |
| `mentoring-prep` | One-page prep from the last note, open actions and recent evidence |
| `mentoring-notes` | Capture a session, extract actions, close finished ones |
| `mentoring-review` | Quarterly progress against the goals, with counts |

**Connectors:** none. **Scheduled tasks:** none.

`brain-growth`'s miner reads `growth/mentoring/` as a source of evidence (for example, a mentee stepping up), so mentoring shows up in your own growth record without you copying anything.

Scripts are stdlib Python 3.11+. See the [module contract](../../docs/module-contract.md).
