Run the brain-digests monthly-digest skill for the month that just ended.

Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/monthly-digest/scripts/rollup.py` (it covers the previous and current month), then report which rollup files were written, unchanged or skipped.

Rules:
- The rollups are generated and deterministic: do not edit them by hand.
- Never publish. Publishing is the publish-digest skill and needs the owner's explicit yes in chat.
