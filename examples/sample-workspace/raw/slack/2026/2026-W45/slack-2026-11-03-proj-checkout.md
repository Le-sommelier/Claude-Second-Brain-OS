---
id: slack-2026-11-03-proj-checkout
source_type: slack-channel
type: slack-ingest
date: 2026-11-03
week: 2026-W45
channel: proj-checkout
channel_id: C0FERN0001
tags: [checkout-revamp]
sensitivity: internal
redact_content: false
tech_decisions: true
message_count: 3
thread_count: 1
contributors: [Alex Morgan, Sam Patel, Taylor Brooks]
wiki_processed: false
---

# #proj-checkout — 2026-11-03

## 09:14 — Sam Patel
> permalink: https://fernhill.slack.com/archives/C0FERN0001/p1793697240000100

Heads up: the new payment sheet is behind the `checkout_v2` flag in staging from today. Please break it.
Test plan: https://fernhill.example/wiki/checkout-v2-test-plan

_Reactions: :eyes: ×3 :white_check_mark: ×1_

### Thread (2 replies)

- **09:31 — Jordan Lee** ([permalink](https://fernhill.slack.com/archives/C0FERN0001/p1793698260000200?thread_ts=1793697240.000100&cid=C0FERN0001))
  Found one already: the saved-card list overflows on narrow screens. Screenshot in the design thread.
- **09:40 — Sam Patel** ([permalink](https://fernhill.slack.com/archives/C0FERN0001/p1793698800000300?thread_ts=1793697240.000100&cid=C0FERN0001))
  Thanks Jordan. Logged as CHK-212, fix lands tomorrow.


## 11:02 — Taylor Brooks
> permalink: https://fernhill.slack.com/archives/C0FERN0001/p1793703720000400

Baseline conversion for the old sheet over the last 4 weeks is 61.4%. I will set up the experiment dashboard against that number.

## 15:47 — Alex Morgan
> permalink: https://fernhill.slack.com/archives/C0FERN0001/p1793720820000500

Decision: we ship the payment sheet to 10% of traffic on 17 November, not before. Rollout plan goes into the project page today.
