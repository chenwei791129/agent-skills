#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["patchright", "python-dotenv"]
# ///
"""Facebook group/page post scraper using patchright."""

import argparse
import base64
import os
import re
import signal
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import parsing

SKILL_DIR = Path(__file__).resolve().parent.parent
USERDATA_DIR = SKILL_DIR / ".userdata"
EXTRACT_JS = (Path(__file__).resolve().parent / "extract.js").read_text(
    encoding="utf-8"
)


# --------------------------------------------------------------------------- #
# Credentials & login
# --------------------------------------------------------------------------- #
def load_credentials() -> tuple[str | None, str | None]:
    # .env from skill dir then cwd (cwd wins via override)
    load_dotenv(SKILL_DIR / ".env")
    load_dotenv(Path.cwd() / ".env", override=True)
    return os.getenv("FB_EMAIL"), os.getenv("FB_PASSWORD")


def is_logged_in(page) -> bool:
    url = page.url
    if "login" in url or "checkpoint" in url:
        return False
    # login wall shows an email/password form
    try:
        return page.locator('input[name="pass"]').count() == 0
    except Exception:
        return True


def ensure_login(page, email: str | None, password: str | None) -> None:
    if is_logged_in(page):
        return
    if not email or not password:
        print(
            "Not logged in and FB_EMAIL/FB_PASSWORD not found. "
            "Please log in manually in the open browser, then press Enter…",
            file=sys.stderr,
        )
        input()
        return
    # The logged-out root page carries the classic login form (email/pass/login).
    page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    page.fill('input[name="email"]', email)
    page.fill('input[name="pass"]', password)
    # Submit: prefer the named button, fall back to pressing Enter.
    try:
        page.click('button[name="login"]', timeout=5000)
    except Exception:
        page.press('input[name="pass"]', "Enter")
    page.wait_for_timeout(6000)
    if not is_logged_in(page):
        print(
            "Automatic login did not complete (possibly 2FA / a security check). "
            "Please finish it in the open browser, then press Enter…",
            file=sys.stderr,
        )
        input()


# --------------------------------------------------------------------------- #
# Feed scan
# --------------------------------------------------------------------------- #
def _expand_buttons(page, labels: list[str]) -> None:
    """Click all buttons whose text matches any of labels (best-effort)."""
    for _ in range(8):
        clicked = page.evaluate(
            """(labels) => {
                let n = 0;
                const btns = document.querySelectorAll('div[role="button"],span[role="button"]');
                for (const b of btns) {
                    const t = (b.innerText || '').trim();
                    if (labels.some(l => t === l)) { b.click(); n++; }
                }
                return n;
            }""",
            labels,
        )
        if not clicked:
            break
        page.wait_for_timeout(1000)


def scan_feed(
    page,
    url: str,
    limit: int | None,
    limit_hour: int | None,
    now: datetime,
    safety_cap: int = 200,
) -> list[dict]:
    """Scroll the feed and collect full post objects honouring limit / limit_hour.

    Post content (author/time/text/images) is extracted directly from the feed,
    where each post container is cleanly separated. FB virtualises the feed, so
    we scroll incrementally and collect on every step before posts are recycled.
    Returns post dicts in the render schema (comments filled in later).
    """
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    collected: list[dict] = []
    seen: set[str] = set()
    stale_rounds = 0
    while True:
        # Expand truncated post bodies in the current DOM before collecting.
        _expand_buttons(page, ["查看更多", "See more"])
        found = page.evaluate(f"() => {{ {EXTRACT_JS}\n return collectFeedPosts(); }}")
        new_this_round = 0
        for item in found:
            permalink = item.get("permalink")
            if not permalink or permalink in seen:
                continue
            # time filter (feed is roughly chronological newest-first)
            if limit_hour is not None:
                age = parsing.parse_relative_age_hours(item.get("timeText", ""), now)
                if age is not None and age > limit_hour:
                    print(
                        f"Reached the {limit_hour}-hour limit; stopping scan.",
                        file=sys.stderr,
                    )
                    return collected
            seen.add(permalink)
            collected.append(
                {
                    "author": item.get("author", ""),
                    "time_text": item.get("timeText", ""),
                    "permalink": permalink,
                    "text": item.get("text", ""),
                    "images": [
                        {"url": u, "local_path": None, "failed": False}
                        for u in item.get("images", [])
                    ],
                    "comments": [],
                }
            )
            new_this_round += 1
            if limit is not None and len(collected) >= limit:
                return collected
            if len(collected) >= safety_cap:
                print(
                    f"Reached the safety cap of {safety_cap} posts; stopping scan.",
                    file=sys.stderr,
                )
                return collected
        print(f"  scanning… collected {len(collected)} posts", file=sys.stderr)
        if new_this_round == 0:
            stale_rounds += 1
            if stale_rounds >= 5:
                break
        else:
            stale_rounds = 0
        # Incremental scroll so posts render and get collected before recycling.
        page.evaluate("() => window.scrollBy(0, Math.round(window.innerHeight * 0.85))")
        page.wait_for_timeout(2000)
    return collected


