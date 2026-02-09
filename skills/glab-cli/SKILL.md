---
name: glab-cli
description: GitLab CLI (glab) integration for managing repositories, merge requests, CI/CD pipelines, variables, and runners on self-managed GitLab instances. Use when working with GitLab - authentication issues ("token expired", "unauthorized"), repo operations ("create repo", "clone"), merge requests ("create MR", "view MR", "code review"), CI/CD pipelines ("check CI", "view job logs", "trigger job", "download artifacts"), variables ("list variables", "set variable"), or runners ("list runners").
---

# GitLab CLI (glab) Integration

Manage GitLab repositories, merge requests, CI/CD, variables, and runners with glab CLI.

## Prerequisites

```bash
glab auth status
```

If authentication fails, see [Authentication Setup](#authentication-setup).

---

## General Rules

1. **Prefer native `glab` commands over `glab api`** — native commands handle URL encoding via `-R <repo>`.
2. **Strip ANSI codes** when analyzing job logs: `| sed 's/\x1b\[[0-9;]*m//g'`
3. **Avoid TUI commands** (`glab ci view`) — crashes in non-interactive environments.
4. **URL encoding**: When using `glab api`, encode `/` as `%2F` in project paths.
5. **JSON output**: Use `--output=json` or `-F json` with `jq` for scripting and automation.
6. **API pagination**: Use `glab api --paginate "endpoint?per_page=100"` to auto-fetch all pages.
7. **Repo context**: glab auto-detects repo from git remote; use `-R owner/repo` when outside a repo directory.

---

## Quick Reference

| Task | Command |
|------|---------|
| Auth status | `glab auth status` |
| Create repo | `glab repo create <name> --group <group>` |
| Clone repo | `glab repo clone <owner/repo>` |
| Create MR | `glab mr create` |
| List MRs | `glab mr list` |
| View MR | `glab mr view <id>` |
| Add MR comment | `glab mr note <id> -m "comment"` |
| List pipelines | `glab ci list -R <repo>` |
| Pipeline info | `glab ci get -p <id> -R <repo> -F json` |
| Pipeline jobs | `glab ci get -p <id> -R <repo> --with-job-details -F json` |
| View job log | `glab ci trace <job-id> -R <repo>` |
| Trigger job | `glab ci trigger <job-id> -R <repo>` |
| Download artifacts (latest) | `glab job artifact <branch> <job-name> -R <repo>` |
| Download artifacts (by job ID) | `glab api /projects/<path>/jobs/<id>/artifacts > file.zip` |
| List variables | `glab variable list` |
| Set variable | `glab variable set <key> <value>` |
| List runners | `glab api projects/:fullpath/runners` (no native cmd) |

---

## Authentication Setup

### Check Status

```bash
glab auth status
```

### Token Expired or Not Initialized

If you see `token expired`, `unauthorized`, or `failed to authenticate`:

**Step 1: Create a Personal Access Token**

1. Open: https://gitlab.domain.com/-/user_settings/personal_access_tokens
2. Create token with scopes: `api` and `write_repository`
3. Copy the token immediately

**Step 2: Authenticate**

```bash
echo "<YOUR_TOKEN>" | glab auth login --hostname gitlab.domain.com --stdin --git-protocol ssh
```

**Step 3: Verify**

```bash
glab auth status
```

### Refresh OAuth Token

```bash
glab auth refresh --hostname gitlab.domain.com
```

**Note:** Only works for OAuth (interactive login), not PAT (`--stdin`).

---

## Repository Management

### Create Repository

**IMPORTANT: Correct syntax for nested groups**

```bash
# CORRECT: Use --group for the full group path, repo name separately
glab repo create my-project --group parent/child/subgroup --private

# WRONG: Don't put the full path as the repo name
glab repo create parent/child/subgroup/my-project  # Will fail
```

**Examples:**

```bash
# In user namespace
glab repo create my-project

# In a group
glab repo create my-project --group my-group

# In nested group with options
glab repo create packer-lab \
  --group my-org/my-team/my-subgroup \
  --description "Project description" \
  --private \
  --defaultBranch main
```

After creating, glab initializes a new git repo in `./my-project/`. If you already have a local repo:

```bash
rm -rf ./my-project
git remote add origin git@gitlab.domain.com:group/my-project.git
git push -u origin main
```

**Visibility:** `--private` | `--public` | `--internal`

### Find Available Groups

```bash
glab api "groups?search=devops" | jq -r '.[] | "\(.full_path) (id: \(.id))"'
glab api groups --paginate | jq -r '.[] | .full_path'
```

### Clone Repository

```bash
glab repo clone owner/repo
glab repo clone owner/repo target-dir
glab repo clone -g group-name  # Clone all in group
```

### Fork & View

```bash
glab repo fork owner/repo
glab repo view
glab repo view --web
```

---

## Merge Request Operations

### Create MR

```bash
glab mr create
glab mr create --title "feat: add feature" --description "desc"
glab mr for 123  # From issue
```

### List MRs

```bash
glab mr list
glab mr list --assignee=@me
glab mr list --reviewer=@me
glab mr list --state merged --author @me
```

### View & Checkout

```bash
glab mr view 123
glab mr view 123 --web
glab mr diff 123
glab mr checkout 123
```

### Code Review (CE Compatible)

```bash
glab mr note 123 -m "LGTM! Nice work."
glab mr merge 123
glab mr merge 123 --squash
glab mr merge 123 --when-pipeline-succeeds  # Auto-merge after CI passes
glab mr close 123
glab mr reopen 123
```

### Inline Comment (via API)

```bash
glab api projects/:fullpath/merge_requests/123/discussions \
  --method POST \
  -f body="Comment here" \
  -f "position[base_sha]=<base>" \
  -f "position[head_sha]=<head>" \
  -f "position[start_sha]=<start>" \
  -f "position[position_type]=text" \
  -f "position[new_path]=file.go" \
  -f "position[new_line]=42"
```

Get SHA values: `glab mr view 123 --json diffRefs`

### Premium/EE Only

```bash
glab mr approve 123    # Premium/EE only
glab mr revoke 123     # Premium/EE only
```

---

## CI/CD Pipeline & Jobs

For complete reference including all commands, monitoring patterns, artifacts, and debugging workflows, see [references/cicd-pipelines.md](references/cicd-pipelines.md).

### Most Common Operations

```bash
# List recent pipelines
glab ci list --per-page 5

# Get pipeline info as JSON
glab ci get -p <pipeline-id> -R <repo> -F json

# Get pipeline jobs
glab ci get -p <pipeline-id> -R <repo> --with-job-details -F json | jq '.jobs[] | {id, name, status, stage}'

# View job logs (strip ANSI codes)
glab ci trace <job-id> -R <repo> | sed 's/\x1b\[[0-9;]*m//g'

# Trigger manual job
glab ci trigger <job-id> -R <repo>

# Retry failed job
glab ci retry <job-id> -R <repo>

# Run new pipeline
glab ci run -b main

# Download artifacts (latest pipeline)
glab job artifact <branch> <job-name> -R <repo>

# Download artifacts (specific job ID, via API)
glab api /projects/<url-encoded-path>/jobs/<job-id>/artifacts > artifacts.zip

# CI lint
glab ci lint
```

**Note:** `glab job artifact` only downloads from the **latest pipeline** of a branch. For specific job IDs, use the API.

---

## CI/CD Variables

```bash
glab variable list
glab variable get MY_VAR
glab variable set MY_VAR "value"
glab variable delete MY_VAR

# Advanced options
glab variable set MY_VAR "value" --protected   # Only on protected branches
glab variable set MY_VAR "value" --masked      # Hidden in logs
glab variable set MY_VAR "value" --scope production
glab variable set MY_CERT --value-file /path/to/cert.pem

# Backup and restore
glab variable export > variables.json
glab variable import < variables.json
```

---

## Runner Status (via API)

No native `runner` command exists. Use `glab api`.

```bash
# List project runners
glab api projects/:fullpath/runners | jq '.[] | {id, description, status, is_shared}'

# Online only
glab api projects/:fullpath/runners --field status=online

# Runner details
glab api runners/<runner-id>
glab api runners/<runner-id>/jobs

# Group runners
glab api groups/<group-id>/runners
```

---

## Errors & Debugging

For common error solutions (401, HTTP 405, namespace not found, TUI panic, URL encoding), see [references/troubleshooting.md](references/troubleshooting.md).

For CI/CD failure debugging workflow (list pipelines -> find failed jobs -> view logs -> retry), see [references/cicd-pipelines.md](references/cicd-pipelines.md#debugging-ci-failures-workflow).
