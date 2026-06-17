# gcx install and self-hosted auth setup

## Install

Check first:

```bash
gcx --version
```

If missing, download a pre-built binary from the
[GitHub releases](https://github.com/grafana/gcx/releases) (no Go toolchain
needed). Detect the platform, resolve the latest version, and drop the binary
on PATH:

```bash
# 1. Detect OS / arch (release assets use darwin|linux and amd64|arm64)
os=$(uname -s | tr '[:upper:]' '[:lower:]')
arch=$(uname -m); [ "$arch" = "x86_64" ] && arch=amd64; [ "$arch" = "aarch64" ] && arch=arm64

# 2. Resolve the latest release version (tag is vX.Y.Z; assets drop the leading v)
ver=$(curl -fsSL https://api.github.com/repos/grafana/gcx/releases/latest \
  | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p')

# 3. Download + extract just the binary into /usr/local/bin
curl -fsSL "https://github.com/grafana/gcx/releases/download/v${ver}/gcx_${ver}_${os}_${arch}.tar.gz" \
  | sudo tar -xz -C /usr/local/bin gcx
```

Asset naming is `gcx_<version>_<os>_<arch>.tar.gz` (`darwin`/`linux`,
`amd64`/`arm64`); pin a specific `ver` instead of resolving `latest` for
reproducible installs. Windows users grab the matching `.zip` from the releases
page.

After installing, confirm the binary is on PATH: `gcx --version`.

## Configuration model

gcx uses a context model like kubectl's kubeconfig: a single YAML file
(default `~/.config/gcx/config.yaml`) holds multiple named contexts, each
pointing at one Grafana instance with its server URL, auth, and namespace. Only
one context is active at a time.

- `gcx config view` — inspect config (secrets redacted; `--raw` reveals them)
- `gcx config check` — validate the active context and health-check the server

## On-premise setup flow

### 1. Create a context

```bash
gcx config set contexts.onprem.grafana.server https://grafana.example.com
```

Replace `onprem` with an identifying environment name (`production`,
`staging`, `local`).

### 2. Set auth

**Option A: service account token (recommended)**

```bash
gcx config set contexts.onprem.grafana.token glsa_XXXXXXXXXXXXXXXX
```

Get a token at Grafana → **Administration > Service accounts**. Permissions
depend on the operation (Viewer for read-only; Editor or Admin for writes).
`grafana.token` takes precedence over user/password.

**Option B: username + password (dev only)**

```bash
gcx config set contexts.onprem.grafana.user admin
gcx config set contexts.onprem.grafana.password mysecretpassword
```

### 3. Set the org ID

Self-hosted uses an org ID to determine the namespace for API calls (default
org is 1):

```bash
gcx config set contexts.onprem.grafana.org-id 1
```

Find the org ID: **Administration > Organizations**, select an org, and read
the number in the URL.

### 4. Switch and verify

```bash
gcx config use-context onprem
gcx config check
```

### TLS (optional)

Self-signed certificate or custom CA:

```bash
# Skip TLS verification (dev only, never in production)
gcx config set contexts.onprem.grafana.tls.insecure-skip-verify true

# Provide a custom CA (base64-encoded PEM)
gcx config set contexts.onprem.grafana.tls.ca-data <base64-encoded-pem>
```

## Environment variable overrides (CI/CD)

To avoid writing a config file, override the active context's fields with env
vars (affects the current run only):

| Env var | Overrides field | Description |
|---------|-----------------|-------------|
| `GRAFANA_SERVER` | `grafana.server` | Server URL |
| `GRAFANA_TOKEN` | `grafana.token` | API token (precedes user/pass) |
| `GRAFANA_USER` | `grafana.user` | basic auth user |
| `GRAFANA_PASSWORD` | `grafana.password` | basic auth password |
| `GRAFANA_ORG_ID` | `grafana.org-id` | Org ID (self-hosted namespace) |

```bash
export GRAFANA_SERVER=https://grafana.example.com
export GRAFANA_TOKEN=glsa_XXXX
export GRAFANA_ORG_ID=1
gcx resources get dashboards -o json
```

Config file search order (high to low): `--config <path>` → `$GCX_CONFIG` →
`$XDG_CONFIG_HOME/gcx/config.yaml` → `$HOME/.config/gcx/config.yaml`.

## Default datasource (type less `-d <uid>`)

```bash
gcx datasources list -o json   # find each datasource's uid
gcx config set contexts.onprem.default-prometheus-datasource <prometheus-uid>
gcx config set contexts.onprem.default-loki-datasource <loki-uid>
```

Once set, query commands that support `-d` use the defaults automatically.

## Multi-context

```bash
gcx config set contexts.production.grafana.server https://grafana.example.com
gcx config set contexts.production.grafana.token glsa_PROD
gcx config set contexts.production.grafana.org-id 1

gcx config use-context production
gcx --context staging resources get dashboards   # target one context, no switch
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| config check fails / empty context | `gcx config view` to confirm; `gcx config set current-context <name>` |
| missing namespace | self-hosted: `gcx config set contexts.<name>.grafana.org-id 1` |
| 401 Unauthorized | token invalid/expired: reset `...grafana.token glsa_NEW` |
| 403 Forbidden | token valid but lacks permission: assign Viewer/Editor/Admin in Service accounts |
| Connection refused / timeout | check URL, VPN/proxy; `curl -I https://grafana.example.com/api/health`; for self-signed certs see the TLS section above |
