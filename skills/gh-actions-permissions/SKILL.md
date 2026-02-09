---
name: gh-actions-permissions
description: Manage GitHub Actions workflow permissions using gh CLI. Use when: (1) Checking repository Actions permissions settings, (2) Enabling GitHub Actions to create or approve pull requests, (3) Troubleshooting workflow failures with "GitHub Actions is not permitted to create or approve pull requests" errors, (4) Configuring workflow permissions for tools like release-please that need PR creation access, or (5) Managing default_workflow_permissions and can_approve_pull_request_reviews settings.
---

# GitHub Actions Permissions Management

Manage GitHub Actions workflow permissions via gh CLI API, specifically for enabling Actions to create and approve pull requests.

## Common Issue

When GitHub Actions workflows (like release-please) fail with:

```
GitHub Actions is not permitted to create or approve pull requests
```

This occurs when the repository's workflow permissions block PR creation, even if the workflow file has correct `permissions:` declarations.

## Check Current Permissions

View the current workflow permission settings:

```bash
gh api repos/{owner}/{repo}/actions/permissions/workflow \
  --jq '{default_workflow_permissions: .default_workflow_permissions, can_approve_pull_request_reviews: .can_approve_pull_request_reviews}'
```

**Expected output:**
```json
{
  "default_workflow_permissions": "read",
  "can_approve_pull_request_reviews": false
}
```

When `can_approve_pull_request_reviews` is `false`, workflows cannot create PRs regardless of workflow-level permissions.

## Enable PR Creation Permission

Use PUT method (not PATCH) to update the setting:

```bash
gh api --method PUT repos/{owner}/{repo}/actions/permissions/workflow \
  -F default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=true
```

**Important:**
- Must use `PUT` method, not `PATCH` (PATCH returns 404)
- Must provide both parameters even if only changing one
- Requires `repo` scope in gh CLI authentication

Verify the change:

```bash
gh api repos/{owner}/{repo}/actions/permissions/workflow \
  --jq '.can_approve_pull_request_reviews'
```

Should return: `true`

## Permission Levels Explained

**default_workflow_permissions**: Controls base permissions for GITHUB_TOKEN
- `read`: Read-only access (recommended for security)
- `write`: Read and write access

**can_approve_pull_request_reviews**: Allows workflows to create/approve PRs
- `false`: Workflows cannot create or approve PRs (default, more secure)
- `true`: Workflows can create and approve PRs (needed for release automation)

## Workflow Architecture

Even when `can_approve_pull_request_reviews` is enabled, workflow files should explicitly declare permissions:

```yaml
permissions:
  contents: write
  pull-requests: write
```

This explicit declaration:
- Overrides repository default_workflow_permissions
- Documents required permissions in workflow file
- Follows principle of least privilege

## Rerun Failed Workflows

After enabling permissions, rerun the failed workflow:

```bash
gh run rerun {run-id}
```

Or watch the workflow execution:

```bash
gh run watch {run-id}
```

## Authentication Requirements

Verify gh CLI has sufficient permissions:

```bash
gh auth status
```

Required token scopes:
- `repo` - For repository settings access
- `workflow` - For workflow operations (if managing workflow files)

Refresh authentication if needed:

```bash
gh auth refresh -s repo
```
