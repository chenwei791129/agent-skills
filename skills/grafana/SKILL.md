---
name: grafana
description: >
  Use when operating a Grafana instance from the terminal — listing/searching
  dashboards, querying datasources, inspecting alert rules, running
  PromQL/LogQL/TraceQL over metrics/logs/traces, or pulling/pushing dashboards
  as code (GitOps). Triggers on Grafana, gcx, PromQL, LogQL, dashboard,
  alerts/告警, 查 Grafana, dashboard 管理, 監控查詢. Use this instead of a
  Grafana MCP server or raw curl/grafana-backup/grizzly. Self-hosted focused.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion
---

# Grafana (via gcx CLI)

Operate Grafana with [`gcx`](https://github.com/grafana/gcx), the official CLI:
dashboards, datasources, alerts, metrics/logs/traces. It replaces a Grafana MCP
server.

**Do NOT** use raw `curl` against the Grafana HTTP API, and **do NOT** use
`grafana-backup-tool` / `grizzly`. Those are pre-skill fallbacks. gcx gives you
structured output, pagination, error handling, and token-efficient output, and
its commands evolve with the Grafana version.

> **Environment assumption**: this skill targets **self-hosted (OSS /
> Enterprise)**. Auth uses a service account token + `org-id`. Grafana
> Cloud-only features (SLO, Synthetic Monitoring, IRM, k6) **do not apply** —
> when asked for those, say so and propose a self-hosted-viable alternative.

## 🔑 Core: discover before you act (the key to replacing MCP)

gcx has many commands and they evolve, so **never memorize or guess commands**.
Discover them with progressive disclosure to save tokens:

```bash
gcx help-tree --depth 1 -o text   # Step 1: list all top-level groups (~30 lines)
gcx help-tree <group> -o text     # Step 2: expand one group's subtree
gcx <group> <subcommand> --help   # Step 3: see exact flags and args
```

When unsure of syntax, run those three steps. Do **not** web-search grafana.com
docs, and do not guess API paths.

## Prerequisite check

```bash
gcx --version
```

If missing, download a pre-built binary from the
[GitHub releases](https://github.com/grafana/gcx/releases) (no Go toolchain
needed) — see `references/setup.md` for details:

```bash
ver=$(curl -fsSL https://api.github.com/repos/grafana/gcx/releases/latest \
  | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p')
os=$(uname -s | tr '[:upper:]' '[:lower:]')
arch=$(uname -m); [ "$arch" = "x86_64" ] && arch=amd64; [ "$arch" = "aarch64" ] && arch=arm64
curl -fsSL "https://github.com/grafana/gcx/releases/download/v${ver}/gcx_${ver}_${os}_${arch}.tar.gz" \
  | sudo tar -xz -C /usr/local/bin gcx
```

## Intent-to-group quick reference (self-hosted groups)

When you already know the user's intent, go straight to the right group and
skip discovery:

| Intent | Group | Example |
|--------|-------|---------|
| Dashboards / folders / resource CRUD | `resources` | `gcx resources get dashboards` |
| List / search dashboards | `dashboards` | `gcx dashboards list` |
| Alert rule definitions | `alert` | `gcx alert rules list` |
| **Currently firing alerts** (live state) | `alert` | `gcx alert instances list --state firing` |
| PromQL queries | `metrics` | `gcx metrics query -d <uid> 'up'` |
| LogQL queries | `logs` | `gcx logs query -d <uid> '{app="foo"}'` |
| Trace queries (Tempo) | `traces` | `gcx traces query -d <uid> '{ status = error }'` |
| Profiling (Pyroscope) | `profiles` | `gcx profiles query` |
| Datasource info / queries | `datasources` | `gcx datasources list` |
| Endpoints with no dedicated command (last resort) | `api` | `gcx api /api/v1/...` |

If no command exists for the request, say so and propose the nearest viable
flow. **Don't use `gcx api` when a dedicated command exists.**

## Verify context before acting

```bash
gcx config check            # validate the active context and test connectivity
gcx config current-context  # show the active context name
gcx config use-context <name>
gcx <any-command> --context <name>   # target one context without switching
```

First-time setup (install, self-hosted auth, multi-context, troubleshooting):
see `references/setup.md`.

## Output control

| Intent | Flag |
|--------|------|
| Structured output (for parsing) | `-o json` |
| Select fields | `--json <f1,f2>` (use `--json list` to discover fields) |
| Don't truncate the table | `--no-truncate` |
| YAML | `-o yaml` |

Default to `-o json` for programmatic work. **Prefer gcx's built-in `--json`
field selection over piping to jq/python** — gcx itself hints "no external
parsing needed". Discover fields with `--json list`, then select with
`--json a,b`.

> **Parsing pitfall**: with `-o json` the JSON goes to stdout, but a line
> `{"class":"hint",...}` goes to **stderr**. When parsing externally, do not
> use `2>&1 | jq` (it merges the hint and breaks parsing) — read stdout
> directly (use `2>/dev/null` if needed).

## Safe mutation workflow

For any write operation, follow this order (skip steps only when the user
explicitly asks for speed):

1. **Verify context** — confirm which environment you're operating on
2. **Read current state** — list / get the resource first
3. **Build payload from a template** — `gcx resources schemas <kind>` /
   `gcx resources examples <kind>`, don't hand-craft it
4. **Preview** — run `--dry-run` where available
5. **Apply** — create / update / delete
6. **Verify** — get the resource again to confirm the change landed

## Parallelism

gcx commands are stateless API calls. Issue multiple queries with **no output
dependency** as parallel Bash calls in a single message (list/get across
resources, multiple schema/example fetches, independent queries). Only
serialize when a later call needs an earlier call's output.

## Secret safety

**Never** read the config file directly (it contains a plaintext token). Use
`gcx config view` (it redacts secrets) to inspect. When passing a token to an
external tool, use a shell variable, not an inline value.

## Per-task recipes (load on demand)

- Query metrics / logs / traces (PromQL / LogQL / TraceQL) → `references/queries.md`
- Dashboards as code (pull / push / validate / GitOps) → `references/dashboards.md`
- Install and self-hosted auth setup, troubleshooting → `references/setup.md`
