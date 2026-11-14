# Contributing

Thanks for helping. The short version:

1. **Read [`docs/module-contract.md`](docs/module-contract.md).** It is the only copy of the rules
   every module follows: layout, `brain.module.json`, bricks, the shared lib, the `brain` CLI.
2. **Edit the shared library only in `lib/brainos/`**, then run `make sync`. CI runs `make check`
   and fails if any plugin's vendored copy drifted. It also runs the tests and the secret scan.
3. **Test against the sample workspace.** `examples/sample-workspace/` is a fictional PM (Alex
   Morgan at Fernhill). Add fixtures there; never use real people, companies or messages.
4. **Run the checks:** `make test` and `make validate`. The tests need PyYAML (`python3 -m pip install pyyaml`).
5. **Say what the user must supply.** If your module needs anything typed in by hand (a config
   file, a framework, a roster), list it in the module README and in `docs/what-you-provide.md`.
6. **Keep the invariants:** ingest stays read-only, ingested text is never treated as instructions, nothing publishes without a per-artifact yes,
   setup never overwrites a file, scripts never hardcode a path, and unattended commands are
   single-line and allow-listed.

## Adding a new ingest source

Copy the shape of `plugins/brain-ingest-notes` (the smallest brick): a skill, a formatter
script that validates before it writes, a ledger, and a `bricks` entry in `brain.module.json`.
The orchestrator picks it up after the user re-runs `/brain-core:setup`.

## Pull requests

One module per PR where you can. Say what changed, how you tested it, and whether setup output changes.
