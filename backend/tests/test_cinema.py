"""Tamil cinema bulletin: the shared news engine with a cinema feed mix.

The cinema project reuses ``news`` rather than copying it, so these tests check
the two things that can actually break: the general-feed filter (only film
stories may leave a newsroom feed) and the wiring of the new kind (project list,
registry, theme, upload metadata).
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

import pytest

from app.video_creator import cinema, jobs, news, registry, schedules, theme
from app.video_creator.backgrounds import ART

CONTENT = (Path(__file__).resolve().parents[1] / "storage" / "automation" / "projects"
           / "YouTube Upload" / "content.py")
spec = importlib.util.spec_from_file_location("cinema_content_under_test", CONTENT)
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)


def _rss(items):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Test</title>{''.join(items)}</channel></rss>"""


def _item(title, description="", image="", published=None, link="https://example.com/a"):
    published = published or datetime.now(timezone.utc)
    media = f'<media:content url="{image}" type="image/jpeg"/>' if image else ""
    return (f"<item><title><![CDATA[{title}]]></title>"
            f"<link>{link}</link>"
            f"<description><![CDATA[{description}]]></description>"
            f"<pubDate>{format_datetime(published)}</pubDate>{media}</item>")


GENERAL = {"name": "Daily Thanthi", "url": "https://www.dailythanthi.com/feed",
           "site": "https://www.dailythanthi.com", "keep": cinema.FILM_STORY}
DEDICATED = cinema.CINEMA_FEEDS[1]   # Sathiyam TV's cinema category
MIXED = cinema.CINEMA_FEEDS[0]       # Ananda Vikatan's cinema desk


def test_general_feed_keeps_only_film_stories():
    body = _rss([
        _item("ராமாயணம் ரூ.100 கோடி வசூல்: பாக்ஸ் ஆபிஸில் புதிய சாதனை",
              image="https://cdn.example.com/a.jpg"),
        _item("முதல்வர் புதிய நலத்திட்டத்தை தொடங்கி வைத்தார்"),
        _item("நடிகை மிருணாளினி ரவியின் திருமணப் புகைப்படங்கள்!"),
    ])
    titles = [item["title"] for item in news.parse_feed(body.encode(), GENERAL)]
    assert titles[0].startswith("ராமாயணம்")
    assert "நடிகை மிருணாளினி" in titles[1]
    assert not any("முதல்வர்" in title for title in titles)


def test_a_film_mention_in_the_body_does_not_make_a_non_film_story():
    """A general feed's copy often name-drops a film; the headline decides."""
    body = _rss([
        _item("‘TATA’-வுக்கு ரிசர்வ் வங்கி விடுத்த அதிரடி உத்தரவு",
              "இந்த படத்தில் நடிகர் ஒருவர் இதே போன்ற காட்சியில் நடித்திருந்தார். "
              "திரைப்பட விமர்சகர்கள் இதை நினைவுபடுத்துகின்றனர்."),
    ])
    assert news.parse_feed(body.encode(), GENERAL) == []


def test_a_dedicated_cinema_feed_needs_no_filter():
    body = _rss([_item("திருமணம் முடிந்து ஜோடியாக சென்னை திரும்பிய அனிருத் – காவ்யா")])
    items = news.parse_feed(body.encode(), DEDICATED)
    assert len(items) == 1
    assert items[0]["topic"] in ART


def test_the_mixed_cinema_desk_drops_its_general_trending_story():
    """cinema.vikatan.com also republishes the day's non-film trending story."""
    body = _rss([
        _item("இஸ்ரேல் அதிபராக தொடர நெதன்யாகுவின் ஐடியா; ஒத்துழைக்காத எதிர்க்கட்சி"),
        _item("விஜய் ஆண்டனி ஏன் செருப்பு அணிவதில்லை?- எமோஷனலாக விளக்கம் அளித்த மனைவி"),
    ])
    titles = [item["title"] for item in news.parse_feed(body.encode(), MIXED)]
    assert titles == ["விஜய் ஆண்டனி ஏன் செருப்பு அணிவதில்லை?- எமோஷனலாக விளக்கம் அளித்த மனைவி"]


def test_cinema_profile_ships_its_own_feeds_and_caps():
    names = [feed["name"] for feed in cinema.PROFILE.feeds]
    assert names[:2] == ["Ananda Vikatan Cinema", "Sathiyam TV Cinema"]
    assert "Daily Thanthi" in names
    # General newsrooms are read through the film filter; the cinema feeds are not.
    filtered = [feed for feed in cinema.PROFILE.feeds if feed.get("keep") is cinema.FILM_STORY]
    assert {feed["name"] for feed in filtered} >= {"Daily Thanthi", "Maalai Malar", "Hindu Tamil"}
    assert cinema.PROFILE.per_video == 10
    assert cinema.PROFILE.max_per_feed > news.NEWS_PROFILE.max_per_feed


def _stub(feed, title, image=True, published=None, topic="cinema", group="general"):
    published = published or datetime.now(timezone.utc)
    return {
        "feed": feed, "source_name": feed, "source_url": "https://example.com/x",
        "title": title, "detail": "", "image_url": f"https://cdn.example.com/{title[:4]}.jpg" if image else "",
        "published": published, "category": "", "topic": topic, "group": group, "source_id": 0,
    }


