---
name: ndc-lightscore
description: "Fetch Taiwan NDC 景氣對策信號 latest month, score, signal light, recent series, and next publish date from index.ndc.gov.tw using a uv Python script with Patchright/Chrome when Cloudflare blocks direct HTTP requests."
---

# NDC 景氣對策信號查詢

Fetch the latest Taiwan National Development Council (NDC, 國發會) business cycle monitoring indicator: latest published month, score, signal light, recent score series, and the next publish date shown on the NDC lightscore page.

The NDC site at `https://index.ndc.gov.tw/m/zh_tw/lightscore` is protected by Cloudflare. Direct `curl` or `requests` calls often return 403, so the included script runs through `uv` and Patchright, opens Chrome, loads the page once, then reads the official same-origin JSON endpoint `/n/json/lightscore`.

## Usage

Output normalized JSON:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --json
```

Output human-readable text:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --text
```

Include the most recent N rows of the score series:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --json --series-limit 12
```

Try headless mode when suitable:

```bash
uv run ~/.claude/skills/ndc-lightscore/scripts/fetch_ndc_lightscore.py --json --headless
```

If Cloudflare blocks headless mode, omit `--headless` and use the default headed Chrome mode.

## Output Fields

`--json` returns:

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
  "fetched_at": "2026-06-08T19:14:19+08:00"
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
- `next_publish_at` is the next release timestamp shown by the NDC site, not the current data month.

## Troubleshooting

- **HTTP 403 or Cloudflare block:** run without `--headless`, or open the source URL once manually in Chrome on the same machine.
- **Chrome not found:** install Google Chrome or adjust the script launch channel for your environment.
- **Do not parse the animated page score:** the page animates the displayed score; use the JSON endpoint value `line[-1].y` instead.
