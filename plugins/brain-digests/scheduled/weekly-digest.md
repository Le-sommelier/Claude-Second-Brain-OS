Run the brain-digests weekly-digest skill for the current ISO week.

Start with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/weekly-digest/scripts/run_weekly_recap.py`, then follow the skill's SKILL.md from step 2.

Rules:
- Hard stop if the runner returns `requires_user_confirmation: true` (nothing was ingested for the week). Report the stop reason and finish.
- A missing Slack file is not a stop condition; carry on without it.
- Keep it short: Overview is 2-3 sentences, table cells at most two bullets.
- Confidential sources appear at signal level only: no names, amounts, ratings or quotes.
- Write the draft to `digests/weekly/`, validate it, present it, and STOP. Never publish. Publishing is the publish-digest skill and needs the owner's explicit yes in chat.
