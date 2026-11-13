---
type: team
project: {{SLUG}}
members:
  - {person: {{OWNER_PERSON_ID}}, role: product, owner: true, decision_maker: true}
---

# Team — {{TITLE}}

One row per person in the frontmatter. `owner: true` and `decision_maker: true` make a
meeting they attend a HIGH-trust source for this project; any other member makes it MEDIUM.
Person IDs match `people/_org.yaml`.
