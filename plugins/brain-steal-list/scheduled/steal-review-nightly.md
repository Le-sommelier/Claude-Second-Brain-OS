# Scheduled task: brain-steal-review-nightly

You are running the nightly steal review in the owner's workspace. The owner is not present.

Run mode 1 (review) of the `steal` skill of the `brain-steal-list` plugin, exactly as written: `init_db.py`,
`build_my_setup.py`, `sync_drive_inbox.py`, `list_inbox.py`, review each new screenshot (Read the image),
`record.py`, `build_digest.py`, `build_board.py`, `purge_processed.py`. One-line `python3` calls only.

- If the inbox is empty, exit quietly with one line.
- If `list_inbox.py` fails, report the reason in one line and stop. Do not retry with any sandbox disabled.
- Do not adopt, plan or build anything. Do not post or publish anywhere.

Final report, terse: counts, then for each steal or adapt item its id, title, target and first step.
