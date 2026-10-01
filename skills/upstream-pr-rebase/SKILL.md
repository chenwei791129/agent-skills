---
name: upstream-pr-rebase
description: 'Rebase explicitly listed GitHub pull requests onto their latest upstream base branch, one by one in the current repository, then run the project''s own tests and update the PR branch with an exact-SHA --force-with-lease push. Checks whether upstream already implemented the same change before rebasing, resolves conflicts by intent, and asks for confirmation before pushing any conflict resolution. Use when the user says "rebase my PRs", "update PR #123 to latest main", "sync these PRs with upstream", 「rebase 這幾個 PR」, 「把 PR 更新到最新 main」, 「PR 跟上 upstream」, or gives a list of PR numbers or URLs to bring up to date.'
compatibility: Requires git, a Bash or Zsh shell, and an authenticated GitHub CLI (gh) with push access to each PR head repository.
---

# Upstream PR Rebase

In the current repository, rebase each GitHub PR the user explicitly listed onto its latest base branch, one at a time. For every PR, first check whether upstream already has the same implementation, then rebase, run the tests the project's own way, and update the PR branch with `--force-with-lease` carrying an exact expected SHA.

This workflow never merges PRs, never widens PR scope, never pushes when tests fail, and never pushes a conflict resolution or closes a PR without user confirmation.

Platform operations are described in terms of change requests (PRs); only GitHub (`gh`) commands are provided for now.

## Inputs

- **PR list (required)**: PR numbers or PR URLs. Process only the listed PRs; do not look up the author's other PRs.
  - A bare number refers to the GitHub repository (`OWNER/REPO`) behind the upstream remote.
  - A URL pointing at a different repository is rejected and reported; do not switch repositories.
- **Upstream remote**: defaults to `upstream`. If it does not exist and `origin` is the PR's base repository, use `origin` as upstream.
- Draft PRs the user listed are processed normally but flagged as draft in the report.

## Outcome Categories

Every PR ends up in exactly one of these categories, and the final report is grouped by them:

| Category | Meaning |
|---|---|
| **Pushed** | No conflicts during rebase; validation and tests passed; pushed. |
| **Awaiting confirmation** | Conflicts were resolved during rebase; validation and tests passed; kept locally, not pushed, waiting for the user to confirm the resolution. |
| **Needs decision** | Upstream already has the same or a partially overlapping implementation, an unresolvable conflict, no discoverable test method, or failing tests; aborted or not pushed, the user must decide the next step. |
| **Skipped** | Not eligible: different repository, no pushable remote, stacked PR, or PR already closed or merged. |

Any PR that required conflict resolution always goes to **Awaiting confirmation** and must never be pushed directly.

## Procedure

### 1. Preflight

```bash
git status --short --branch
git remote -v
gh auth status
START_BRANCH=$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)
```

1. Read the repository's agent instructions (`AGENTS.md`, `CLAUDE.md`, or whatever the current environment loads) and contribution guidelines. Follow them for dependency setup, lint, and tests.
2. Confirm no rebase, merge, or cherry-pick is in progress (`git status` shows this). If one is, stop and report; do not abort it on the user's behalf.
3. If the working tree has uncommitted changes (including untracked files), stash them and continue:

   ```bash
   git stash push -u -m "upstream-pr-rebase: $(date +%Y%m%dT%H%M%S)"
   STASH_SHA=$(git rev-parse stash@{0})
   ```

   Record `STASH_SHA` and restore by that exact SHA later; never blindly `git stash pop` the top stash. Ignored files are not stashed.

### 2. Resolve and Freeze the PR List

Fetch metadata for each PR:

```bash
gh pr view PR_NUMBER --repo OWNER/REPO \
  --json number,title,url,state,isDraft,baseRefName,headRefName,headRefOid,headRepository,headRepositoryOwner,isCrossRepository,mergeable,mergeStateStatus,closingIssuesReferences
```

Filter with these rules; anything that fails goes to **Skipped** with the reason recorded:

