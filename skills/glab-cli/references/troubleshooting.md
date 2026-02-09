# Common Errors & Solutions

## Contents

- [401 Unauthorized](#401-unauthorized)
- [HTTP 405 - Non GET methods not allowed for moved projects](#http-405---non-get-methods-not-allowed-for-moved-projects)
- [Could not find group or namespace](#could-not-find-group-or-namespace)
- [TUI panic (glab ci view)](#tui-panic-glab-ci-view)
- [URL encoding in project path](#url-encoding-in-project-path)

---

## 401 Unauthorized

**Cause:** Token expired or not authenticated.

```bash
# Check auth status
glab auth status

# Re-authenticate (see Authentication Setup in SKILL.md)
```

---

## HTTP 405 - Non GET methods not allowed for moved projects

**Cause:** Project was moved or renamed. POST/PUT/DELETE requests fail on old project path.

```
glab: Non GET methods are not allowed for moved projects (HTTP 405)
```

**Solution:**

```bash
# 1. Update git remote URL to new project path
git remote set-url origin git@gitlab.domain.com:new/project/path.git

# 2. Verify
git remote -v

# 3. Use the new project path in API calls
glab api -X POST /projects/new%2Fproject%2Fpath/jobs/123/play
```

**Note:** GET requests may still work on old path, but POST/PUT/DELETE require the new path.

---

## Could not find group or namespace

**Cause:** Using full path `group/subgroup/repo` as the repo name.

```bash
# Wrong
glab repo create my-org/my-team/my-subgroup/my-repo

# Correct — use --group for the namespace
glab repo create my-repo --group my-org/my-team/my-subgroup
```

---

## TUI panic (glab ci view)

**Cause:** `glab ci view` opens interactive TUI, which crashes in non-interactive environments.

```
panic: close of nil channel
goroutine 1 [running]:
github.com/gdamore/tcell/v2.(*tScreen).finish(...)
```

**Solution:** Use non-interactive commands instead:

```bash
# Avoid
glab ci view

# Use instead
glab ci list -R <repo>
glab ci get -p <pipeline-id> -R <repo> --with-job-details -F json
```

---

## URL encoding in project path

**Cause:** Project path contains `/` which must be URL-encoded as `%2F` when using `glab api`.

```bash
# Wrong
glab api /projects/group1/subgroup/myrepo/jobs/123

# Correct
glab api /projects/group1%2Fsubgroup%2Fmyrepo/jobs/123
```

**Tip:** Prefer native `glab ci` commands with `-R <repo>` flag to avoid URL encoding entirely.
