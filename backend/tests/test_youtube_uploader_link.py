"""The uploader reads the new video's id from Studio's address bar after publish."""
import importlib.util
import sys
from pathlib import Path

MODULE = (Path(__file__).resolve().parents[1]
          / "storage" / "automation" / "projects" / "YouTube Upload" / "uploader.py")
sys.path.insert(0, str(MODULE.parent))
spec = importlib.util.spec_from_file_location("yt_uploader_under_test", MODULE)
uploader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uploader)


class FakePage:
    def __init__(self, url):
        self.url = url


def link_for(url):
    return uploader.YouTubeUploader(FakePage(url))._page_video_url()


def test_studio_edit_url_yields_the_video_link():
    assert link_for("https://studio.youtube.com/video/cfKLZwpWLUM/edit") == \
        "https://youtu.be/cfKLZwpWLUM"
    assert link_for("https://studio.youtube.com/video/cfKLZwpWLUM/video") == \
        "https://youtu.be/cfKLZwpWLUM"


def test_public_urls_are_kept_working():
    assert link_for("https://www.youtube.com/shorts/cfKLZwpWLUM") == \
        "https://youtu.be/cfKLZwpWLUM"
    assert link_for("https://youtu.be/cfKLZwpWLUM") == "https://youtu.be/cfKLZwpWLUM"


def test_upload_page_without_a_video_id_returns_nothing():
    assert link_for("https://studio.youtube.com/channel/UCbvF3kubhzam4EqbnOa4QbQ/videos/upload") == ""
    assert link_for("about:blank") == ""