- `state` is not `OPEN`.
- The PR does not belong to the repository behind the upstream remote.
- **No push remote**: match `headRepositoryOwner/headRepository` against the URLs in `git remote -v` (accept both SSH and HTTPS forms) to find the remote pointing at the head repository, recorded as `HEAD_REMOTE`. The head may live in a fork or in the upstream repository itself. If nothing matches, skip; never guess, and never push to a different remote.
- **Stacked PR**: the base branch is itself the head branch of another open PR.

  ```bash
  gh pr list --repo OWNER/REPO --state open --head BASE --json number --jq length
  ```

  A result greater than `0` means a stacked PR; skip and report it.

Freeze the list after filtering and process it in the order the user gave. Do not add new PRs mid-run.

### 3. Fetch the Latest State and Record the Lease

```bash
git fetch upstream BASE
git fetch HEAD_REMOTE HEAD_BRANCH
OLD_SHA=$(git rev-parse "HEAD_REMOTE/HEAD_BRANCH")
MERGE_BASE=$(git merge-base upstream/BASE "HEAD_REMOTE/HEAD_BRANCH")
```

`OLD_SHA` should equal the `headRefOid` reported by `gh`. If it differs, the remote state is inconsistent: fetch again, and if it still differs, move the PR to **Needs decision**. `OLD_SHA` is the only valid lease value for the later push.

List the PR commits, PR files, and overlap files (files changed by both the PR and upstream since the merge base):

```bash
git log --oneline --no-merges upstream/BASE.."HEAD_REMOTE/HEAD_BRANCH"
git diff --name-only "$MERGE_BASE".."HEAD_REMOTE/HEAD_BRANCH"
git diff --name-only "$MERGE_BASE".."HEAD_REMOTE/HEAD_BRANCH" \
  | grep -Fx -f <(git diff --name-only "$MERGE_BASE"..upstream/BASE)
```

- Compute the intersection with `grep -Fx`, not `comm -12`: `comm` depends on locale sort order and silently misses paths that differ only by case. An empty result (exit code 1) is not an error.
- Do not pass file lists as pathspecs via command substitution: an empty list degrades to comparing every file, and filenames with spaces get split.
- No overlap files does not mean the rebase or tests can be skipped.

### 4. Check Whether Upstream Already Implemented the Change

Run these three checks before rebasing:

1. **Patch equivalence**: `git cherry -v upstream/BASE "HEAD_REMOTE/HEAD_BRANCH"`. Commits prefixed with `-` already exist in upstream in full.
2. **Upstream commits on overlap files**:

   ```bash
   git log --oneline "$MERGE_BASE"..upstream/BASE -- OVERLAP_FILE...
   ```

   Read the message and diff of each commit and judge whether its intent matches the PR. Even with no overlap files, if the feature named in the PR title could have been implemented in other files, search by keyword with `git log --oneline -i --grep=KEYWORD "$MERGE_BASE"..upstream/BASE`.
3. **Linked issues**: for each issue in `closingIssuesReferences`, run

   ```bash
   gh issue view ISSUE_NUMBER --repo OWNER/REPO --json state,closedByPullRequestsReferences
   ```

   An issue already closed by a different merged PR is evidence of an existing implementation.

Verdict:

- **Fully equivalent**: upstream already provides all of the PR's intended behavior. Do not rebase; move to **Needs decision**, recommend closing the PR, and link the superseding upstream commit or PR.
- **Partial overlap**: upstream provides only part of the PR's behavior. Do not rebase; move to **Needs decision** with these options: close the PR, trim the PR to the remaining part, or rebase as usual.
- **No overlap**: proceed to rebase.

If the PR has no commits relative to the latest base, treat it as needing investigation as well: move to **Needs decision** and never push an empty result.

### 5. Rebase

Use a dedicated temporary branch so a same-named local branch with unpushed commits is never overwritten:

```bash
WORK_BRANCH="upstream-pr-rebase/PR_NUMBER"
git switch -C "$WORK_BRANCH" "HEAD_REMOTE/HEAD_BRANCH"
git rebase upstream/BASE
```

