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
| `facebook-scraper` | Scrape Facebook group/page posts (text, images, top-level comments) into a Markdown report via patchright |
| `find-claude-session` | Search across past Claude Code sessions to recall what was discussed and locate the original cwd |
| `finmind` | Query Taiwan stock financial reports (income, balance sheet, cash flow, revenue, PER) via FinMind API |
| `gh-actions-permissions` | GitHub Actions workflow permissions management |
| `glab-cli` | GitLab CLI repository and CI/CD management |
| `go-concurrency-patterns` | Go concurrency programming and goroutine patterns |
| `grafana` | Operate a self-hosted Grafana from the terminal via the gcx CLI — dashboards, datasource queries (PromQL/LogQL/TraceQL), alerts, and dashboards-as-code |
| `malware-repo-analysis` | Malware and supply chain attack detection in third-party git repositories using Agent Teams parallel analysis |
| `ndc-lightscore` | Fetch Taiwan NDC 景氣對策信號 latest score, historical scores, red-light streaks, and next publish date |
| `newcity` | Query mail/parcels, community points, and announcements (with attachments) from the Newcity community property app (itlife.com.tw / NewcityWebApi) |
| `postgres` | Read-only SQL query execution for PostgreSQL |
| `powershell-style-guide` | PowerShell code style and best practices review |
| `pre-goal` | Turn a vague task into a well-bounded goal prompt (Outcome, Verification, Constraints, Iteration Policy, Error Handling) before launching /goal |
| `prompt-engineering` | LLM prompt optimization and design patterns |
| `reimburse-request` | Submit a company expense reimbursement (請款) on reimburse.digital via the agent-browser CLI — logs in through your org SSO, fills the Benefit/Others claim form, attaches the receipt, and submits |
| `sap-leave-request` | Submit a full-day leave / time-off request (incl. sick leave with proof attachment) in SAP SuccessFactors via the agent-browser CLI |
| `shell-style-guide` | Shell/Bash code style review guide |
| `slack-notify` | Send Slack notifications via Incoming Webhook with mrkdwn support |
| `styling` | CSS and Tailwind styling best practices |
| `tw-trading-agents` | Multi-agent Taiwan-stock investment research using the TradingAgents methodology and FinMind data |
| `youtube-transcribe` | Transcribe a YouTube video or local audio/video file into text/SRT/JSON locally (mlx-whisper on Apple Silicon, faster-whisper elsewhere) |
