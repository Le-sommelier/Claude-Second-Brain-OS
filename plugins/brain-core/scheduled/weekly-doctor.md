Run the weekly workspace health check.

1. Run `brain doctor` from the workspace root. Read its JSON.
2. For each item under `verify_in_session.scheduled`, check it exists in the scheduled-task registry; for each item under `verify_in_session.connectors` marked required, check the connector responds.
3. Run `brain kb build` then `brain kb attention`.
4. Write nothing else. For each error or warning that needs a human decision, run
   `brain kb propose --audience owner --title "<one line>" --source doctor`.
5. End with a five-line summary: status, errors, warnings, proposals created, attention counts.

Never publish, post or send anything.
