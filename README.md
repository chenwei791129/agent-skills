# agent-skills

Shared [Claude Code](https://claude.com/claude-code) skills and agent configuration.

## Install

Requires [GitHub CLI](https://cli.github.com/) `2.90+` with the `skill` subcommand.

### A Single Skill

Replace `<skill-name>` with the skill directory name (e.g. `chrome-devtools`):

```bash
gh skill install chenwei791129/agent-skills <skill-name> --agent claude-code --scope user
```

Example:

```bash
gh skill install chenwei791129/agent-skills chrome-devtools --agent claude-code --scope user
```

### Pick Skills Interactively

Omit the skill name to choose from a list:

```bash
gh skill install chenwei791129/agent-skills --agent claude-code --scope user
```

### Update Installed Skills

```bash
gh skill update --all
```

## Available Skills

| Skill | Description |
|-------|-------------|
| `acli-jira` | Jira CLI operations and JQL queries |
| `buffett-investment-strategy` | Warren Buffett's investment analysis framework from 60 years of Berkshire Hathaway letters and annual meetings |
| `chrome-devtools` | Launch Chrome with remote debugging for DevTools MCP integration |
| `deep-research` | Deep multi-step web research using Agent Teams for parallel, coordinated investigation |
| `finmind` | Query Taiwan stock financial reports (income, balance sheet, cash flow, revenue, PER) via FinMind API |
| `gh-actions-permissions` | GitHub Actions workflow permissions management |
| `glab-cli` | GitLab CLI repository and CI/CD management |
| `go-concurrency-patterns` | Go concurrency programming and goroutine patterns |
| `imagen` | AI image generation using Google Gemini |
| `malware-repo-analysis` | Malware and supply chain attack detection in third-party git repositories using Agent Teams parallel analysis |
| `postgres` | Read-only SQL query execution for PostgreSQL |
| `powershell-style-guide` | PowerShell code style and best practices review |
| `prompt-engineering` | LLM prompt optimization and design patterns |
| `shell-style-guide` | Shell/Bash code style review guide |
| `slack-notify` | Send Slack notifications via Incoming Webhook with mrkdwn support |
| `styling` | CSS and Tailwind styling best practices |