# --------------------------------------------------------------------------- #
# Comments (from each post's permalink page)
# --------------------------------------------------------------------------- #
def fetch_author_and_comments(page, permalink: str, text_prefix: str) -> dict:
    """Visit a post's permalink; return its authoritative author + top comments.

    The permalink page has no feed activity-actor contamination, so the author
    resolved there (matched against the feed text) is more reliable than the
    feed's. Returns {"author": str, "comments": [ {author, text} ]}.
    """
    page.goto(permalink, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    _expand_buttons(page, ["查看更多留言", "View more comments", "查看全部留言"])
    page.wait_for_timeout(1000)
    return page.evaluate(
        f"(prefix) => {{ {EXTRACT_JS}\n return extractFromPermalink(prefix); }}",
        text_prefix,
    )


# --------------------------------------------------------------------------- #
# Image download (via page context to reuse session & anti-detection)
# --------------------------------------------------------------------------- #
def download_images(page, posts: list[dict], out_dir: Path) -> None:
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for i, post in enumerate(posts, 1):
        for j, img in enumerate(post["images"], 1):
            url = img["url"]
            try:
                b64 = page.evaluate(
                    """async (url) => {
                        const r = await fetch(url);
                        if (!r.ok) throw new Error('status ' + r.status);
                        const buf = await r.arrayBuffer();
                        let bin = '';
                        const bytes = new Uint8Array(buf);
                        for (let k = 0; k < bytes.length; k++) bin += String.fromCharCode(bytes[k]);
                        return btoa(bin);
                    }""",
                    url,
                )
                ext = ".jpg"
                m = re.search(r"\.(jpg|jpeg|png|webp|gif)", url, re.I)
                if m:
                    ext = "." + m.group(1).lower()
                fname = f"post{i}_img{j}{ext}"
                (images_dir / fname).write_bytes(base64.b64decode(b64))
                img["local_path"] = f"images/{fname}"
            except Exception as e:
                print(f"Image download failed {url}: {e}", file=sys.stderr)
                img["failed"] = True


# --------------------------------------------------------------------------- #
# CLI / orchestration
# --------------------------------------------------------------------------- #
def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Scrape FB group/page posts.")
    p.add_argument("--url", required=True, help="[required] group or fan page URL")
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="[optional] number of recent posts (default: 10)",
    )
    p.add_argument(
        "--limit-hour",
        type=int,
        default=None,
        dest="limit_hour",
        help="[optional] only posts within the last H hours (intersected with --limit)",
    )
    p.add_argument(
        "--out",
        default=None,
        help="[optional] output directory "
        "(default: /tmp/fb_scrape_output/<slug>_<timestamp>/)",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    limit = args.limit
    limit_hour = args.limit_hour
    if limit is None and limit_hour is None:
        limit = 10  # default when neither given

    now = datetime.now()
    slug = parsing.derive_slug(args.url)
    if args.out:
        out_dir = Path(args.out)
    else:
        ts = now.strftime("%Y%m%d-%H%M%S")
        out_dir = Path(f"/tmp/fb_scrape_output/{slug}_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    email, password = load_credentials()

    from patchright.sync_api import sync_playwright

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(USERDATA_DIR),
            channel="chrome",
            headless=False,
            no_viewport=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            ensure_login(page, email, password)

            posts = scan_feed(page, args.url, limit, limit_hour, now)
            print(f"Found {len(posts)} posts; fetching comments…", file=sys.stderr)

            for idx, post in enumerate(posts, 1):
                print(f"[{idx}/{len(posts)}] {post['permalink']}", file=sys.stderr)
                try:
                    result = fetch_author_and_comments(
                        page, post["permalink"], post["text"]
                    )
                    post["comments"] = result.get("comments", [])
                    # The permalink page resolves the author without feed
                    # activity-actor contamination; prefer it when available.
                    if result.get("author"):
                        post["author"] = result["author"]
                except Exception as e:
                    print(
                        f"Comment fetch failed {post['permalink']}: {e}",
                        file=sys.stderr,
                    )

            download_images(page, posts, out_dir)

            md = parsing.render_markdown(posts, source_url=args.url)
            (out_dir / "report.md").write_text(md, encoding="utf-8")
            print(f"Done. Report: {out_dir / 'report.md'}")
        finally:
            context.close()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
