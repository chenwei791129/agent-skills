#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///

"""
Query Taiwan stock financial reports via FinMind API.

Environment variables:
  FINMIND_TOKEN - API token for higher rate limits (optional)

Usage:
  uv run finmind_query.py income -s 2330 --start 2024-01-01
  uv run finmind_query.py balance-sheet -s 2330 --start 2023-01-01 --format json
  uv run finmind_query.py revenue -s 2317 --start 2024-01-01 --limit 12
  uv run finmind_query.py datasets
  uv run finmind_query.py translate --dataset TaiwanStockFinancialStatements
"""

import argparse
import json
import os
import signal
import sys
from datetime import date

import requests

API_BASE = "https://api.finmindtrade.com/api/v4"

DATASETS = {
    "income": ("TaiwanStockFinancialStatements", "Comprehensive Income Statement"),
    "balance-sheet": ("TaiwanStockBalanceSheet", "Balance Sheet"),
    "cash-flow": ("TaiwanStockCashFlowsStatement", "Cash Flow Statement"),
    "revenue": ("TaiwanStockMonthRevenue", "Monthly Revenue"),
    "dividend": ("TaiwanStockDividend", "Dividend Policy"),
    "per": ("TaiwanStockPER", "PER / PBR / Dividend Yield"),
    "price": ("TaiwanStockPrice", "Daily Stock Price"),
}


def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


def _api_get(endpoint, params=None, token=""):
    """Send GET request to FinMind API with unified error handling."""
    if params is None:
        params = {}
    if token:
        params["token"] = token

    try:
        resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
    except requests.exceptions.Timeout:
        print("Error: request timed out after 30 seconds.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Error: unable to connect to FinMind API.", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 402:
        print(
            "Error: rate limit exceeded. "
            "Set FINMIND_TOKEN env var or use --token for higher limits (600 req/hr).",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"Error: FinMind API returned HTTP {resp.status_code}.", file=sys.stderr)
        sys.exit(1)

    return resp.json()


def format_table(data, stock_id, dataset):
    """Format data as a markdown table."""
    if not data:
        return f"No data found for stock {stock_id} in dataset {dataset}."

    keys = list(data[0].keys())
    lines = []
    lines.append("| " + " | ".join(keys) + " |")
    lines.append("| " + " | ".join("---" for _ in keys) + " |")
    for row in data:
        values = [str(row.get(k, "")).replace("|", "\\|") for k in keys]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    lines.append(f"*{len(data)} rows from {dataset} for stock {stock_id}*")
    return "\n".join(lines)


def format_json(data, stock_id, dataset):
    """Format data as JSON output."""
    return json.dumps(
        {
            "dataset": dataset,
            "stock_id": stock_id,
            "count": len(data),
            "data": data,
        },
        ensure_ascii=False,
        indent=2,
    )


def cmd_query(args):
    """Generic query handler for all financial datasets."""
    dataset_name = DATASETS[args.command][0]
    token = args.token or os.environ.get("FINMIND_TOKEN", "")
    end = args.end or date.today().isoformat()

    result = _api_get(
        "data",
        params={
            "dataset": dataset_name,
            "data_id": args.stock,
            "start_date": args.start,
            "end_date": end,
        },
        token=token,
    )

    if result.get("status") != 200:
        print(f"Error: {result.get('msg', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    data = result.get("data", [])
    if args.limit:
        data = data[: args.limit]

    if args.format == "json":
        print(format_json(data, args.stock, dataset_name))
    else:
        print(format_table(data, args.stock, dataset_name))


def cmd_datasets(args):
    """List available datasets."""
    token = args.token or os.environ.get("FINMIND_TOKEN", "")
    result = _api_get("datalist", token=token)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        datasets = result.get("data", result)
        if isinstance(datasets, dict):
            for category, items in datasets.items():
                print(f"\n## {category}\n")
                if isinstance(items, list):
                    for item in items:
                        print(f"- {item}")
                else:
                    print(f"- {items}")
        elif isinstance(datasets, list):
            for item in datasets:
                print(f"- {item}")
        else:
            print(json.dumps(datasets, ensure_ascii=False, indent=2))


def cmd_translate(args):
    """Translate dataset field names."""
    token = args.token or os.environ.get("FINMIND_TOKEN", "")
    result = _api_get("translation", params={"dataset": args.dataset}, token=token)
    data = result.get("data", result)

    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if isinstance(data, dict):
            print(f"## Field translations for {args.dataset}\n")
            print("| English | Chinese |")
            print("| --- | --- |")
            for en, zh in data.items():
                print(f"| {en} | {zh} |")
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser():
    """Build argument parser with subcommands."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--token", help="API token (overrides FINMIND_TOKEN env var)")
    common.add_argument(
        "--format",
        "-f",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )

    parser = argparse.ArgumentParser(
        description="Query Taiwan stock financial reports via FinMind API."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for cmd, (_, desc) in DATASETS.items():
        sub = subparsers.add_parser(cmd, parents=[common], help=desc)
        sub.add_argument("--stock", "-s", required=True, help="Stock ID (e.g. 2330)")
        sub.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
        sub.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
        sub.add_argument(
            "--limit", "-l", type=int, help="Limit number of rows returned"
        )

    subparsers.add_parser(
        "datasets", parents=[common], help="List all available datasets"
    )

    tr = subparsers.add_parser(
        "translate", parents=[common], help="Translate dataset field names"
    )
    tr.add_argument(
        "--dataset",
        required=True,
        help="Dataset name to translate (e.g. TaiwanStockFinancialStatements)",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "datasets":
        cmd_datasets(args)
    elif args.command == "translate":
        cmd_translate(args)
    else:
        cmd_query(args)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