#### Conflict Handling

1. List unresolved conflicts with `git status --short` and `git diff --name-only --diff-filter=U`.
2. Read the intent of the relevant upstream commits and of the PR commit; never mechanically pick `ours` or `theirs`.
3. If resolving the conflict reveals that upstream already implemented the same feature another way, treat it like the "fully equivalent" or "partial overlap" verdict from step 4: run `git rebase --abort` and move to **Needs decision**.
4. Combine the behavior from both sides that still applies, remove duplicate implementations superseded by upstream, stage resolved files by name, and run `git rebase --continue`. Repeat until done.
5. Record for each conflict: the file, the upstream intent, the PR intent, and the chosen resolution. These records are presented to the user for confirmation in the final report.
6. If a conflict cannot be resolved without changing the PR's intent, run `git rebase --abort`, move to **Needs decision** with the conflicting files and a blocker description, and continue with the next PR.

Never use `git rebase --skip` unless the commit is proven to exist in upstream in full and the final diff still preserves the PR's intended behavior.

### 6. Validate the Rebased Result

```bash
git diff --check upstream/BASE...HEAD
git log --oneline upstream/BASE..HEAD
git diff --name-only upstream/BASE...HEAD
git merge-base --is-ancestor upstream/BASE HEAD
git range-diff "$MERGE_BASE".."$OLD_SHA" upstream/BASE..HEAD
```

Confirm that:

- The upstream base is an ancestor of HEAD.
- The PR commits and changed files match the original intent, with no commits from other branches mixed in.
- There are no whitespace errors or conflict markers.
- Every per-commit content change in `range-diff` is explained by a conflict resolution or an upstream change.

### 7. Select and Run Tests

Find the project's test method in this order and use the first explicit source. Never substitute a generic command for a project wrapper:

1. The repository's agent instructions (`AGENTS.md`, `CLAUDE.md`, etc.).
2. `CONTRIBUTING*` or developer docs.
3. Task runners: `Makefile`, `justfile`, `Taskfile.yml`, `package.json` scripts, `pyproject.toml`, etc.
4. Test steps actually run in CI configuration (e.g. `.github/workflows/`).

If none of these yields a method, do not guess a command or skip tests; move to **Needs decision** and ask the user how to test.

Test scope must cover at least:

- Test files the PR adds or modifies.
- Existing tests for the production files the PR modifies.
- Integration points affected by conflict resolutions.
- Lint, type checks, or other checks required by project guidelines.

When tests fail, first classify the failure: rebase regression, pre-existing PR problem, flaky, or a confirmed pre-existing platform failure. A rebase regression may be fixed on the branch and re-tested without widening PR scope; any other failure that cannot be ruled out moves to **Needs decision** with a failure summary, and nothing is pushed.

### 8. Push or Hold for Confirmation

- **No conflicts during rebase**: push directly.
- **Conflicts resolved during rebase**: do not push; keep `$WORK_BRANCH`, move to **Awaiting confirmation**, and continue with the next PR.

Always push with the exact `OLD_SHA` recorded in step 3:

```bash
git push \
  --force-with-lease="refs/heads/HEAD_BRANCH:$OLD_SHA" \
  HEAD_REMOTE "HEAD:refs/heads/HEAD_BRANCH"
```

A rejected lease means the remote was updated after the fetch: do not retry or fall back to `--force`. Fetch again, list the new remote commits, move to **Needs decision**, and report the concurrent update.

After a successful push, verify:

```bash
git fetch HEAD_REMOTE HEAD_BRANCH
git merge-base --is-ancestor upstream/BASE "HEAD_REMOTE/HEAD_BRANCH"
git rev-list --left-right --count upstream/BASE..."HEAD_REMOTE/HEAD_BRANCH"   # left count must be 0
gh pr view PR_NUMBER --repo OWNER/REPO \
  --json headRefOid,mergeable,mergeStateStatus,statusCheckRollup
```

