# Querying metrics / logs / traces

Rule of thumb: when unsure of a command or flag, run `gcx <group> --help`
first (`metrics` / `logs` / `traces` / `profiles` / `datasources`). Default to
`-o json` for easy parsing.

## Find the datasource

Many queries need a datasource uid (`-d <uid>`). List them first:

```bash
gcx datasources list -o json   # see each one's uid / name / type
```

If a default datasource is configured (see setup.md), you can omit `-d`.

## Metrics (PromQL)

```bash
# Instant query
gcx metrics query -d <prometheus-uid> 'rate(http_requests_total[5m])'

# With a time range
gcx metrics query -d <prometheus-uid> 'rate(http_requests_total[5m])' --since 1h

# Discover what metrics / labels exist (do this before guessing the schema)
gcx metrics labels -d <prometheus-uid>
gcx metrics query -d <prometheus-uid> 'count by (__name__)({__name__=~".+"})'
```

Prefer `gcx metrics query` over `gcx datasources query <prometheus-uid>` — the
signal-specific command resolves the datasource automatically.

Error-rate example (confirm real metric / label names with `gcx metrics labels`
first, then substitute):

```bash
gcx metrics query -d <uid> \
  'sum(rate(http_requests_total{service="checkout",status=~"5.."}[1h]))
   / sum(rate(http_requests_total{service="checkout"}[1h]))'
```

## Logs (LogQL)

```bash
gcx logs query -d <loki-uid> '{app="checkout"} |= "error"' --since 1h

# Discover available labels / values
gcx logs labels -d <loki-uid>
```

## Traces (Tempo)

When the output is for an agent to read / summarize / debug, prefer Tempo's
LLM-friendly encoding (`--llm`) to save tokens:

```bash
# Discover attribute names first
gcx traces labels -d <tempo-uid>

# Search for traces (get trace ids)
gcx traces query -d <tempo-uid> '{ status = error }'

# Attribute values (grouped by type)
gcx traces tags -d <tempo-uid> -l resource.service.name --llm -o json

# Fetch a full trace body
gcx traces get -d <tempo-uid> <trace-id> --llm -o json
```

Omit `--llm` only when the user explicitly needs raw Tempo/OTLP JSON or the
standard `tagValues:[{type,value}]` shape.

## Extracting a query from an existing dashboard panel (important)

To "reproduce a number shown on a dashboard", **read the panel's real query —
don't invent one**:

```bash
# 1. Find the dashboard: the selector id is metadata.name, the title is spec.title
gcx dashboards list --json metadata.name,spec.title

# 2. Read the panel queries (dig into panels[].targets[].expr and datasource)
gcx resources get dashboards/<metadata.name> -o json
```

**Key pitfall: panel PromQL/LogQL contains Grafana macros and template
variables that raw `gcx metrics query` does NOT expand** — substitute them with
concrete values before running:

| As written in the dashboard | Substitute before running gcx |
|-----------------------------|-------------------------------|
| `$__rate_interval` / `$__interval` | a fixed window, e.g. `[5m]` |
| `$__range` | an explicit range, or use `--since 1h` |
| `$var` / `${var}` / `[[var]]` (template vars) | concrete value (e.g. `service="checkout"`) |

This substitution rule is **Grafana-general, not instance-specific**: these
`$...` tokens are interpolated by Grafana at panel render time, but `gcx
metrics query` sends PromQL straight to the datasource, which receives them
literally and errors. The macro names are Grafana built-ins; only *which value*
to substitute depends on the dashboard/environment.

Example: a panel has `rate(ifHCInOctets{ifName="$iface"}[$__rate_interval])*8`,
so actually run:

```bash
gcx metrics query -d <prom-uid> 'rate(ifHCInOctets{ifName="eth0"}[5m])*8'
```

When a dashboard has "one panel per entity" (e.g. one chart per link), the
panels' exprs differ only by label value; run them one by one, or merge into a
single multi-series instant query with `label_replace` to compare them.

## Profiles (Pyroscope)

```bash
gcx profiles query -d <pyroscope-uid> --help   # discover flags, then query
```

## Parallelism

Run independent queries across different datasources as multiple parallel Bash
calls in a single message.
