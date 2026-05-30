---
name: facebook-scraper
description: 'Scrape posts (text, images, top-level comments) from a Facebook group or fan page and output a Markdown report. Use when: the user wants to scrape, back up, or collect FB group/page post content and comments. Trigger on: facebook group, fan page, post scrape, fb group/page scraper.'
---

# Facebook Scraper

Scrape posts from a Facebook group or fan page using patchright (anti-detection Playwright): author, time, text, images, and top-level comments, rendered as a Markdown report.

## Prerequisites

1. Install Chrome for patchright (one-time):
   ```bash
   uv run --with patchright patchright install chrome
   ```
2. Provide credentials (either option):
   - Environment variables `FB_EMAIL` / `FB_PASSWORD`
   - A `.env` file in the current directory or the skill directory (copy `.env.example` and fill it in)

## Usage

```bash
uv run ~/.claude/skills/facebook-scraper/scripts/fb_scraper.py \
  --url <group-or-page-URL> [--limit N] [--limit-hour H] [--out DIR]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | required | Group or fan page URL |
| `--limit` | 10 | Number of most-recent posts |
| `--limit-hour` | none | Only posts within the last H hours (intersected with `--limit`) |
| `--out` | `/tmp/fb_scrape_output/<slug>_<timestamp>/` | Output directory |

When both `--limit` and `--limit-hour` are given they are intersected (no more than N posts AND no older than H hours; scrolling stops as soon as either bound is hit).

On first run a browser opens: if not logged in it logs in automatically with the credentials; if 2FA / a security checkpoint appears it pauses and asks you to finish it in the open browser, then press Enter. The session is saved under `.userdata/`, so later runs usually skip login.

## Output

- `report.md`: author / time / permalink / text / images / top-level comments for each post
- `images/`: downloaded images

## How it works

Two phases: first scroll the feed to collect each post's permalink (applying limit / limit-hour), then visit each permalink to fetch the full comment thread and resolve the authoritative author. Post content (author, time, text, images) is extracted from the feed, where each post container is cleanly separated. All DOM extraction logic lives in `scripts/extract.js`; selector references and maintenance notes are in `references/selectors.md` (check there first when FB changes its markup).

## Limitations (non-goals)

No posting, commenting, or liking.
