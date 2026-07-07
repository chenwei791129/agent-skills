# Hermes Superpowers Skills

Hermes-adapted development workflow skills from [`obra/superpowers`](https://github.com/obra/superpowers) v6.1.1.

This collection is intentionally **not** a direct plugin install. Hermes has its own skill loader, gateway rules, tools, and `delegate_task` semantics, so these skills adapt Superpowers v6's development methodology to Hermes rather than importing the upstream bootstrap wholesale.

## Recommended application-development flow

1. `brainstorming` — turn a rough feature idea into an approved design spec.
2. `using-git-worktrees` — verify or create an isolated development workspace.
3. `writing-plans` — create a task-by-task implementation plan with exact files, tests, and commands.
4. `subagent-driven-development` — execute the plan with one Hermes subagent per task, task briefs, review packages, combined task review, and a durable progress ledger.
5. `test-driven-development` — required discipline for feature and bugfix implementation tasks.
6. `systematic-debugging` — root-cause workflow for bugs, failing tests, and unexpected behavior.
7. `requesting-code-review` / `receiving-code-review` — whole-branch review and review-response workflows.
8. `verification-before-completion` — evidence gate before claiming success.
9. `finishing-a-development-branch` — verified merge / PR / keep / discard options at the end.

## Superpowers v6 efficiency mechanics included

- Task brief files (`subagent-driven-development/scripts/task-brief`) so implementers do not read the whole plan.
- Review package files (`subagent-driven-development/scripts/review-package`) so reviewers read one generated diff package instead of repeatedly running git commands.
- Combined task reviewer (`subagent-driven-development/task-reviewer-prompt.md`) that returns both spec-compliance and code-quality verdicts.
- Report files and durable progress ledger under `.superpowers/sdd/` to survive context compression/resume.
- Guidance to avoid pasted history; pass paths and terse summaries instead.

## Hermes-specific differences

- Hermes `delegate_task` children inherit the parent model. Per-task model routing from upstream Superpowers is represented as guidance; use a spawned `hermes chat --model ...` process only when an explicit model tier is required.
- Hermes subagents cannot call `clarify`; they should return `NEEDS_CONTEXT` and a precise question in their report, then the controller re-dispatches with the answer.
- The upstream `using-superpowers` bootstrap skill is intentionally omitted to avoid overriding Hermes' own system prompt, gateway, safety, and family-butler behavior.
- Visual brainstorming support is omitted from the portable `brainstorming` port; use Hermes browser/computer-use tooling separately when a visual design discussion needs it.

## Install examples

Install a single skill by full path:

```bash
hermes skills install chenwei791129/agent-skills/hermes-skills/superpowers/subagent-driven-development
```

Because this repository keeps Hermes skills under `hermes-skills/` rather than the default tap path, use the full repository path form above for reliable installs.

Each skill directory includes its own `NOTICE.md` with the upstream MIT notice.
