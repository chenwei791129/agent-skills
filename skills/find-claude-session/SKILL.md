---
name: find-claude-session
description: "Search across all past Claude Code sessions (across every working directory) to recall what was discussed and locate the original cwd. Use this skill whenever the user wants to find a past conversation, recall which directory a session was in, search their Claude history for a topic, or asks things like '我之前在哪個對話/目錄聊過 X', '幫我找之前討論 X 的 session', 'which directory did we talk about X in', 'search my Claude transcripts for Y'. Especially useful when the user opens throwaway conversations via `cd $(mktemp -d)` and later forgets which tmp directory hosted a discussion."
---

# Find Claude Session

Search across the user's full Claude Code conversation history (`~/.claude/projects/`) by keyword, and report back which working directory (cwd) each match originated from. Useful when the user knows they discussed something with Claude before but doesn't remember when or where the conversation happened — particularly common when they spin up throwaway sessions in `mktemp -d` directories.

## How conversation storage works

Every Claude Code session is persisted as a JSONL transcript at:

```
~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl
```

`<encoded-cwd>` is the cwd at session start with `/`, `_`, `.` all replaced by `-`, which makes decoding lossy. Don't try to decode the directory name. Instead, read the `cwd` field directly from message records inside the JSONL — every user/assistant message in a Claude Code transcript carries it.

Subagent transcripts live under `<session-dir>/subagents/agent-*.jsonl` and usually duplicate the parent session's cwd. They're excluded by default to keep output clean.

## Usage

Run the search script with one or more keywords. All keywords must appear (case-insensitive) in a transcript for it to match.

```bash
uv run ~/.claude/skills/find-claude-session/scripts/search_sessions.py <keyword> [more keywords...] [options]
```

The script uses PEP 723 inline metadata (stdlib only, no external deps), so `uv run` handles execution without any project setup.

### Options

| Flag | Purpose |
|------|---------|
| `--days N` | Only sessions modified within the last N days (faster + tighter results) |
| `--limit N` | Max results to print (default 20, sorted newest first) |
| `--dir SUBSTRING` | Only show results whose cwd contains this substring |
| `--include-subagents` | Also search subagent transcripts (off by default) |
| `--json` | Emit JSON instead of human-readable output |

### Example output

```
[1] 2026-05-11 12:27
    cwd:     /private/var/folders/5r/.../T/tmp.4BKt3ITSdD
    session: /Users/.../tmp-4BKt3ITSdD/635d9ca1-....jsonl
    opener:  我的 Tabby 在最近更新到 1.0.233 後...
    match:   ...Tabby 在最近更新到 1.0.233 後，背景半透明失效了...
```

Each result shows:
- **mtime** — when the session was last written (newest first)
- **cwd** — the original working directory (read from the transcript, not decoded from the path)
- **session** — full path to the JSONL transcript
- **opener** — first user message in that session, for quick orientation
- **match** — a snippet around the first keyword hit

## Choosing keywords

The matcher is a literal AND across the supplied terms, applied to the raw transcript bytes (which include tool calls, tool results, system reminders, and so on — not just user/assistant text). To get sharper results:

- Use the most distinctive term the user mentioned (a version number, error string, library name, ticket ID) rather than a common word.
- Add a second keyword when the distinctive one alone is too noisy. For example `Tabby 1.0.233` narrows down faster than `Tabby` on its own.
- For a phrase the user typed verbatim, prefer a short unique substring of it. The matcher does not normalize whitespace, so quoting whole sentences will often miss.
- If the user only remembers a vague topic, start with `--days 30` to limit scope and avoid scanning years of history.

If the first search returns nothing, broaden — drop a keyword, drop `--days`, or try a synonym — before reporting "not found".

## Reporting back to the user

When the user's actual goal is "where was that conversation?", the cwd is the answer they care about. Lead with it. If there is a clear single best match, state the cwd directly and offer the transcript path as a follow-up. If there are several plausible candidates, list them with timestamps so the user can pick.

When the user wants the *content* of the past discussion (not just the location), the transcript path is a JSONL file you can read directly with the Read tool, or grep through for more context. Don't try to dump the whole file — extract the relevant section.

## Limitations to mention if relevant

- Older transcripts may be missing if the user has cleared `~/.claude/projects/`.
- The matcher is literal — case-insensitive but no fuzzy / stemming / synonym handling.
- A tmp directory that no longer exists on disk will still show in results (the transcript outlives the cwd). That's usually fine because the user is looking for the conversation, not the directory contents.
