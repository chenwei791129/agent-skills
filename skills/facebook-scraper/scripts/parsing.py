"""Pure parsing/rendering helpers for the Facebook scraper.

No third-party dependencies so it can be unit-tested without a browser.
"""

import re
from datetime import datetime
from urllib.parse import urlparse

_REL_PATTERNS = [
    (re.compile(r"剛剛|just now", re.I), lambda m: 0.0),
    (re.compile(r"(\d+)\s*分鐘"), lambda m: int(m.group(1)) / 60),
    (re.compile(r"(\d+)\s*小時"), lambda m: float(int(m.group(1)))),
    (re.compile(r"(\d+)\s*天"), lambda m: int(m.group(1)) * 24.0),
    (re.compile(r"(\d+)\s*週"), lambda m: int(m.group(1)) * 168.0),
    (re.compile(r"昨天|yesterday", re.I), lambda m: 24.0),
    (re.compile(r"(\d+)\s*(?:hr|hour)s?", re.I), lambda m: float(int(m.group(1)))),
    (re.compile(r"(\d+)\s*(?:min)s?", re.I), lambda m: int(m.group(1)) / 60),
    (re.compile(r"(\d+)\s*(?:day)s?", re.I), lambda m: int(m.group(1)) * 24.0),
]


def parse_relative_age_hours(text: str, now: datetime) -> float | None:
    """Approximate post age in hours from a relative-time string.

    Returns None when the string cannot be parsed (caller should keep the post
    and rely on --limit instead of filtering it out).
    """
    if not text:
        return None
    text = text.strip()
    for pattern, fn in _REL_PATTERNS:
        m = pattern.search(text)
        if m:
            return fn(m)
    return None


def derive_slug(url: str) -> str:
    """Derive a filesystem-safe slug from a group/page URL."""
    path = urlparse(url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "facebook"
    if parts[0] == "groups" and len(parts) >= 2:
        raw = parts[1]
    else:
        raw = parts[-1]
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_") or "facebook"


def parse_comment_aria(aria: str) -> dict | None:
    """Parse a comment article's aria-label.

    Returns {"author": str, "is_reply": bool} or None when the aria-label is
    not a comment. Replies are detected via 回覆 / "replied".
    """
    if not aria:
        return None
    is_comment = ("的留言" in aria) or re.search(r"comment", aria, re.I)
    if not is_comment:
        return None
    is_reply = ("回覆" in aria) or bool(re.search(r"replied", aria, re.I))
    # Chinese: 「<author>的留言...」 or 「<author>回覆<target>的留言...」
    m = re.match(r"^(.*?)(?:回覆.*?)?的留言", aria)
    if m and m.group(1):
        author = m.group(1)
    else:
        # English: "Bob's comment" / "Bob replied to Alice's comment"
        m2 = re.match(r"^(.*?)(?:'s comment| replied to)", aria, re.I)
        author = m2.group(1).strip() if m2 else ""
    return {"author": author, "is_reply": is_reply}


def render_markdown(posts: list[dict], source_url: str) -> str:
    lines = [
        "# Facebook Scrape Report",
        "",
        f"- Source: {source_url}",
        f"- Posts: {len(posts)}",
        "",
        "---",
        "",
    ]
    for i, p in enumerate(posts, 1):
        lines.append(f"## Post {i}: {p.get('author') or '(unknown author)'}")
        lines.append("")
        lines.append(f"- Time: {p.get('time_text') or '(unknown)'}")
        lines.append(f"- Permalink: {p.get('permalink') or '(none)'}")
        lines.append("")
        lines.append(p.get("text") or "(no text)")
        lines.append("")
        images = p.get("images") or []
        if images:
            lines.append("### Images")
            lines.append("")
            for j, img in enumerate(images, 1):
                if img.get("failed") or not img.get("local_path"):
                    lines.append(f"- Download failed: {img.get('url')}")
                else:
                    lines.append(f"![post{i}-img{j}]({img['local_path']})")
            lines.append("")
        comments = p.get("comments") or []
        lines.append("### Top-level comments")
        lines.append("")
        if not comments:
            lines.append("(no comments)")
        else:
            for c in comments:
                author = c.get("author") or "(anonymous)"
                text = (c.get("text") or "").replace("\n", " ")
                lines.append(f"- **{author}**：{text}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)
