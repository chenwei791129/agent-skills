---
name: hermes-plugin-operations
description: "Install, reinstall, migrate, and verify Hermes Agent plugins, especially third-party standalone plugins under ~/.hermes/plugins."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [hermes, plugins, installation, troubleshooting, migration]
    related_skills: [hermes-agent]
---

# Hermes Plugin Operations

Use this skill when a user asks to install, reinstall, remove, migrate, enable, disable, or troubleshoot a Hermes plugin. This is a class-level companion to the protected `hermes-agent` skill, focused on practical plugin lifecycle work.

## Workflow

1. **Load `hermes-agent` first when available.** Use it for the current CLI surface and safety notes. Treat live docs/README from the target plugin repo as authoritative for plugin-specific install steps.
2. **Inspect current state before changing anything.**
   - `hermes plugins list --plain --no-bundled`
   - Check `$HERMES_HOME/plugins` (default `~/.hermes/plugins`) for old files/directories matching the plugin's old and new names.
   - Check `$HERMES_HOME/config.yaml` for `plugins.enabled` and stale `plugins.disabled` entries.
3. **For reinstall/migration, remove old artifacts deliberately.**
   - If an old plugin was a single file, remove both the `.py` file and matching `__pycache__` bytecode.
   - If an old plugin was a directory, remove the whole old plugin directory.
   - Remove the old plugin name from `plugins.enabled`; preserve unrelated enabled plugins.
4. **Follow the plugin's current installer or README exactly.** For standalone third-party plugins, Hermes expects a directory containing `plugin.yaml` under `$HERMES_HOME/plugins/<plugin-name>/`, then the plugin name in `plugins.enabled`.
5. **Verify installation, not just copy files.**
   - `hermes plugins list --plain --no-bundled` should show the new plugin as `enabled` and the old name absent.
   - Confirm `plugin.yaml` exists in the installed directory.
   - If the plugin includes a quick-check script, run it in the documented context.
6. **Restart the running Hermes process/gateway.** From inside a gateway session, do not run `hermes gateway restart` as a child process; Hermes blocks this because the gateway would kill its own command. Ask the user to send `/restart` or run `hermes gateway restart` from an external shell.

## Pitfalls and patterns

### Python dependency context

Do not treat `python3 script.py` failures for missing packages as proof the plugin is broken. Quick-check scripts may assume `uv run`, Hermes' environment, or a repo-local `pyproject.toml`. Prefer the command shown in the plugin README, often something like:

```bash
uv run plugin/providers/codex_usage.py
```

If you run a script from an installed plugin directory rather than the source repo, relative/package imports may differ. Re-run from a temporary clone when the README's quick-check expects repo layout.

### Hermes auth layout compatibility

When a plugin reads Hermes OAuth credentials from `$HERMES_HOME/auth.json`, inspect the credential shape without printing token values. Hermes installs may store provider credentials under either:

- `providers.<provider-name>`
- `credential_pool.<provider-name>` as a prioritized list

If a plugin only supports one layout, patch the installed plugin or upstream source to normalize both layouts, then verify by calling the provider endpoint with tokens redacted from logs.

### Configuration editing

Prefer Hermes CLI commands for enable/disable when they work:

```bash
hermes plugins enable <name>
hermes plugins disable <name>
```

If editing `config.yaml` programmatically, preserve unrelated plugin entries and do not require optional modules like PyYAML unless the active Python environment has them. A line-based removal of one exact stale `- old-plugin-name` entry is acceptable for a narrow cleanup.

## Verification checklist

- [ ] Old plugin files/directories removed.
- [ ] Old plugin name removed from `plugins.enabled`.
- [ ] New plugin directory exists and contains `plugin.yaml`.
- [ ] `hermes plugins list --plain --no-bundled` reports the new plugin as `enabled`.
- [ ] Any provider/API quick check was run in the documented environment.
- [ ] User was told whether a gateway restart is still required.
