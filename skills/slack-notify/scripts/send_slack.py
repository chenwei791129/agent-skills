#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["slack_sdk"]
# ///

"""
Send Slack notifications via Incoming Webhook with mrkdwn support.

Environment variables:
  SLACK_WEBHOOK_URL - Default Incoming Webhook URL (overridden by --webhook-url)

Usage:
  uv run scripts/send_slack.py --text "*Hello* from _Claude_!"
  uv run scripts/send_slack.py --webhook-url https://hooks.slack.com/... --text "test"
  echo "multiline\nmessage" | uv run scripts/send_slack.py

Output:
  Prints "ok" to stdout on success.
  Exits with code 1 on failure.
"""

import argparse
import os
import signal
import sys

from slack_sdk.webhook import WebhookClient


def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


def resolve_webhook_url(cli_url: str | None) -> str:
    """Return the webhook URL from --webhook-url arg or SLACK_WEBHOOK_URL env var."""
    url = cli_url or os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        print(
            "Error: no webhook URL provided. "
            "Use --webhook-url or set SLACK_WEBHOOK_URL environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    return url


def resolve_message(cli_text: str | None) -> str:
    """Return the message from --text arg or stdin."""
    if cli_text:
        return cli_text.replace("\\n", "\n").replace("\\t", "\t")

    if not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if text:
            return text

    print("Error: no message provided. Use --text or pipe via stdin.", file=sys.stderr)
    sys.exit(1)


def send_message(webhook_url: str, message: str) -> None:
    """Send a mrkdwn message to Slack via Incoming Webhook."""
    webhook = WebhookClient(url=webhook_url)
    response = webhook.send(
        text=message,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
            }
        ],
    )

    if response.status_code != 200:
        print(
            f"Error: Slack returned status {response.status_code}: {response.body}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("ok")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send Slack notification via Incoming Webhook",
    )
    parser.add_argument("--text", "-t", help="Message text (mrkdwn format)")
    parser.add_argument(
        "--webhook-url", help="Incoming Webhook URL (overrides SLACK_WEBHOOK_URL)"
    )
    args = parser.parse_args()

    webhook_url = resolve_webhook_url(args.webhook_url)
    message = resolve_message(args.text)
    send_message(webhook_url, message)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
