# External Skill Dependency Audit Cases

This reference captures reusable findings from auditing external skill libraries for Hermes installation.

## Case: `obra/superpowers` → `skills/brainstorming`

Source path: `https://github.com/obra/superpowers/tree/main/skills/brainstorming`

### Standalone viability

`brainstorming/SKILL.md` is mostly understandable on its own, but a raw direct install of only `SKILL.md` is incomplete if the visual companion is desired and the workflow expects a follow-on planning skill.

### Dependencies and references found

- Hard handoff to `writing-plans`:
  - “Transition to implementation — invoke writing-plans skill”
  - “The ONLY skill you invoke after brainstorming is writing-plans.”
- Optional writing aid:
  - `elements-of-style:writing-clearly-and-concisely` “if available”.
- Negative references / guardrails:
  - Do not jump to `frontend-design`, `mcp-builder`, or implementation skills after brainstorming.
- Same-skill support files:
  - `visual-companion.md`
  - `spec-document-reviewer-prompt.md`
  - `scripts/start-server.sh`, `stop-server.sh`, `server.cjs`, `helper.js`, `frame-template.html`

### Hermes adaptation notes

- If installing by raw `SKILL.md` URL, explicitly treat the visual companion as unavailable unless support files are also packaged.
- If porting fully, map files as:
  - `visual-companion.md` and `spec-document-reviewer-prompt.md` → `references/`
  - visual companion server files → `scripts/`
- Patch repo-relative paths such as `skills/brainstorming/visual-companion.md` to Hermes-local references such as `references/visual-companion.md`.
- Ensure Hermes has an appropriate `writing-plans` skill; if it already has a Hermes-adapted `writing-plans`, the hard handoff is satisfied.

## Case: `mattpocock/skills` → `skills/productivity/grill-me`

Source path: `https://github.com/mattpocock/skills/tree/main/skills/productivity/grill-me`

### Standalone viability

Do **not** install `grill-me` alone if the goal is functionality. It is a thin wrapper:

```md
Run a `/grilling` session.
```

The actual workflow lives in `skills/productivity/grilling/SKILL.md`.

### Dependencies and references found

- `grill-me` → hard dependency on `/grilling`.
- `grilling` has no support files and no further skill dependencies.
- `grill-me` includes `disable-model-invocation: true`, indicating user-invoked wrapper semantics in the source harness.

### Hermes adaptation notes

- Prefer installing only `grilling` when the user wants the capability: a relentless one-question-at-a-time interview to sharpen a plan/design.
- Install both `grill-me` and `grilling` only if the user wants to preserve the upstream slash-command naming or wrapper/core design.
- If porting `grill-me`, rewrite the body for Hermes semantics: “Load and follow the `grilling` skill” rather than relying on `/grilling` slash-command routing.
- Preserve the design intent of `disable-model-invocation: true` in prose if Hermes does not enforce that frontmatter.

## Design pattern: user wrapper + reusable core

External skill libraries may split skills on who can invoke them:

- **User-invoked wrapper skill:** friendly command/entrypoint, often thin and sometimes disabled for model auto-invocation.
- **Model-invoked reusable core skill:** contains the actual workflow and can be composed by other skills.

This mirrors software design: `CLI command / route handler → service function`. In Hermes, install the core skill for capability, and keep the wrapper only when the user values the original UX or name.
