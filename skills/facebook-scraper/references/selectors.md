# Facebook DOM Extraction — Selector Reference & Maintenance Notes

Researched 2026-05-30, verified live on both a group (groups/lotushill2022) and a fan page (DieWithoutBang).

FB marks content with the **`data-ad-rendering-role`** attribute, which is far more stable than its obfuscated class names. When FB changes its markup, check this file and `scripts/extract.js` first.

## `data-ad-rendering-role` values

| Value | Meaning |
|-------|---------|
| `story_message` | Post body text (the anchor for all extraction) |
| `profile_name` | A person's name (post author **or** commenter **or** feed activity actor) |
| `comment_button` | Comment button (used to locate the post container) |
| `like_button` / `share_button` | Like / share buttons |

## Final extraction architecture (important)

The implementation is **feed-centric** rather than "visit each permalink to extract", because permalink pages have anti-scraping traps (see below).

1. **The feed** provides: each post's `permalink`, `timeText`, `text`, `images`. In the feed each post container is cleanly separated.
2. **The permalink page** provides only: top-level **comments**, plus the **authoritative author** (locate the main post's `story_message` by matching the feed text prefix, then read its author).

| Target | Rule |
|--------|------|
| Post container | From `story_message`, climb to the nearest ancestor that has `profile_name` **and** an engagement button — `comment_button` OR `like_button` OR `share_button` (`_postContainer`). Do NOT require `comment_button` alone: some pages render no comment button (comments off / different layout) |
| Author | From `story_message`, walk up and check **preceding siblings** for the nearest `profile_name` (`_authorForMessage`). The post header sits immediately above the body |
| Text | The `story_message` text inside the container; click "查看更多" in the feed to expand first; then `_cleanText` strips control words ("查看更多/顯示更多/顯示較少/See more/Show less", including trailing-appended ones) |
| Time + permalink | An `<a>` in the container whose href matches `_POST_LINK_RE` (`/posts/`, `/permalink/`, `story_fbid=`, `/photo`, `/videos/`, `/watch/`, `fbid=`) and whose text is a relative time. Groups = numeric ID; pages = `pfbid...`. Photo/video posts have no `/posts/` link — use the photo permalink and keep its `fbid`(+`set`) query (`_postUrl`) |
| Images | `<img>` whose src contains `scontent` and `naturalWidth >= 200` (filters out avatars/emoji/`static.xx.fbcdn` UI icons and `data:` SVGs) |
| Top-level comments | `[role="article"]` whose aria-label contains "的留言"/"comment" and does **not** contain "回覆"/"replied". Author parsed from the aria-label prefix `^(.*?)的留言`; body is the longest `div[dir="auto"]` in the article. **Dedupe by (author + body)** (FB renders the comment list twice in the DOM) |
| Load more comments | Click "查看更多留言" / "View more comments" / "查看全部留言" |

## Anti-scraping traps (lessons learned)

1. **Feed activity-card "actor" name contaminates the author**: group feeds often surface a post as an "X commented" activity card, whose top `profile_name` is the **commenter**, not the post author. So the author is taken from "the nearest preceding `profile_name` of the `story_message`" (`_authorForMessage`); the feed may still pick the actor, so the final author is **overridden by the permalink page** (matched by text), which has no such contamination.

2. **Permalink pages have multiple `story_message`** (the main post + suggested posts, e.g. "IEObserve 台積電"). A suggested post may even carry a backlink to the main post, so **you cannot match the main post by targetId**. Instead, locate the main post's `story_message` by **matching the feed text prefix** (`extractFromPermalink`).

7. **Not every page has a `comment_button`**: some fan pages render only like/share. Requiring `comment_button` to locate the container makes those pages return zero posts — use any engagement button instead.

8. **Photo/video posts and pinned posts**: a photo-only post has no `/posts/` link (only `/photo/?fbid=…`), and pinned posts often have a **character-obfuscated timestamp** (scrambled single chars, no clean relative-time text). Such posts are still captured (text/author/image from the feed) but their time may be `(unknown)` and comments may be empty, since the photo-viewer permalink page differs from a normal post permalink.

3. **Permalink-page timestamps are character-obfuscated**: the timestamp link's innerText is often rendered as a single decorative character (e.g. `d`/`s`/`n`). So time is always taken from the **feed** (where it is clean).

4. **The feed is virtualised**: posts scrolled off-screen are removed from the DOM. So scroll **incrementally** (~0.85 viewport height per step) and collect on every step, otherwise only the few currently-rendered posts are captured.

5. **The comment list is duplicated in the DOM**: the same comment `role="article"` appears twice; dedupe is required.

6. `role="article"` is used for **both posts and comments**; do not use it to find posts — always derive a post from its `story_message`. The "精選內容" (featured) section at the top of a group is featured **comments**.

## Login

- The logged-out `https://www.facebook.com/` root page carries the classic login form: `input[name="email"]` / `input[name="pass"]` / `button[name="login"]`.
- The `/login` page's submit button uses a different selector, so log in on the **root page**; submit with `button[name="login"]`, falling back to pressing Enter in the password field.
