"""Tests for the (date, kind) -> YouTube URL map shared by the upload projects."""
import importlib.util
from pathlib import Path

import pytest

MODULE = (Path(__file__).resolve().parents[1]
          / "storage" / "automation" / "projects" / "_lib" / "youtube_links.py")
spec = importlib.util.spec_from_file_location("youtube_links_under_test", MODULE)
links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(links)


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(links, "STORE", tmp_path / "youtube_links.json")
    return tmp_path / "youtube_links.json"


def test_video_id_handles_every_url_shape():
    assert links.video_id("https://youtu.be/4HgiIMH6DlE") == "4HgiIMH6DlE"
    assert links.video_id("https://www.youtube.com/shorts/XrcMgzQzOV0?feature=share") == "XrcMgzQzOV0"
    assert links.video_id("https://www.youtube.com/watch?v=t3kjBrr2NfQ") == "t3kjBrr2NfQ"
    assert links.video_id("https://www.youtube.com/embed/4hLQooNMvjM") == "4hLQooNMvjM"
    assert links.video_id("https://studio.youtube.com/video/abc/video") == ""
    assert links.video_id("") == ""
    assert links.video_id(None) == ""


def test_record_and_lookup_round_trip():
    url = links.record("2026-10-26", "news",
                       "https://www.youtube.com/shorts/XrcMgzQzOV0?feature=share",
                       title="Tamil News Today")
    assert url == "https://youtu.be/XrcMgzQzOV0"
    assert links.lookup("2026-10-26", "news") == url
    assert links.has_link("2026-10-26", "news")
    assert links.lookup("2026-10-27", "news") == ""
    assert links.entry("2026-10-26", "news")["source"] == "studio"


def test_record_rejects_a_blank_url():
    assert links.record("2026-10-26", "gk", "") == ""
    assert not links.has_link("2026-10-26", "gk")


def test_pending_entry_is_not_a_link_and_never_overwrites_a_real_one():
    links.record_pending("2026-10-26", "health", "Health Tips")
    assert links.lookup("2026-10-26", "health") == ""
    assert "2026-10-26|health" in links.pending()

    links.record("2026-10-26", "health", "https://youtu.be/4jSUoXMxd8w")
    links.record_pending("2026-10-26", "health", "Health Tips")
    assert links.lookup("2026-10-26", "health") == "https://youtu.be/4jSUoXMxd8w"
    assert "2026-10-26|health" not in links.pending()


def test_decorate_caption_puts_the_link_above_the_hashtags():
    links.record("2026-10-26", "kids", "https://youtu.be/O3z2WG08FEQ")
    caption = "Kids Learning – 26 Oct 2026 – 3 easy Tamil lessons\n#KidsLearning #TamilKids"
    decorated, url = links.decorate_caption(caption, "2026-10-26", "kids")
    assert url == "https://youtu.be/O3z2WG08FEQ"
    lines = decorated.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("Kids Learning")
    assert "https://youtu.be/O3z2WG08FEQ" in lines[1]
    assert lines[2].startswith("#KidsLearning")


def test_decorate_caption_without_hashtags_appends_the_link():
    links.record("2026-10-26", "kids", "https://youtu.be/O3z2WG08FEQ")
    decorated, _ = links.decorate_caption("one line only", "2026-10-26", "kids")
    assert decorated.splitlines()[-1].endswith("https://youtu.be/O3z2WG08FEQ")


def test_decorate_caption_without_a_link_keeps_the_caption_untouched():
    caption = "Day of History – 26 Oct 2026\n#TamilHistory"
    decorated, url = links.decorate_caption(caption, "2026-10-26", "history")
    assert decorated == caption
    assert url == ""


def test_find_in_feed_matches_exactly_then_by_long_prefix():
    feed = [("4HgiIMH6DlE", "Day of History – 26 Oct 2026 – 10 historical events in Tamil")]
    assert links.find_in_feed(
        "Day of History – 26 Oct 2026 – 10 historical events in Tamil", feed) == "4HgiIMH6DlE"
    # Titles are capped at 100 chars in Studio, so the feed can trim the tail.
    assert links.find_in_feed(
        "Day of History – 26 Oct 2026 – 10 historical events in Tamil #TamilHistory #DailyHistory",
        feed) == "4HgiIMH6DlE"
    assert links.find_in_feed("Some other video", feed) == ""


def test_sync_pending_resolves_and_keeps_the_unmatched(monkeypatch):
    links.record_pending("2026-10-26", "history", "Day of History – 26 Oct 2026")
    links.record_pending("2026-10-26", "news", "Tamil News Today – 26 Oct 2026")

    feed = [("4HgiIMH6DlE", "Day of History – 26 Oct 2026")]
    monkeypatch.setattr(links, "fetch_feed", lambda timeout=20: feed)

    assert links.sync_pending(attempts=1, delay=0, verbose=False) == 1
    assert links.lookup("2026-10-26", "history") == "https://youtu.be/4HgiIMH6DlE"
    assert links.lookup("2026-10-26", "news") == ""
    assert "2026-10-26|news" in links.pending()
