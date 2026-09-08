# acli jira Command Reference

## Table of Contents

1. [workitem](#workitem)
2. [project](#project)
3. [board](#board)
4. [sprint](#sprint)
5. [filter](#filter)
6. [auth](#auth)

---

## workitem

### view

View work item details.

```bash
acli jira workitem view KEY-123 --json
acli jira workitem view KEY-123 --fields "summary,status,assignee" --json
acli jira workitem view KEY-123 --fields '*navigable' --json
acli jira workitem view KEY-123 --web  # opens in browser
```

**Flags:**
- `-f, --fields string`: Comma-separated fields. Special values: `*all`, `*navigable`. Prefix with `-` to exclude.
- `--json`: JSON output (required for reliable output)
- `-w, --web`: Open in browser

### search

Search work items with JQL.

```bash
acli jira workitem search --jql "project = PROJ" --limit 10 --json
acli jira workitem search --jql "project = PROJ AND status != Done" --json
acli jira workitem search --jql "assignee = currentUser()" --paginate --json
acli jira workitem search --filter 10001 --json  # use saved filter
```

**Flags:**
- `-j, --jql string`: JQL query
- `--filter string`: Filter ID
- `-l, --limit int`: Max results
- `--paginate`: Fetch all pages
- `-f, --fields string`: Output fields (default: issuetype,key,assignee,priority,status,summary)
- `--json`: JSON output

### comment list

List comments on a work item.

```bash
acli jira workitem comment list --key PROJ-123 --json
acli jira workitem comment list --key PROJ-123 --limit 10 --order "-created" --json
```

**Flags:**
- `--key string`: Work item key (required)
- `--limit int`: Max comments (default 50)
- `--order string`: Order by field (created, updated, prefix with - for desc)
- `--paginate`: Fetch all pages
- `--json`: JSON output

### attachment list

List attachments on a work item.

```bash
acli jira workitem attachment list --key PROJ-123 --json
```

**Flags:**
- `--key string`: Work item key (required)
- `--json`: JSON output

### link list

List links on a work item.

```bash
acli jira workitem link list --key PROJ-123 --json
```

**Flags:**
- `--key string`: Work item key (required)
- `--json`: JSON output

### Write Operations (Use with Caution)

Check `<subcommand> --help` before unfamiliar or bulk writes because flags may change between `acli` releases. Current commands use flag-based selectors rather than positional work item keys.

```bash
# Create
acli jira workitem create --project PROJ --type Task --summary "Title" --json

# Create a subtask
acli jira workitem create \
  --project PROJ \
  --type Subtask \
  --parent PROJ-100 \
  --summary "Title" \
  --assignee "user@example.com" \
  --json

# Edit
acli jira workitem edit --key KEY-123 --summary "New title" --json

# Transition one or more work items
acli jira workitem transition --key "KEY-123,KEY-124" --status "Done" --yes --json

# Transition a scoped JQL result set
acli jira workitem transition \
  --jql 'parent = PROJ-100 AND status != Done' \
  --status "Done" \
  --yes \
  --json

# Comment
acli jira workitem comment create --key KEY-123 --body "Comment text" --json

# Assign
acli jira workitem assign --key KEY-123 --assignee "user@example.com" --yes --json
```

After a bulk write, query the same bounded key/JQL set and verify the resulting count and field values. Do not blindly retry `workitem create`; first check whether Jira created the expected item despite a lost CLI response.

---

## project

### view

View project details.

```bash
acli jira project view --key PROJ --json
```

**Flags:**
- `--key string`: Project key (required)
- `--json`: JSON output

### list

List visible projects.

```bash
acli jira project list --limit 30 --json
acli jira project list --recent --json  # up to 20 recently viewed
acli jira project list --paginate --json  # all projects
```

**Flags:**
- `-l, --limit int`: Max projects (default 30)
- `--recent`: Recently viewed (max 20)
- `--paginate`: Fetch all
- `--json`: JSON output

---

## board

### search

Search boards.

```bash
acli jira board search --limit 10 --json
acli jira board search --project PROJ --json
acli jira board search --name "Sprint" --type scrum --json
```

**Flags:**
- `--name string`: Filter by name (partial match)
- `--project string`: Filter by project key
- `--type string`: scrum, kanban, simple
- `--limit int`: Max results (default 50)
- `--paginate`: Fetch all
- `--json`: JSON output

### list-sprints

List sprints for a board.

```bash
acli jira board list-sprints --id 123 --json
acli jira board list-sprints --id 123 --state active,closed --json
```

**Flags:**
- `--id string`: Board ID (required)
- `--state string`: future, active, closed (comma-separated)
- `--limit int`: Max results (default 50)
- `--paginate`: Fetch all
- `--json`: JSON output

### get

Get board details.

```bash
acli jira board get --id 123 --json
```

---

## sprint

### view

View sprint details.

```bash
acli jira sprint view --id 456 --json
```

### list-workitems

List work items in a sprint.

```bash
acli jira sprint list-workitems --id 456 --json
```

---

## filter

### list

List filters.

```bash
acli jira filter list --my --json
acli jira filter list --favourite --json
```

**Flags:**
- `--my`: My filters
- `--favourite`: Favourite filters
- `--json`: JSON output

### get

Get filter by ID.

```bash
acli jira filter get --id 10001 --json
```

### search

Search filters.

```bash
acli jira filter search --name "Sprint" --json
```

---

## auth

### status

Check authentication status.

```bash
acli jira auth status
```

Returns: Site, Email, Authentication Type

### switch

Switch between configured accounts (if multiple).

```bash
acli jira auth switch
```
