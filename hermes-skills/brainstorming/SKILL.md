---
name: brainstorming
description: 'Use before creative or product work: creating features, building components, adding functionality, or changing behavior. Refines intent, requirements, and design before implementation, then hands off to Hermes writing-plans.'
---

# Brainstorming Ideas Into Designs

Turn rough ideas into approved designs through collaborative dialogue before implementation.

This is a **design gate**. Do not write code, scaffold files, modify behavior, or invoke implementation workflows until you have presented a design and the user has approved it.

## When to Use

Use before:

- Creating features or products
- Building components
- Adding functionality
- Changing existing behavior
- Turning a vague idea into a plan

Do not skip because the task seems simple. Simple tasks can have short designs, but unexamined assumptions still cause wasted work.

## Checklist

Create and complete tasks in this order:

1. **Explore context** — inspect relevant files, docs, existing behavior, and recent commits when a codebase exists.
2. **Assess scope** — if the request spans multiple independent subsystems, pause and propose decomposition before refining details.
3. **Ask clarifying questions** — one at a time; prefer multiple-choice questions when helpful.
4. **Propose 2–3 approaches** — include trade-offs and your recommendation.
5. **Present the design** — section by section, scaled to complexity; get user approval as you go.
6. **Write the design doc** — save the approved design to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, unless the user or project has a different preferred location.
7. **Self-review the spec** — fix placeholders, contradictions, ambiguity, and scope creep.
8. **Ask the user to review the written spec** — do not proceed until approved.
9. **Transition to planning** — load and use Hermes' `writing-plans` skill to create the implementation plan.

## Process Flow

```dot
digraph brainstorming {
    "Explore context" [shape=box];
    "Assess scope" [shape=box];
    "Ask one clarifying question" [shape=box];
    "Propose 2-3 approaches" [shape=box];
    "Present design sections" [shape=box];
    "User approves design?" [shape=diamond];
    "Write design doc" [shape=box];
    "Spec self-review" [shape=box];
    "User reviews spec?" [shape=diamond];
    "Load Hermes writing-plans skill" [shape=doublecircle];

    "Explore context" -> "Assess scope";
    "Assess scope" -> "Ask one clarifying question";
    "Ask one clarifying question" -> "Propose 2-3 approaches";
    "Propose 2-3 approaches" -> "Present design sections";
    "Present design sections" -> "User approves design?";
    "User approves design?" -> "Present design sections" [label="no, revise"];
    "User approves design?" -> "Write design doc" [label="yes"];
    "Write design doc" -> "Spec self-review";
    "Spec self-review" -> "User reviews spec?";
    "User reviews spec?" -> "Write design doc" [label="changes requested"];
    "User reviews spec?" -> "Load Hermes writing-plans skill" [label="approved"];
}
```

The terminal state is **loading Hermes' `writing-plans` skill**. Do not jump directly to implementation.

## Understanding the Idea

- Start by understanding the project or problem context.
- If working in a repository, inspect existing structure before proposing changes. Follow existing patterns.
- If the project is too large for a single spec, help the user split it into sub-projects. Brainstorm the first sub-project through the normal flow.
- Ask one question per message. If a topic needs more exploration, break it into multiple turns.
- Focus on purpose, constraints, success criteria, users, edge cases, and what is explicitly out of scope.

## Exploring Approaches

- Propose 2–3 viable approaches.
- Explain trade-offs: complexity, speed, maintainability, risk, user experience, and testing burden.
- Lead with your recommended option and explain why.
- Apply YAGNI ruthlessly: remove unrequested or speculative capabilities.

## Presenting the Design

Once you understand what should be built, present the design in sections. Scale each section to the work:

- A few sentences for simple tasks.
- Up to 200–300 words for nuanced sections.

Cover the relevant pieces:

- User-visible behavior
- Architecture and boundaries
- Components and responsibilities
- Data flow or state flow
- Error handling and recovery
- Security/privacy implications, if any
- Testing and verification strategy
- Out-of-scope items

After each meaningful section, ask whether it looks right so far. If the user says no, revise before moving on.

## Design for Isolation and Clarity

Break the system into smaller units with clear responsibilities and interfaces.

For each unit, be able to answer:

- What does it do?
- How is it used?
- What does it depend on?
- Can its internals change without breaking consumers?
- Can it be tested independently?

When existing code has problems that affect the work, include targeted improvements as part of the design. Do not propose unrelated refactoring.

## Documentation

Write the approved design to a spec file. Default path:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

Project or user preferences override this default.

The spec should include:

```markdown
# <Feature / Change> Design

## Goal

## Non-Goals

## Context

## Proposed Design

## Components / Boundaries

## Data or Control Flow

## Error Handling

## Testing / Verification

## Open Questions
```

Commit the design document when working in a git repository and committing is appropriate for the task.

## Spec Self-Review

Before asking the user to review the spec, check it with fresh eyes:

1. **Placeholder scan:** remove `TBD`, `TODO`, incomplete sections, and vague requirements.
2. **Internal consistency:** fix contradictions between sections.
3. **Scope check:** ensure the spec is focused enough for one implementation plan.
4. **Ambiguity check:** make requirements explicit when they could be interpreted multiple ways.
5. **YAGNI check:** remove features the user did not ask for.

Fix issues inline, then proceed.

## User Review Gate

After the self-review passes, ask the user to review the written spec before proceeding:

> Spec written to `<path>`. Please review it and tell me if you want changes before I create the implementation plan.

If the user requests changes, update the spec and repeat the self-review. Only proceed once the user approves.

## Handoff to Hermes Writing Plans

After the user approves the written spec, load and follow Hermes' `writing-plans` skill to create a detailed implementation plan.

In Hermes, this means using the installed `writing-plans` skill rather than an upstream Superpowers repo-relative reference.

Do not invoke another implementation skill before `writing-plans` has produced the plan.

## Key Principles

- **One question at a time** — do not overwhelm the user.
- **Multiple choice preferred** — easier to answer than open-ended prompts when possible.
- **YAGNI ruthlessly** — remove unnecessary features from every design.
- **Explore alternatives** — present 2–3 approaches before settling.
- **Incremental validation** — present design sections and get approval before moving on.
- **Evidence over guessing** — inspect the codebase when the answer can be discovered.
- **Design before implementation** — no code or scaffolding before approval.

---

Adapted for Hermes Agent from obra/superpowers `brainstorming`, with the Superpowers repo-relative `writing-plans` handoff changed to Hermes' installed `writing-plans` skill and the browser visual companion omitted for portability.