- `headRefOid` must equal the pushed SHA.
- `mergeable: MERGEABLE` means no content conflicts; `mergeStateStatus: BLOCKED` usually means a review, branch protection, or CI gate, not a merge conflict.
- If checks have not been created or are still running, report only local test results; never claim remote CI passed.

Once pushed and verified, delete `$WORK_BRANCH` (switch off it first).

### 9. Restore the Working Environment

After every PR is processed and before asking the user anything:

1. Switch back to `START_BRANCH` (if the starting state was a detached HEAD, `START_BRANCH` holds a SHA; use `git switch --detach "$START_BRANCH"`).
2. If step 1 stashed changes, restore them by SHA:

   ```bash
   git stash apply --index "$STASH_SHA"
   ```

   Only after it succeeds, find the entry matching `$STASH_SHA` in `git stash list` and `git stash drop` it. If restoring conflicts, keep the stash, do not drop it, and report the stash SHA and conflicting files.
3. Run `git status --short --branch` and confirm the state matches the start.
4. Keep the `$WORK_BRANCH` of each **Awaiting confirmation** PR; all other temporary branches have already been deleted.

### 10. Final Report and Consolidated Questions

Report grouped by Outcome Category. For each PR include:

- PR number, title, URL, and whether it is a draft.
- Overlap files.
- Result of the existing-implementation check and its evidence.
- Whether conflicts occurred, and for each one the file, both intents, and the resolution.
- Head SHA after rebase.
- The test commands actually run and their passed/failed counts.
- Push result, GitHub mergeability, and checks status.
- The exact reason for anything not pushed or skipped.

Then list every pending item at once and ask the user to answer each one:

- **Awaiting confirmation**: include the conflict resolution summary and the `git range-diff` output, and ask whether to push.
- **Needs decision**: for PRs with an existing implementation, ask whether to close, trim, or rebase as usual; for other blockers, ask for the next step.

### 11. Follow Up on the User's Answers

- **Confirm push**: switch to the PR's `$WORK_BRANCH` and run `git fetch HEAD_REMOTE HEAD_BRANCH`. If the remote still equals `OLD_SHA`, push with the original lease and complete the step 8 verification; if the remote changed, report the concurrent update and do not push. Afterwards return to `START_BRANCH` and delete `$WORK_BRANCH`. If the working tree changed in the meantime, stash and restore it the same way as steps 1 and 9.
- **Close PR**: only when the user explicitly answers close in that turn. The comment links the superseding upstream commit or PR:

  ```bash
  gh pr close PR_NUMBER --repo OWNER/REPO --comment "Superseded by UPSTREAM_REF."
  ```

- **Trim PR** or **rebase as usual**: restart that PR from step 3. When trimming, remove only the parts upstream already provides; do not add new features.

## Pitfalls

- Never use `git push --force`, or `--force-with-lease` without an expected SHA.
- Never push before testing, and never push a conflict resolution without confirmation.
- Never overwrite a same-named local branch with `git switch -C HEAD_BRANCH`; always use `upstream-pr-rebase/PR_NUMBER`.
- Never skip the existing-implementation check, the rebase, or tests just because there are no overlap files.
- Never report `BLOCKED` as a merge conflict.
- Never describe passing local tests as passing GitHub CI.
- Never overwrite commits someone else just pushed after a lease failure.
- Never `git stash pop` the top stash; restore only by the recorded `STASH_SHA`.
- Never push to a remote that does not match the PR's head repository.

## Verification

Before finishing, confirm:

- [ ] Every PR in the list is in exactly one Outcome Category, with a reason and evidence.
- [ ] Every PR that was rebased went through the existing-implementation check.
- [ ] Every push was preceded by diff validation and project tests, and used a lease with the exact `OLD_SHA`.
- [ ] For every pushed PR, GitHub `headRefOid` equals the pushed SHA and the remote branch is not behind the upstream base.
- [ ] No PR with resolved conflicts was pushed before user confirmation.
- [ ] Back on the starting branch, with the stash restored by SHA or explicitly reported.
- [ ] Every skip, failure, pending confirmation, and pending check is reported truthfully.
