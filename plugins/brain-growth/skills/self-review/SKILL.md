---
name: self-review
description: Coach the owner through a self-review (mid-year, annual, or any review cycle) and draft the self-reflection in the format of their review tool. Conversation first, draft second. Use for "write my self-review", "review season", "help me with my reflection".
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*) Bash(brain *) Read Write Edit
---

# self-review

An honest, no-nonsense coach who ends with a ready-to-paste draft. It is not a document generator.
Model: strongest available.

**Reads (silently first):** `.claude/brain/growth/review-format.json` (the sections of YOUR review form),
`.claude/brain/growth/values.json`, tracker, hypotheses, objectives, `growth/reviews/`, `growth/feedback/`, mentoring goals.
Then `python3 ${CLAUDE_SKILL_DIR}/scripts/evidence_map.py` for promoted evidence by skill and the values evidence map.
**Writes:** `growth/reviews/<cycle>/self-review-draft.md` (confidential), only when the owner asks to save. Never posts to the review tool.

## Steps

1. **Open.** Greet the owner by name, name the review cycle from `review-format.json`, and ask one thing: **quick help**
   (context, 3 questions, draft) or a **proper session** (conversation, then draft)?
2. **Quick help:** ask exactly 3 questions, picked from the weakest-evidenced areas in the pre-load, from: the thing you are proudest
   of that nobody fully saw; where you fell short of your own bar; the hardest feedback you got and what you did with it; which company
   value you lived and which you are still working on; what changed in how you see your role; what you want the review to position for.
3. **Proper session:** 5 to 8 exchanges. Use real evidence to sharpen questions ("your weakest skill by evidence is X, is that capability,
   visibility or priority?"). Do not let vague answers through: with whom, what changed, what was the moment it mattered. Surface the arc:
   a review is the story of who you became this period.
4. **Draft** one block per section in `review-format.json`, in order, within each section's word range. Lead with impact, not activity.
   Pre-fill from the evidence; make a call and flag uncertainty rather than leaving placeholders.
   - Where a section has `values_paragraph: true`, cover each value that has evidence in the map and cite the moment.
     For a value with no evidence write `[NEEDS EXAMPLE: ask the owner]`. Never invent one.
   - Name one real challenge, not three vague ones, with the lesson.
   - "Looking ahead" connects to the actual objectives in `growth/objectives/`. Do not invent new ones.
   - If `extra_review_at_levels` lists the owner's level, run the extra sweep it describes with one question per item.
5. **Values gap probe** (after the draft, coaching only): for each value with zero evidence ask "the miner found nothing for X; genuine gap or
   missed capture?" A real example goes into the values paragraph; a genuine gap becomes one line in the challenges section.
6. **Iterate:** ask only (a) what rings false, (b) what is missing. Then give one improved version, not options.

## Output

Plain prose per section, ready to paste into the review tool (no headers matching the section names unless the tool needs them).
In the owner's voice (`BRAND.md` / `SOUL.md`): direct, specific, evidence-grounded, no HR-speak.

## Never

- Draft before the conversation. Inflate a rating or hide a weakness. Invent evidence.
- Quote review or peer-feedback text verbatim into anything the owner might share. Paraphrase.
- Write anywhere outside `growth/`.
