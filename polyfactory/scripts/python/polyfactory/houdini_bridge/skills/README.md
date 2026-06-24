# Houdini bridge — Skills

This folder is the **extendable skill/recipe library** the MCP serves to agents.
Each `.md` file is one skill: a goal-oriented recipe for operating Houdini
(how to sequence tools + the hard-won gotchas no model knows from training data).

The MCP exposes three tools over this folder:

- `houdini_list_skills()` — discovery: name + description + when-to-use for every skill.
- `houdini_get_skill(name)` — retrieval: the full markdown of one skill.
- `houdini_save_skill(...)` — self-extension: an agent (or you) adds a new skill.

So the library grows over time: when an agent works out a reliable procedure,
it banks it as a new skill, and every future agent can discover and reuse it.

## Skill file format

```markdown
---
name: my-skill-slug          # kebab-case, unique; becomes the filename
description: One line shown in list_skills (used to decide relevance)
when_to_use: When to reach for this skill
tags: comma, separated, tags
---

# Skill body (markdown)

The actual recipe: inputs, step-by-step workflow, the non-obvious traps,
pointers to fuller docs / exemplars, and a "done when" check.
```

## Conventions
- Keep the body **actionable** — steps, gotchas, and a done-condition, not prose.
- Point to canonical docs (`documentation/...`) and worked exemplars rather than
  duplicating long content, so skills don't drift from the source of truth.
- `README.md` (this file) is ignored by the registry; everything else `*.md` is a skill.
