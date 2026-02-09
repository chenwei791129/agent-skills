---
name: acli-jira
description: Atlassian CLI (acli) for Jira operations. Use when working with Jira issues via command line - viewing tickets ("view PROJ-123", "show ticket"), searching with JQL ("find issues", "search Jira"), listing projects/boards/sprints, viewing comments/attachments/links, or any Jira query that benefits from CLI output. Prefer acli over MCP tools for structured JSON output and complex JQL queries.
---

# Atlassian CLI (acli) for Jira

Use `acli jira` for Jira Cloud operations via command line.

## Critical: Always Use --json Flag

**The text/table output format has bugs.** Always add `--json` to commands for reliable output:

```bash
# CORRECT - always use --json
acli jira workitem view KEY-123 --json
acli jira workitem search --jql "project = PROJ" --json

# INCORRECT - will often fail with "unexpected error"
acli jira workitem view KEY-123
acli jira workitem search --jql "project = PROJ" --csv
```

## Intermittent API Errors

acli has **intermittent "unexpected error" failures** (~60-80% failure rate). This is an API/network issue, not syntax-related. **Retry the command** if it fails:

```bash
# If this fails, just run it again
acli jira workitem view PROJ-123 --json
# Error: unexpected error, trace id: xxx  <-- retry!
```

For critical operations, consider using MCP tools which are more reliable.

## Custom Fields (Example Mappings)

Common custom field mappings for JSM tickets:

| Field Name | Custom Field ID | Example Value |
|------------|-----------------|---------------|
| Related Project(s) | `customfield_10735` | `["My-Project"]` |
| Root Cause | `customfield_10536` | Text description |
| Root Cause Category | `customfield_10560` | `"Coding Bug"` |
| Resolution | `customfield_11506` | Text description |
| Impact Summary | `customfield_11371` | Markdown table |
| Severity | `customfield_10530` | `"High"`, `"Medium"`, `"Low"` |
| Reporter Type | `customfield_10531` | `"Monitoring System"`, `"CS"` |

**Limitation:** acli `--fields` flag does NOT work reliably with custom fields. For custom fields, use MCP tool instead:

```bash
# This will FAIL
acli jira workitem view PROJ-123 --fields "customfield_10536" --json

# Use MCP tool instead (fields: "*all")
mcp__atlassian__jira_get_issue(issue_key="PROJ-123", fields="*all")
```

## Common Operations

### View a Ticket

```bash
acli jira workitem view PROJ-123 --json
```

Default fields: `key,issuetype,summary,status,assignee,description`

**Note:** `--fields '*navigable'` often fails. Use default fields or MCP tool for custom fields.

### Search with JQL

```bash
# Basic project search
acli jira workitem search --jql "project = PROJ" --limit 10 --json

# With pagination for large results
acli jira workitem search --jql "project = PROJ" --paginate --json
```

**JQL Limitations:** Some JQL queries fail. If `key = PROJ-123` fails, use `workitem view` instead:

```bash
# This may fail
acli jira workitem search --jql "key = PROJ-123" --json

# Use this instead
acli jira workitem view PROJ-123 --json
```

### Comments, Attachments, Links

```bash
acli jira workitem comment list --key PROJ-123 --json
acli jira workitem attachment list --key PROJ-123 --json
acli jira workitem link list --key PROJ-123 --json
```

### Projects and Boards

```bash
acli jira project view --key PROJ --json
acli jira board search --limit 10 --json
acli jira board list-sprints --id 123 --json
```

## Command Reference

See [references/commands.md](references/commands.md) for full command list and parameters.

## When to Use acli vs MCP

| Use Case | Recommended Tool |
|----------|------------------|
| View basic ticket info | `acli jira workitem view` |
| Search with simple JQL | `acli jira workitem search` |
| List projects/boards/sprints | `acli` commands |
| Get custom fields (Root Cause, etc.) | `mcp__atlassian__jira_get_issue` with `fields="*all"` |
| Complex JQL with filters | MCP tool |

## Authentication

Check status: `acli jira auth status`

Authentication is configured outside this skill. If auth fails, verify API token configuration.
