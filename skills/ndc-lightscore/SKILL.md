---
name: ndc-lightscore
description: 'Fetch Taiwan NDC 景氣對策信號 latest month, score, signal light, recent series, full historical score series, consecutive red-light runs, and next publish date from index.ndc.gov.tw using a uv Python script with Patchright/Chrome when Cloudflare blocks direct HTTP requests.'
---

# NDC 景氣對策信號查詢

Fetch Taiwan National Development Council (NDC, 國發會) business cycle monitoring indicators: latest published month, score, signal light, recent series, full historical score series, consecutive red-light runs, and the next publish date shown on the NDC lightscore page.

The NDC site is protected by Cloudflare. Direct `curl` or `requests` calls often return 403, so the included script runs through `uv` and Patchright, opens Chrome, loads the relevant NDC page once, then reads official same-origin JSON endpoints from the browser context.

## Usage

Output the latest normalized JSON and recent 12-month series:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --json
```

Output latest data in human-readable text:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --text
```

Include the most recent N rows of the short lightscore series:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --json --series-limit 12
```

Fetch the full historical monthly score series from the NDC indicators endpoint:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --history --json --series-limit -1
```

Find historical consecutive red-light runs. This answers questions like "哪些年份景氣燈號超過連五紅，分別連多少紅":

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --red-runs --min-red-length 5 --text
```

Machine-readable red-run output:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --red-runs --min-red-length 5 --json
```

Try headless mode when suitable:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --json --headless
```

If Cloudflare blocks headless mode, omit `--headless` and use the default headed Chrome mode.

## Output Fields

Default `--json` returns:

```json
{
  "source_url": "https://index.ndc.gov.tw/m/zh_tw/lightscore",
  "api_url": "https://index.ndc.gov.tw/n/json/lightscore",
  "latest": {
    "month": "2026-04",
    "roc_month_label": "115年4月",
    "score": 39,
    "signal": "紅燈"
  },
  "next_publish_at": "2026-06-26 16:00",
  "series": [
    {
      "month": "2026-04",
      "roc_month_label": "115年4月",
      "score": 39,
      "signal": "紅燈"
    }
  ],
  "series_count": 12,
  "fetched_at": "2026-06-08T19:14:19+08:00"
}
```

`--history --series-limit -1 --json` uses `https://index.ndc.gov.tw/n/zh_tw/data/eco/indicators_table1` and `/n/json/data/eco/indicators`, extracts score code `SR0005`, and returns a full non-null monthly `series` plus `series_count`.

`--red-runs --json` adds:

```json
{
  "history_range": {"start_month": "1984-01", "end_month": "2026-04"},
  "red_run_min_length": 5,
  "red_runs": [
    {
      "signal": "紅燈",
      "start_month": "2021-02",
      "end_month": "2021-10",
      "months": 9,
      "years": [2021],
      "scores": [38, 39],
      "min_score": 38,
      "max_score": 41
    }
  ]
}
```

## Signal Mapping

The script maps scores to NDC monitoring lights:

| Score range | Signal |
|-------------|--------|
| `<= 16` | 藍燈 |
| `17–22` | 黃藍燈 |
| `23–31` | 綠燈 |
| `32–37` | 黃紅燈 |
| `>= 38` | 紅燈 |

## Notes

- The script uses PEP 723 inline dependencies, so `uv run` installs `patchright` automatically when needed.
- It uses local Chrome via `p.chromium.launch(channel="chrome")`.
- The latest data month comes from the final `line` entry in `/n/json/lightscore`.
- `next_publish_at` is the next release timestamp shown by the NDC lightscore page, not the current data month.
- The short `/n/json/lightscore` endpoint only returns the chart window. Use `--history` or `--red-runs` for all historical monthly score rows.
- `--series-limit -1` means all available non-null rows; `--series-limit 0` omits the `series` rows while keeping summary fields.

## Troubleshooting

- **HTTP 403 or Cloudflare block:** run without `--headless`, or open the source URL once manually in Chrome on the same machine.
- **Chrome not found:** install Google Chrome or adjust the script launch channel for your environment.
- **Do not parse the animated page score:** the page animates the displayed score; use the JSON endpoint value `line[-1].y` for latest data.
- **Need historical runs:** use `--red-runs`; do not try to increase the default endpoint's chart window with `--series-limit` alone.
