# Rules — coding

Load when working with code: `*.py`, `*.sh`, `*.js`, `*.ts`, config `*.json`, or any skill
`scripts/` folder. Does **not** load for markdown, writing or PM analysis.

## Workspace-specific

- **Never hardcode a path.** Read `.claude/paths.json` through `brainos.workspace.path()`. Resolve the workspace with `brainos.workspace.root()` (it honours `$BRAIN_ROOT`, then walks up from the current directory).
- **Case is load-bearing.** A mismatch works on a case-insensitive disk and breaks on git elsewhere.
- **Scripts a scheduled task calls must be single-line invocable**: `python3 <path> --args` or `brain ...`. No heredocs, pipes, shell loops or inline `python3 -c`; an unattended run stalls on anything that can't be allow-listed.
- **Never blank an output on bad input.** Validate first, write second. A failed upstream step must leave the previous artifact intact.
- **One writer per file.** Generated code must not share a file with another scheduled job or sync.
- **Print one JSON object** as a script's result (`emit()`), so the calling skill reads counts, not prose.

## Surgical changes

- Touch only what the task requires. Don't reformat neighbouring code or fix unrelated nits.
- If you spot something worth fixing nearby, mention it separately.
- A 5-line bug fix is a 5-line diff. If a fix genuinely needs a refactor, do it and say so.

## Define done before writing

| Vague | Verifiable |
|---|---|
| "Add validation" | three failing tests for invalid inputs, then make them pass |
| "Make it faster" | time it, name the bottleneck, target a number |
| "Handle errors" | list the failure modes; decide which return, raise or retry |
| "Make it robust" | say what robust means, and show the test |

## When to break these

Alex says "just do it" or "this is exploratory": follow that lead.
