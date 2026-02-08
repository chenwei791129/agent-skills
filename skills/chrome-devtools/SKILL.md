---
name: chrome-devtools
description: Use when about to use chrome-devtools MCP tools and Chrome connection fails or remote debugging needs to be enabled. Symptoms include "Could not connect to Chrome" or "Could not find DevToolsActivePort" errors.
---

# Chrome DevTools MCP Setup

## Overview

Chrome DevTools MCP requires Chrome running with remote debugging enabled. Without this, all `mcp__chrome-devtools__*` tool calls fail.

## When to Use

- Before first use of any `mcp__chrome-devtools__*` tool
- When error: "Could not connect to Chrome" or "Could not find DevToolsActivePort"

## Setup

Run the launch script via Bash tool:

```bash
~/.claude/skills/chrome-devtools/scripts/launch-chrome-debug.sh
```

The script handles everything automatically: quits existing Chrome, launches with debug flags, waits and verifies the connection. If Chrome debug mode is already running, it skips and reuses it.

## MCP Installation

If `mcp__chrome-devtools__*` tools are not available, guide the user to install the MCP server:

```bash
claude mcp add --scope user chrome-devtools -- npx chrome-devtools-mcp@latest --autoConnect
```

The user needs to restart Claude Code after installation for the MCP tools to become available.

## Common Errors

| Error | Fix |
|-------|-----|
| "Could not connect to Chrome" | Run setup command |
| "Could not find DevToolsActivePort" | Quit Chrome first, then run setup command |
| Port 9222 already in use | Another debug Chrome is running; use it or kill it first |
