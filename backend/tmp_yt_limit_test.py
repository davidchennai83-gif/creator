import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "storage" / "automation" / "projects" / "YouTube Upload"))

import content
from playwright.sync_api import sync_playwright
from uploader import CDP_URL, DailyUploadLimit, YouTubeUploader

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    for pg in list(browser.contexts[0].pages):
        try:
            if pg.locator("tp-yt-paper-dialog").filter(has_text="Daily upload limit").count():
                print("CLOSING_UPLOAD_PAGE", pg.url)
                pg.close()
        except Exception:
            pass

    videos = content.discover_videos("2026-10-23", ["health"])
    if not videos:
        print("NO_VIDEO")
        raise SystemExit(1)
    video = videos[0]
    video["_meta"] = content.build_meta(video)
    print("TEST_VIDEO", video["mp4"])
    page = browser.contexts[0].new_page()
    u = YouTubeUploader(page)
    try:
        result = u.upload(video, "public")
        print("UNEXPECTED_SUCCESS", result)
    except DailyUploadLimit as exc:
        print("EXPECTED_DAILY_LIMIT:", exc)
    except Exception as exc:
        print("OTHER_ERROR", type(exc).__name__, str(exc)[:1500])
    finally:
        try:
            page.close()
        except Exception:
            pass
    browser.close()
