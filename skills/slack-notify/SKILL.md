---
name: slack-notify
description: "Send Slack notifications via Incoming Webhook with mrkdwn formatting. Use this skill whenever: (1) you need to send a message or notification to Slack, (2) alerting users about task completion or results, (3) sharing summaries, reports, or status updates to a Slack channel, (4) another skill or workflow needs to notify someone via Slack. Even if the user doesn't say 'Slack' explicitly, use this skill when they mention sending notifications, alerting a channel, or posting updates."
---

# Slack Notify

Send messages to Slack channels via Incoming Webhook with mrkdwn formatting support.

## Prerequisites

A Slack Incoming Webhook URL is required. Provide it via either:

1. **Environment variable** (recommended for repeated use):
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx"
   ```
2. **`--webhook-url` argument** (for one-off or per-channel sends):
   ```bash
   uv run scripts/send_slack.py --webhook-url "https://hooks.slack.com/services/..." --text "hello"
   ```

The `--webhook-url` argument takes priority over the environment variable when both are present.

## Usage

Send a simple message:
```bash
uv run scripts/send_slack.py --text "Deployment complete :rocket:"
```

Send with mrkdwn formatting:
```bash
uv run scripts/send_slack.py --text "*Build succeeded*\nBranch: \`main\`\nCommit: <https://github.com/org/repo/commit/abc123|abc123>"
```

Send a multiline message via stdin (useful for longer content):
```bash
cat <<'EOF' | uv run scripts/send_slack.py
*Daily Report* :bar_chart:

> Total requests: 12,345
> Error rate: 0.02%
> P99 latency: 120ms

_Generated at 2025-03-22 09:00 UTC_
EOF
```

Send to a specific webhook (overrides env var):
```bash
uv run scripts/send_slack.py --webhook-url "https://hooks.slack.com/services/T.../B.../xxx" --text "Alert!"
```

## Arguments

| Argument | Description |
|----------|-------------|
| `--text`, `-t` | Message text in mrkdwn format |
| `--webhook-url` | Incoming Webhook URL (overrides `SLACK_WEBHOOK_URL`) |
| (stdin) | If `--text` is not provided, reads message from stdin |

## mrkdwn Quick Reference

Slack uses its own markup syntax called mrkdwn (not standard Markdown). Key differences from Markdown:

| Syntax | Renders as |
|--------|------------|
| `*bold*` | **bold** |
| `_italic_` | _italic_ |
| `~strikethrough~` | ~~strikethrough~~ |
| `` `inline code` `` | `inline code` |
| ` ```code block``` ` | code block |
| `> quote` | blockquote |
| `\n` | newline (in --text arg) |
| `<URL\|display text>` | hyperlink |
| `<@U012ABC>` | mention user |
| `<!channel>` | @channel |
| `<!here>` | @here |
| `:emoji_name:` | emoji |

Important rules:
- Slack mrkdwn is NOT standard Markdown. `**bold**` will not work — use `*bold*` instead.
- Formatting markers (`*`, `_`, `~`, `` ` ``) MUST have a whitespace or newline before the opening marker. They will NOT render after punctuation (especially CJK punctuation like `：`, `，`, `。`). For example:
  - `狀態： *running*` — works (space before `*`)
  - `狀態：*running*` — broken (no space before `*`)
  - `*running*` at line start — works

## Workflow

When using this skill to send notifications:

1. Compose the message content using mrkdwn syntax
2. Choose the delivery method:
   - `--text` for single-line or short messages
   - stdin pipe for multiline or template-based messages
3. Run the script via `uv run`
4. Verify the output is `ok`

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Message sent successfully |
| 1 | Error (missing webhook URL, missing message, or Slack API error) |

## Troubleshooting

| Error | Solution |
|-------|----------|
| "no webhook URL provided" | Set `SLACK_WEBHOOK_URL` env var or pass `--webhook-url` |
| "no message provided" | Pass `--text` or pipe content via stdin |
| Slack returned non-200 | Check webhook URL is valid and not revoked |
| "channel_not_found" | The webhook's associated channel was deleted |
| "invalid_payload" | Check message formatting — mrkdwn syntax may be malformed |
