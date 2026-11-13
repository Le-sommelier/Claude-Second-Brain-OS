# .secrets/

Holds `apis.env`, the one file with API tokens for any integration that is not a Claude
connector (most modules use connectors and need nothing here). It is git-ignored by the
workspace `.gitignore`; keep it that way.

## Format

Plain `KEY=value` lines, one per token, no quotes, no `export`:

```
# example only: create the real file yourself, never paste it into chat
CONFLUENCE_BASE_URL=https://your-site.example/wiki
CONFLUENCE_API_TOKEN=
```

## Rules

- Setup never creates `apis.env` and never asks for a token value. Create it yourself.
- Scripts load it into the environment and read variables by name. They never print a value.
- Claude never reads the file aloud, quotes it, or copies a value into another file.
- Rotate a token by editing the file; nothing else caches it.
