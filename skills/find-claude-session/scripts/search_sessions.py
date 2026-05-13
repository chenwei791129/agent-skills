#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Search across all Claude Code session transcripts to find past conversations."""

import argparse
import json
import signal
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


def find_matching_files(patterns, days=None, include_subagents=False):
    """Walk all .jsonl files and return those containing all patterns (case-insensitive)."""
    matches = []
    cutoff = None
    if days is not None:
        cutoff = datetime.now().timestamp() - days * 86400

    lower_patterns = [p.lower().encode("utf-8") for p in patterns]

    for jsonl in PROJECTS_DIR.rglob("*.jsonl"):
        if not include_subagents and "/subagents/" in str(jsonl):
            continue
        try:
            stat = jsonl.stat()
        except OSError:
            continue
        if cutoff and stat.st_mtime < cutoff:
            continue
        try:
            with open(jsonl, "rb") as f:
                content = f.read().lower()
        except OSError:
            continue
        if all(pat in content for pat in lower_patterns):
            matches.append((jsonl, stat.st_mtime))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def extract_text(rec):
    """Extract text from a message record (handles both string and list content)."""
    msg = rec.get("message")
    if not msg:
        return None
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return " ".join(parts) if parts else None
    return None


def extract_cwd_and_snippet(jsonl_path, patterns):
    """Extract cwd and a snippet around the first pattern match."""
    cwd = None
    snippet = None
    first_user_text = None

    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if cwd is None and "cwd" in rec:
                    cwd = rec["cwd"]

                if snippet is None:
                    text = extract_text(rec)
                    if text:
                        if first_user_text is None and rec.get("type") == "user":
                            first_user_text = text[:120].replace("\n", " ")
                        lower_text = text.lower()
                        for pat in patterns:
                            idx = lower_text.find(pat.lower())
                            if idx >= 0:
                                start = max(0, idx - 60)
                                end = min(len(text), idx + len(pat) + 100)
                                prefix = "..." if start > 0 else ""
                                suffix = "..." if end < len(text) else ""
                                snippet = (
                                    prefix + text[start:end].replace("\n", " ") + suffix
                                )
                                break

                if cwd and snippet:
                    break
    except OSError:
        pass

    return cwd, snippet, first_user_text


def main():
    parser = argparse.ArgumentParser(
        description="Search Claude Code session transcripts across all working directories."
    )
    parser.add_argument(
        "patterns",
        nargs="+",
        help="Keywords (case-insensitive). All must appear in the session.",
    )
    parser.add_argument(
        "--days", type=int, help="Only search sessions modified within last N days"
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Max results to show (default: 20)"
    )
    parser.add_argument(
        "--dir",
        help="Filter results: cwd must contain this substring",
    )
    parser.add_argument(
        "--include-subagents",
        action="store_true",
        help="Also search subagent transcripts (off by default to reduce noise)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable",
    )
    args = parser.parse_args()

    if not PROJECTS_DIR.exists():
        print(f"No projects directory found at {PROJECTS_DIR}", file=sys.stderr)
        sys.exit(1)

    matches = find_matching_files(
        args.patterns, days=args.days, include_subagents=args.include_subagents
    )

    results = []
    for jsonl, mtime in matches:
        cwd, snippet, first_user = extract_cwd_and_snippet(jsonl, args.patterns)
        if args.dir and (not cwd or args.dir not in cwd):
            continue
        results.append(
            {
                "mtime": mtime,
                "mtime_str": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                "cwd": cwd,
                "session_file": str(jsonl),
                "snippet": snippet,
                "first_user_message": first_user,
                "is_subagent": "/subagents/" in str(jsonl),
            }
        )
        if len(results) >= args.limit:
            break

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not results:
        print(f"No sessions found matching: {' '.join(args.patterns)}", file=sys.stderr)
        sys.exit(1)

    for i, r in enumerate(results, 1):
        marker = " [subagent]" if r["is_subagent"] else ""
        print(f"[{i}] {r['mtime_str']}{marker}")
        print(f"    cwd:     {r['cwd'] or '(unknown)'}")
        print(f"    session: {r['session_file']}")
        if r["first_user_message"]:
            print(f"    opener:  {r['first_user_message']}")
        if r["snippet"]:
            print(f"    match:   {r['snippet']}")
        print()

    total = len(matches)
    if len(results) < total:
        print(
            f"Shown {len(results)}/{total} results. Increase --limit to see more.",
            file=sys.stderr,
        )
    else:
        print(f"Shown {len(results)} results.", file=sys.stderr)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
