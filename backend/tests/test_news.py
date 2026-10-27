"""The daily Tamil news bulletin: RSS parsing, selection and upload metadata."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

import pytest

from app.video_creator import news

CONTENT = (Path(__file__).resolve().parents[1] / "storage" / "automation" / "projects"
           / "YouTube Upload" / "content.py")
spec = importlib.util.spec_from_file_location("news_content_under_test", CONTENT)
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)


def _rss(items, extra_ns=""):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/" {extra_ns}>
<channel><title>Test</title>{''.join(items)}</channel></rss>"""


def _item(title, description="", image="", published=None, link="https://example.com/a"):
    published = published or datetime.now(timezone.utc)
    media = f'<media:content url="{image}" type="image/jpeg"/>' if image else ""
    return (f"<item><title><![CDATA[{title}]]></title>"
            f"<link>{link}</link>"
            f"<description><![CDATA[{description}]]></description>"
            f"<pubDate>{format_datetime(published)}</pubDate>{media}</item>")


FEED = {"name": "Test News", "url": "https://example.com/feed", "site": "https://example.com"}


def test_parse_feed_keeps_tamil_story_and_lead_image():
    body = _rss([_item(
        "சென்னையில் புதிய மெட்ரோ ரயில் சேவை தொடக்கம்",
        "<p>சென்னையில் புதிய மெட்ரோ ரயில் சேவை இன்று தொடங்கியது.</p><img src='https://cdn.example.com/a.jpg'>",
        image="https://cdn.example.com/lead.jpg",
    )])
    items = news.parse_feed(body.encode(), FEED)
    assert len(items) == 1
    item = items[0]
    assert item["title"].startswith("சென்னையில்")
    assert item["image_url"] == "https://cdn.example.com/lead.jpg"
    assert "<p>" not in item["detail"]
    assert item["source_name"] == "Test News"
    assert item["source_url"] == "https://example.com/a"
    assert item["topic"] in news.ART


def test_parse_feed_skips_horoscope_english_and_stale_items():
    old = datetime.now(timezone.utc) - timedelta(days=5)
    body = _rss([
        _item("இன்றைய ராசிபலன்: அக்டோபர் 27, 2026 ராசி பலன்"),
        _item("English headline about something unrelated"),
        _item("பழைய செய்தி இன்னும் பட்டியலில் உள்ளது", published=old),
        _item("மழை காரணமாக பள்ளிகளுக்கு விடுமுறை அறிவிப்பு"),
    ])
    items = news.parse_feed(body.encode(), FEED)
    assert [item["title"] for item in items] == ["மழை காரணமாக பள்ளிகளுக்கு விடுமுறை அறிவிப்பு"]


def test_parse_feed_upgrades_the_bbc_thumbnail():
    feed = {"name": "BBC Tamil", "url": "https://feeds.bbci.co.uk/tamil/rss.xml",
            "site": "https://www.bbc.com/tamil"}
    body = _rss([_item(
        "புயல் காரணமாக கடலோர மாவட்டங்களில் கனமழை எச்சரிக்கை",
        image="https://ichef.bbci.co.uk/ace/ws/240/cpsprodpb/a.jpg",
    )])
    items = news.parse_feed(body.encode(), feed)
    assert items[0]["image_url"] == "https://ichef.bbci.co.uk/ace/ws/1024/cpsprodpb/a.jpg"


def _stub(feed, title, image=True, published=None, topic="news", group="general"):
    published = published or datetime.now(timezone.utc)
    return {
        "feed": feed, "source_name": feed, "source_url": "https://example.com/x",
        "title": title, "detail": "", "image_url": f"https://cdn.example.com/{title[:4]}.jpg" if image else "",
        "published": published, "category": "", "topic": topic, "group": group, "source_id": 0,
    }


def test_select_items_balances_sources_and_drops_the_same_story():
    stamp = datetime.now(timezone.utc)
    words = ["மழை", "பள்ளி", "ரயில்", "விவசாயம்", "மருத்துவம்", "வங்கி", "தேர்தல்",
             "காவல்", "விண்வெளி", "கடல்", "மலை", "ஆறு", "பூங்கா", "சாலை",
             "விளையாட்டு", "சினிமா", "வரி", "மின்சாரம்", "காடு", "கட்டிடம்"]
    items = []
    index = 0
    for feed in ("BBC Tamil", "Daily Thanthi", "Hindu Tamil", "Polimer News", "Maalai Malar"):
        for i in range(4):
            items.append(_stub(feed, f"{feed} {words[index]}",
                               published=stamp - timedelta(minutes=index), topic=str(index % 5),
                               group=f"group-{index}"))
            index += 1
    items.append(_stub("Sathiyam TV", "படம் இல்லாத செய்தி ஒன்று உள்ளது", image=False))

    picked = news.select_items(items)
    assert len(picked) == 10
    assert all(item["image_url"] for item in picked)
    per_feed = {}
    for item in picked:
        per_feed[item["feed"]] = per_feed.get(item["feed"], 0) + 1
    assert max(per_feed.values()) <= news.MAX_PER_FEED
    assert "Sathiyam TV" not in per_feed
    titles = [item["title"] for item in picked]
    assert len(titles) == len(set(titles))


def test_near_duplicate_catches_the_same_story_reworded():
    assert news._near_duplicate("அன்பில் மகேஷ் கைது வழக்கு விவரம்",
                                ["அன்பில் மகேஷ் கைது வழக்கு பின்னணி"])
    assert not news._near_duplicate("சென்னையில் மழை எச்சரிக்கை",
                                    ["டெல்லியில் புதிய மெட்ரோ சேவை"])


def test_fallback_lines_remove_dateline_quotes_and_stray_spaces():
    lines = news._fallback_lines(
        "டெல்டா மாவட்டங்களில் மழைநீரில் மூழ்கிய நெற்பயிர்",
        'சென்னை : "வடகிழக்கு பருவமழை காரணமாக டெல்டா மாவட்டங்களில் பலத்த மழை பெய்து வருகிறது. '
        'இதில் 6,000 ஏக்கர் நெல் வயல்கள் மழைநீரில் மூழ்கியுள்ளன." ',
        "Hindu Tamil")
    assert len(lines) == 2
    assert all(len(line) <= 240 for line in lines)
    assert all("சென்னை :" not in line for line in lines)
    assert all("  " not in line for line in lines)
    assert all(line[-1] in ".!?…" for line in lines)


def test_upload_metadata_covers_news_with_sources():
    assert "news" in content.KINDS
    assert "cartoon" not in content.KINDS
    job = {
        "kind": "news", "date": "2026-10-27", "id": "job",
        "points": [
            {"title": "செய்தி ஒன்று இங்கே உள்ளது", "source_name": "BBC Tamil",
             "source_url": "https://www.bbc.com/tamil/articles/1",
             "links": [{"title": "BBC Tamil", "link": "https://www.bbc.com/tamil/articles/1"}]},
            {"title": "செய்தி இரண்டு இங்கே உள்ளது", "source_name": "Hindu Tamil",
             "source_url": "https://www.hindutamil.in/news/2",
             "links": [{"title": "Hindu Tamil", "link": "https://www.hindutamil.in/news/2"}]},
        ],
    }
    meta = content.build_meta(job)
    assert "Tamil News Today" in meta["title"]
    assert "#TamilNews" in meta["title"]
    assert "இன்றைய 10 முக்கிய செய்திகள்" in meta["description"]
    assert "https://www.bbc.com/tamil/articles/1" in meta["description"]
    assert "tamilnews" in meta["tags"]
