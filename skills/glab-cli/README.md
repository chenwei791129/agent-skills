# glab-cli Skills

GitLab CLI (glab) integration skills for Claude Code.

## Prerequisites

1. Install glab CLI: https://docs.gitlab.com/cli/
2. Authenticate: `glab auth login`

## Available Skills

| Skill | Description | Trigger Examples |
|-------|-------------|------------------|
| `auth` | Authentication management | "token expired", "setup glab", "auth status" |
| `repo` | Repository operations | "create repo", "clone project", "fork repo" |
| `mr` | Merge Request & Code Review | "create MR", "view MR 123", "list my MRs" |
| `ci` | Pipeline & Job management | "check CI", "view job logs", "run pipeline" |
| `variable` | CI/CD Variables | "list variables", "set variable", "get variable" |
| `runner` | Runner status (via API) | "list runners", "check runner status" |

## Quick Start

```bash
# Check authentication
glab auth status

# If not authenticated, see auth skill for setup guide
```

## GitLab CE Compatibility

These skills are designed to work with GitLab Community Edition (CE). Features that require Premium/Enterprise Edition are clearly marked.

**CE Compatible:**
- All `repo`, `ci`, `variable`, `runner` operations
- MR create, list, view, diff, note, merge

**Premium/EE Only:**
- `glab mr approve`
- `glab mr revoke`

## Self-Managed GitLab

For self-managed GitLab instances (e.g., gitlab.example.com):

```bash
echo "<YOUR_TOKEN>" | glab auth login --hostname gitlab.example.com --stdin --git-protocol ssh
```

See `auth` skill for detailed setup instructions.

## Resources

- [GitLab CLI Documentation](https://docs.gitlab.com/cli/)
- [glab GitHub Repository](https://github.com/gl-cli/glab)
