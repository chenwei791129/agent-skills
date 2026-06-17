# Dashboard management and as-code (GitOps)

Use the `gcx resources` group for CRUD on Grafana's K8s-tier resources
(dashboards, folders, etc.). **Do NOT** use `grafana-backup-tool` or `grizzly`
— `gcx resources pull/push` is exactly the version-control path.

When unsure of a subcommand, run `gcx resources --help` first.

## resources verbs

| Verb | Purpose |
|------|---------|
| `get` | list or fetch resources |
| `pull` | export resources to local files (for git) |
| `push` | create / update from local files |
| `delete` | remove |
| `validate` | validate local files against the live instance |
| `schemas` | discover resource types and their schema |
| `examples` | get an example manifest for a resource type |

Selector examples: `gcx resources get dashboards`,
`gcx resources get dashboards/my-dash`, `gcx resources get dashboards folders`.

## List / inspect

```bash
gcx dashboards list -o json          # list / search dashboards
gcx resources get dashboards -o json
gcx resources get folders -o json
```

## Pull to code (version control)

```bash
# Export resources to a local directory (YAML)
gcx resources pull dashboards -p ./grafana -o yaml

# Or pull all resources
gcx resources pull -p ./grafana
```

Then put `./grafana` under git so the repo becomes the single source of truth.

## Push / apply changes

Follow the safe mutation workflow: read current state → use `examples` as a
template → preview with `--dry-run` → apply → verify.

```bash
# Get an example manifest as a template (don't hand-craft the payload)
gcx resources examples Dashboard
gcx resources examples Folder

# Preview (changes nothing)
gcx resources push -p ./grafana --dry-run

# Apply
gcx resources push -p ./grafana

# Verify it landed
gcx resources get dashboards -o json
```

## Drift detection (for CI)

Detect differences between the repo and live Grafana with a dry-run push:

```bash
gcx resources validate -p ./grafana   # validate local files against live
gcx resources push -p ./grafana --dry-run
```

Put that line in CI (a GitHub Actions step or Makefile target) with env-var
auth (see setup.md's `GRAFANA_SERVER` / `GRAFANA_TOKEN` / `GRAFANA_ORG_ID`) to
auto-detect repo/live drift on PRs.

## Useful flags

| Intent | Flag |
|--------|------|
| Preview without changing anything | `--dry-run` |
| Target a context | `--context <name>` |
| Continue vs abort on error | `--on-error fail\|ignore\|abort` |
| Control concurrency | `--max-concurrent <n>` (default 10) |
