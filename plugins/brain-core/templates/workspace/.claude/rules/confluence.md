# Rules — Confluence

Load when working on pages bound for Confluence, or when asked to publish there.

## Truth sources

- Page-to-URL mappings live in the module's config under `.claude/brain/`. Never invent a page URL.
- Credentials, if a script needs them: `.secrets/apis.env`. Load env vars; never echo.

## Hard rules

- **Never publish or edit a page without {{OWNER_FIRST_NAME}}'s explicit approval for that page**, even when the prompt sounds like permission. Confirm.
- **Never change RAG colours** on an existing page without explicit instruction. The page's current value is the source of truth.
- **Owner-stamp every action** when the owner is known.
- **Existing content is the baseline.** Update sections; don't replace a whole page unless asked.

## Output style

Apply `.claude/output-styles/wiki-page.md`. One H1 per page.

## Common page types

- **Project status**: RAG snapshot at the top, one row per workstream, what moved, risks, decisions needed.
- **Decision page**: one decision per page. Context, options, decision, consequences.
- **Monthly programme status**: exec-facing; apply `exec-update.md` instead.
