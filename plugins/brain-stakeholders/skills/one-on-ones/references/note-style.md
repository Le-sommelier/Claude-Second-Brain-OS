# 1:1 note style: written for the two people who were in the room

The notes are read by the owner (and the other person, if the owner shares them), not by the wiki or another agent. Optimise for a 30-second read.

## Shape

| Field | Rule |
|---|---|
| `id`, `person_id`, `date` | From the detect output. `person_id` is the roster id. |
| `title` | 3 to 8 words naming the main thing discussed. "Q1 roadmap and hiring plan", not "Weekly 1:1". |
| `sections.discussed` | What was talked about, one topic per bullet, with its outcome or state. |
| `sections.decisions` | Only things that were settled. Empty if none. |
| `sections.feedback` | Feedback either way, stated plainly and attributed ("Casey: the pre-read helped"). |
| `sections.career` | Only for people with `showCareer` true (manager, reports): growth, scope, objectives. |
| `sections.carryover` | Raised but not finished, for next time. |
| `actions` | `{"who": "<first name>" or "Both", "what": "...", "due": "YYYY-MM-DD" or ""}`. Real commitments only. A due date only if one was said or clearly implied. |
| `withheld` | Count of topics left out (below). |
| `source` | Transcript file name. |

## Hard limits (the validator enforces them)

At most 4 bullets per section, 25 words per bullet, 170 words in total, 6 actions. No frontmatter, wiki links, ids, tags or flags in any text. No banned words from `BRAND.md`.
Empty sections are empty lists, never "None" or "N/A".

## Writing

- Lead with the fact. "Agreed to move the partner launch to January" beats "We had a discussion about the timeline and agreed...".
- Specific beats balanced: the project, the number, the date. Plain words, short sentences, active voice. Use first names, never "I" or "you".
- Write in English even if the call was not.

## Leave out (and count in `withheld`)

- Anything said "off the record", "between us" or similar, until it is clearly back on the record.
- Personal life: health, family, holidays, feelings about colleagues that were not framed as work feedback.
- Compensation figures and anyone's performance rating.
- Small talk.

Never mention in the text that something was withheld. The count is for the owner only.
