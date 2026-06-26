---
name: grilling
description: 'Interview the user relentlessly about a plan or design. Use when the user wants to stress-test a plan before building, or uses any grill trigger phrase.'
---

# Grilling

Interview the user relentlessly about every aspect of a plan or design until you and the user reach a shared understanding.

## Process

- Walk down each branch of the design tree, resolving dependencies between decisions one by one.
- Ask **one question at a time**, then wait for feedback before continuing. Asking multiple questions at once is bewildering.
- For each question, provide your recommended answer and the reasoning behind it.
- Prefer concrete choices over open-ended prompts when possible.
- If a question can be answered by exploring the codebase, documentation, repository history, or available context, do that research instead of asking the user.
- Keep going until the meaningful unknowns are resolved or the user explicitly stops the grilling session.

## Output Style

For each turn, use this shape:

```markdown
**Question:** <one focused question>

**My recommendation:** <recommended answer>

**Why:** <brief reasoning / trade-off>
```

Do not jump into implementation. The purpose of this skill is to sharpen decisions before work begins.

---

Adapted for Hermes Agent from Matt Pocock's `grilling` skill in `mattpocock/skills`.
