# CI/CD Pipeline & Jobs - Complete Reference

## Contents

- [General Rules](#general-rules)
- [Pipeline Status](#pipeline-status)
- [View Pipeline Info](#view-pipeline-info)
- [List Pipeline Jobs](#list-pipeline-jobs)
- [Trigger Manual Job](#trigger-manual-job)
- [Monitor Job Status](#monitor-job-status)
- [Job Logs](#job-logs)
- [Job Artifacts](#job-artifacts)
- [Job Operations](#job-operations)
- [Pipeline Control](#pipeline-control)
- [CI Lint](#ci-lint)
- [Pipeline Schedules](#pipeline-schedules)
- [Debugging CI Failures Workflow](#debugging-ci-failures-workflow)

---

## General Rules

1. **Always prefer native `glab ci` commands over `glab api`** — native commands handle URL encoding automatically via `-R <repo>` flag.
2. **Always strip ANSI color codes** when analyzing job logs: `| sed 's/\x1b\[[0-9;]*m//g'`
3. **Avoid TUI commands** (`glab ci view`, `glab ci view --live`) — they crash in non-interactive environments (SSH, automation, Claude Code).
4. Only use `glab api` when: (a) no native command exists (e.g., runners), (b) you need specific API fields not in native output, or (c) scripting multi-project workflows.

---

## Pipeline Status

```bash
glab ci status
glab ci list
glab ci list --per-page 5
```

---

## View Pipeline Info

```bash
# Basic info
glab ci get -p <pipeline-id> -R <repo>

# JSON output for scripting
glab ci get -p <pipeline-id> -R <repo> -F json | jq '{id, status, ref, web_url}'
```

---

## List Pipeline Jobs

```bash
# All jobs
glab ci get -p <pipeline-id> -R <repo> --with-job-details -F json | jq '.jobs[] | {id, name, status, stage}'

# Current branch (inside repo)
glab ci get --with-job-details -F json

# Failed jobs only
glab ci get -p <pipeline-id> -R <repo> --with-job-details -F json | \
  jq '.jobs[] | select(.status=="failed") | {id, name, status, stage}'
```

---

## Trigger Manual Job

**Native command (recommended):**

```bash
# By job ID or name
glab ci trigger <job-id>
glab ci trigger <job-name>

# Specify branch or pipeline
glab ci trigger <job-name> -b main
glab ci trigger <job-id> -p <pipeline-id>

# Other repo
glab ci trigger <job-id> -R <repo>
```

**API fallback:**

```bash
glab api -X POST /projects/<url-encoded-path>/jobs/<job-id>/play | jq '{id, name, status, web_url}'
```

---

## Monitor Job Status

**Real-time log streaming (blocks until job completes):**

```bash
glab ci trace <job-id> -R <repo>
```

**Polling with native command:**

```bash
PIPELINE_ID="<pipeline-id>"
REPO="<repo>"

for i in {1..60}; do
  status=$(glab ci get -p $PIPELINE_ID -R $REPO -F json | jq -r '.status')
  echo "[$(date '+%H:%M:%S')] Pipeline status: $status"

  if [ "$status" = "success" ] || [ "$status" = "failed" ]; then
    echo "Pipeline completed! Final status: $status"
    glab ci get -p $PIPELINE_ID -R $REPO --with-job-details -F json | jq '.jobs[] | {name, status}'
    break
  fi

  sleep 5
done
```

---

## Job Logs

```bash
# By job ID or name
glab ci trace <job-id>
glab ci trace <job-name>

# Specify branch or pipeline
glab ci trace <job-name> -b main
glab ci trace <job-id> -p <pipeline-id>

# Other repo
glab ci trace <job-id> -R <repo>

# Always strip ANSI codes for analysis
glab ci trace <job-id> | sed 's/\x1b\[[0-9;]*m//g'
glab ci trace <job-id> | sed 's/\x1b\[[0-9;]*m//g' | tail -100
glab ci trace <job-id> | sed 's/\x1b\[[0-9;]*m//g' | grep -i error
```

**API fallback:**

```bash
glab api /projects/<url-encoded-path>/jobs/<job-id>/trace | tail -100
```

---

## Job Artifacts

**Native command (latest pipeline of a branch only):**

```bash
# Download artifacts from latest pipeline on a branch
glab job artifact <branch> <job-name> -R <repo>

# Download to specific directory
glab job artifact <branch> <job-name> --path ./artifacts/ -R <repo>
```

**Note:** `glab job artifact` only works for the **latest pipeline** of a branch. For specific job IDs, use the API.

**Note:** The deprecated `glab ci artifact` has incorrect help text. Always use `glab job artifact`.

**API (specific job ID — recommended for historical jobs):**

```bash
# Download all artifacts as zip
glab api /projects/<url-encoded-path>/jobs/<job-id>/artifacts > artifacts.zip
unzip artifacts.zip -d ./artifacts/

# Download a single file from artifacts
glab api "/projects/<url-encoded-path>/jobs/<job-id>/artifacts/path/to/file.log"
```

**Check if job has artifacts:**

```bash
glab api /projects/<url-encoded-path>/jobs/<job-id> | jq '{id, name, status, artifacts}'
```

---

## Job Operations

```bash
# Retry job
glab ci retry <job-id>
glab ci retry <job-name>
glab ci retry <job-name> -b main -R <repo>

# Cancel job
glab ci cancel job <job-id>
```

---

## Trigger Job Workflow

**IMPORTANT: When asked to "trigger a job" or "run scan", do NOT use `glab ci run`.** Most projects use `workflow:rules` that restrict pipeline creation to `push`/`schedule`/`merge_request` sources, so `glab ci run` (which uses API source) will fail with `400 Pipeline filtered out by workflow rules`.

**Correct approach — find and trigger existing manual jobs:**

```bash
# Step 1: Find the latest pipeline (push events auto-create pipelines)
glab ci list --per-page 3 -F json | jq '.[] | {id, status, ref}'

# Step 2: List jobs and find the manual one
glab ci get -p <pipeline-id> --with-job-details -F json | \
  jq '.jobs[] | {id, name, status, stage}'

# Step 3: Trigger the manual job by ID
glab ci trigger <job-id>
```

**Only use `glab ci run` when:**
- There is no existing pipeline on the target branch
- AND the project's `workflow:rules` explicitly allow `api` or `trigger` source
- This is rare in practice

---

## Pipeline Control

```bash
# Run new pipeline (CAUTION: often blocked by workflow:rules, see "Trigger Job Workflow" above)
glab ci run
glab ci run -b main
glab ci run --variables "KEY:value"

# Retry/cancel/delete pipeline
glab ci retry
glab ci cancel
glab ci delete <pipeline-id>
```

---

## CI Lint

```bash
glab ci lint
```

---

## Pipeline Schedules

```bash
# List pipeline schedules
glab schedule list

# Create schedule
glab schedule create --cron "0 2 * * *" --ref main --description "Nightly build"

# Run schedule immediately
glab schedule run <schedule-id>

# Delete schedule
glab schedule delete <schedule-id>
```

---

## Debugging CI Failures Workflow

**Step 1: List recent pipelines**

```bash
glab ci list -R <repo> --per-page 5
```

**Step 2: Get failed jobs**

```bash
glab ci get -p <pipeline-id> -R <repo> --with-job-details -F json | \
  jq '.jobs[] | select(.status=="failed") | {id, name, failure_reason}'
```

**Step 3: Get error logs (strip ANSI codes)**

```bash
glab ci trace <job-id> -R <repo> | sed 's/\x1b\[[0-9;]*m//g' | tail -50
glab ci trace <job-id> -R <repo> | sed 's/\x1b\[[0-9;]*m//g' | grep -i error
```

**Step 4: Retry if needed**

```bash
glab ci retry <job-name> -p <pipeline-id> -R <repo>
```
