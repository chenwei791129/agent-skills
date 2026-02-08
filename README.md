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
| `chrome-devtools` | Launch Chrome with remote debugging for DevTools MCP integration |
