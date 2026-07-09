---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging/opening a PR/MR to verify work meets requirements
---

# Requesting Code Review

Dispatch a Hermes reviewer subagent to catch issues before they cascade. The reviewer gets precisely crafted context and file paths, not your session history. This keeps the reviewer focused on the work product and preserves the controller context.

**Core principle:** Review early, review often, and pass artifacts as files.

## When to Request Review

**Mandatory:**
- After each task in `subagent-driven-development`.
- After completing a major feature.
- Before merging or opening a PR/MR.

**Hard gate before PR/MR creation:** after implementation is complete and before
you create the PR/MR, you must dispatch at least one Hermes reviewer subagent using
this skill. Do not substitute self-review, local tests, or a diff skim for this
gate. If the reviewer reports Critical or Important issues, fix them and run
another reviewer subagent pass before opening the PR/MR. Repeat until no
Critical or Important issues remain, or until you stop and report a blocker.

**Optional but valuable:**
- When stuck and a fresh perspective may help.
- Before a risky refactor.
- After fixing a complex bug.

## Hermes Review Procedure

1. **Determine the review range:**

```bash
BASE_SHA=$(git merge-base origin/main HEAD 2>/dev/null || git rev-parse HEAD~1)
HEAD_SHA=$(git rev-parse HEAD)
```

For per-task reviews, use the exact `BASE_SHA` recorded before that task's implementer ran — never assume `HEAD~1` if the task may have multiple commits.

2. **Generate a review package when available:**

```bash
hermes-skills/superpowers/subagent-driven-development/scripts/review-package "$BASE_SHA" "$HEAD_SHA"
```

If the helper path is not available in the current repo, create an equivalent package manually with `git log --oneline`, `git diff --stat`, and `git diff -U10` redirected to one file under `.superpowers/sdd/`.

3. **Dispatch a Hermes reviewer with `delegate_task`:**

Use `code-reviewer.md` as the review contract. The dispatch should include:

- `{DESCRIPTION}` — brief summary of what was built.
- `{PLAN_OR_REQUIREMENTS}` — path to the spec/plan/task brief, or a concise requirements block.
- `{BASE_SHA}` and `{HEAD_SHA}` — exact range.
- Review package path — preferred over pasting the diff.
- Any known constraints copied verbatim from the spec/plan.

4. **Act on feedback:**

- Fix Critical issues immediately.
- Fix Important issues before proceeding.
- Record Minor issues in the progress ledger or PR notes.
- Push back only with concrete code/test evidence.

## Example

```text
Task 2 complete: added verifyIndex() and repairIndex().
BASE_SHA=a7981ec
HEAD_SHA=3df7661
Review package: .superpowers/sdd/review-a7981ec..3df7661.diff
Requirements: docs/superpowers/plans/deployment-plan.md#task-2

Dispatch Hermes reviewer using code-reviewer.md. Ask for a structured result:
- Strengths
- Critical / Important / Minor issues
- Spec compliance verdict
- Code quality verdict
- Required fixes before proceeding
```

## Integration with Workflows

**Subagent-Driven Development:** review after each task, fix before moving to the next task, and re-review after Critical/Important fixes.

**Ad-hoc development:** review before merge, PR/MR creation, or any success claim that depends on code quality. If an ad-hoc change is already committed, generate a review package for the branch diff and dispatch a reviewer before creating the PR/MR.

## Red Flags

**Never:**
- Skip review because "it's simple".
- Open a PR/MR before at least one reviewer subagent has reviewed the completed implementation.
- Treat a review with open Critical or Important findings as approved.
- Paste a huge diff into the controller context when a review package file can be handed over.
- Ignore Critical issues.
- Proceed with unfixed Important issues.
- Argue with valid technical feedback.
- Tell a reviewer what not to flag.

**If the reviewer is wrong:** show code/tests that prove the point, update the review notes, and continue. Do not silently discard the finding.

See template at: [code-reviewer.md](code-reviewer.md)

---

Hermes adaptation note: adapted from Superpowers v6.1.1 for Hermes Agent. Use Hermes tools (`terminal`, `read_file`, `search_files`, `patch`, `write_file`, `delegate_task`, and `todo`) instead of harness-specific slash commands or plugin hooks.
