from datetime import datetime
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import parsing

NOW = datetime(2026, 5, 30, 14, 0, 0)


def test_age_just_now():
    assert parsing.parse_relative_age_hours("剛剛", NOW) == 0.0


def test_age_minutes():
    assert parsing.parse_relative_age_hours("5 分鐘", NOW) == 5 / 60


def test_age_hours():
    assert parsing.parse_relative_age_hours("3 小時", NOW) == 3.0


def test_age_days():
    assert parsing.parse_relative_age_hours("2 天", NOW) == 48.0


def test_age_weeks():
    assert parsing.parse_relative_age_hours("2 週", NOW) == 336.0


def test_age_yesterday():
    assert parsing.parse_relative_age_hours("昨天", NOW) == 24.0


def test_age_no_space_variant():
    assert parsing.parse_relative_age_hours("5分鐘", NOW) == 5 / 60


def test_age_unparseable_returns_none():
    assert parsing.parse_relative_age_hours("???", NOW) is None


def test_slug_group():
    assert (
        parsing.derive_slug("https://www.facebook.com/groups/lotushill2022/")
        == "lotushill2022"
    )


def test_slug_group_numeric():
    assert parsing.derive_slug("https://www.facebook.com/groups/123456/") == "123456"


def test_slug_page():
    assert (
        parsing.derive_slug("https://www.facebook.com/DieWithoutBang")
        == "DieWithoutBang"
    )


def test_slug_strips_query():
    assert (
        parsing.derive_slug("https://www.facebook.com/DieWithoutBang?ref=x")
        == "DieWithoutBang"
    )


def test_slug_sanitizes():
    assert (
        parsing.derive_slug("https://www.facebook.com/some/weird path") == "weird_path"
    )


def test_comment_toplevel():
    a = "范成浩的留言2天前"
    assert parsing.parse_comment_aria(a) == {"author": "范成浩", "is_reply": False}


def test_comment_reply():
    a = "吃土鋁繩-巴逆逆回覆范成浩的留言2天前"
    r = parsing.parse_comment_aria(a)
    assert r["is_reply"] is True
    assert r["author"] == "吃土鋁繩-巴逆逆"


def test_comment_not_a_comment():
    assert parsing.parse_comment_aria("某粉專的貼文") is None


def test_comment_english_reply():
    r = parsing.parse_comment_aria("Bob replied to Alice's comment")
    assert r["is_reply"] is True


def test_render_basic():
    posts = [
        {
            "author": "水蓮山莊",
            "time_text": "2 週",
            "permalink": "https://www.facebook.com/groups/lotushill2022/posts/123/",
            "text": "社區財務難嗎？",
            "images": [
                {
                    "url": "http://x/i.jpg",
                    "local_path": "images/post1_img1.jpg",
                    "failed": False,
                }
            ],
            "comments": [{"author": "范成浩", "text": "友達妳賣了吧？"}],
        }
    ]
    md = parsing.render_markdown(
        posts, source_url="https://www.facebook.com/groups/lotushill2022/"
    )
    assert "# Facebook Scrape Report" in md
    assert "水蓮山莊" in md
    assert "社區財務難嗎？" in md
    assert "![" in md and "images/post1_img1.jpg" in md
    assert "范成浩" in md and "友達妳賣了吧？" in md
    assert "https://www.facebook.com/groups/lotushill2022/posts/123/" in md


def test_render_failed_image_marked():
    posts = [
        {
            "author": "A",
            "time_text": "1 天",
            "permalink": "u",
            "text": "t",
            "images": [{"url": "http://x/i.jpg", "local_path": None, "failed": True}],
            "comments": [],
        }
    ]
    md = parsing.render_markdown(posts, source_url="u")
    assert "Download failed" in md
    assert "http://x/i.jpg" in md


def test_render_no_comments():
    posts = [
        {
            "author": "A",
            "time_text": "1 天",
            "permalink": "u",
            "text": "t",
            "images": [],
            "comments": [],
        }
    ]
    md = parsing.render_markdown(posts, source_url="u")
    assert "(no comments)" in md
