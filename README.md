# my-agent-config

Shared [Claude Code](https://claude.com/claude-code) skills and agent configuration.

## Install

### All Skills

```bash
curl -sL https://github.com/chenwei791129/my-agent-config/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=2 -C ~/.claude/skills/ my-agent-config-main/skills/
```

### A Single Skill

Replace `<skill-name>` with the skill directory name (e.g. `chrome-devtools`):

```bash
curl -sL https://github.com/chenwei791129/my-agent-config/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=2 -C ~/.claude/skills/ my-agent-config-main/skills/<skill-name>
```

Example:

```bash
curl -sL https://github.com/chenwei791129/my-agent-config/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=2 -C ~/.claude/skills/ my-agent-config-main/skills/chrome-devtools
```

## Available Skills

| Skill | Description |
|-------|-------------|
| `acli-jira` | Jira CLI operations and JQL queries |
| `chrome-devtools` | Launch Chrome with remote debugging for DevTools MCP integration |
| `deep-research` | Deep multi-step web research using Agent Teams for parallel, coordinated investigation |
| `gh-actions-permissions` | GitHub Actions workflow permissions management |
| `glab-cli` | GitLab CLI repository and CI/CD management |
| `go-concurrency-patterns` | Go concurrency programming and goroutine patterns |
| `imagen` | AI image generation using Google Gemini |
| `postgres` | Read-only SQL query execution for PostgreSQL |
| `powershell-style-guide` | PowerShell code style and best practices review |
| `prompt-engineering` | LLM prompt optimization and design patterns |
| `shell-style-guide` | Shell/Bash code style review guide |
| `slack-notify` | Send Slack notifications via Incoming Webhook with mrkdwn support |
| `styling` | CSS and Tailwind styling best practices |