def test_selection_fills_ten_scenes_from_three_film_feeds():
    stamp = datetime.now(timezone.utc)
    words = ["வெளியீடு", "வசூல்", "டிரைலர்", "திருமணம்", "பாடல்", "காட்சி", "விருது",
             "படப்பிடிப்பு", "ஓடிடி", "ரசிகர்", "சாதனை", "கதாபாத்திரம்"]
    items = []
    for feed in ("Ananda Vikatan Cinema", "Sathiyam TV Cinema", "Daily Thanthi"):
        for index, word in enumerate(words[:4]):
            items.append(_stub(feed, f"{feed} {word} {index}",
                               published=stamp - timedelta(minutes=index),
                               group=f"group-{index}"))
    picked = news.select_items(items, cinema.PROFILE.per_video, cinema.PROFILE)
    assert len(picked) == 10
    per_feed = {}
    for item in picked:
        per_feed[item["feed"]] = per_feed.get(item["feed"], 0) + 1
    assert max(per_feed.values()) <= cinema.PROFILE.max_per_feed


def test_create_script_uses_the_cinema_feed_mix(monkeypatch):
    stamp = datetime.now(timezone.utc)
    words = ["வெளியீடு", "வசூல்", "டிரைலர்", "திருமணம்", "பாடல்", "காட்சி",
             "விருது", "படப்பிடிப்பு", "ஓடிடி", "ரசிகர்", "சாதனை", "கதாபாத்திரம்"]
    items = []
    for index, word in enumerate(words):
        items.append({
            "feed": "Ananda Vikatan Cinema", "source_name": "Ananda Vikatan Cinema",
            "source_url": f"https://cinema.vikatan.com/{(index % 3) + 1}",
            "title": f"{word} படம் {index}",
            "detail": "படத்தின் புதிய அறிவிப்பு வெளியாகியுள்ளது. ரசிகர்கள் உற்சாகமடைந்துள்ளனர்.",
            "image_url": f"https://cdn.example.com/{index}.jpg",
            "published": stamp - timedelta(minutes=index),
            "category": "", "topic": "cinema", "group": f"g{index % 4}", "source_id": index,
        })
    seen = {}

    def fake_fetch(progress, profile=None):
        seen["profile"] = profile
        return items

    monkeypatch.setattr(news, "fetch_items", fake_fetch)
    messages = []
    points = cinema.create_script(datetime.now(timezone.utc).date(), messages.append)

    assert seen["profile"] is cinema.PROFILE
    assert len(points) == 10
    assert all(point["image_url"] and point["source_name"] for point in points)
    assert all(point["topic"] in ART for point in points)
    assert all(len(point["lines"]) == 2 for point in points)
    assert any("cinema" in message.lower() for message in messages)


def test_kind_is_registered_everywhere():
    assert "cinema" in registry.KINDS
    module, attribute, _, finished = registry._CREATORS["cinema"]
    assert (module, attribute) == ("cinema", "create_script")
    assert "cinema" in finished.lower()
    assert "cinema" in {project["id"] for project in schedules.PROJECTS}
    assert theme.theme_for("cinema")["badge"].startswith("CINEMA")
    assert "cinema" in ART
    from app.video_creator.routes import Request
    assert Request(kind="cinema").kind == "cinema"
    assert jobs.new  # importing the job store keeps the kind list authoritative


def test_the_daily_hook_rotation_covers_cinema():
    """A new kind must not fall back to the generic "இன்றைய வீடியோ" opener."""
    from app.growth import playbook
    hooks = playbook.HOOKS["cinema"]
    assert len(hooks) >= 3
    assert all("சினிமா" in hook or "திரை" in hook or "கோலிவுட்" in hook for hook in hooks)
    assert playbook.variant_for("cinema", "2026-11-18")["hook"] in hooks
    assert theme.theme_for("cinema")["hook"] in hooks


def test_upload_metadata_covers_cinema_with_sources():
    assert "cinema" in content.KINDS
    job = {
        "kind": "cinema", "date": "2026-11-17", "id": "job",
        "points": [
            {"title": "ராமாயணம் ரூ.100 கோடி வசூல் சாதனை", "source_name": "Daily Thanthi",
             "source_url": "https://www.dailythanthi.com/cinema/1",
             "links": [{"title": "Daily Thanthi", "link": "https://www.dailythanthi.com/cinema/1"}]},
            {"title": "புதிய படத்தின் டிரைலர் வெளியீடு", "source_name": "Ananda Vikatan Cinema",
             "source_url": "https://cinema.vikatan.com/2",
             "links": [{"title": "Ananda Vikatan Cinema", "link": "https://cinema.vikatan.com/2"}]},
        ],
    }
    meta = content.build_meta(job)
    assert "Tamil Cinema News" in meta["title"]
    assert "10 cinema news in Tamil" in meta["title"]
    assert "#" not in meta["title"]
    assert "#TamilCinema #KollywoodNews #CinemaSeithigal" in meta["description"]
    assert "இன்றைய 10 திரைச் செய்திகள்" in meta["description"]
    assert "https://cinema.vikatan.com/2" in meta["description"]
    assert "kollywood" in meta["tags"]
    assert content.SUBSCRIBE_URL in meta["description"]
