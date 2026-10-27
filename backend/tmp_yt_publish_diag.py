"""Reproduce one YouTube upload and capture the publish/verify state.

This intentionally stops at the Publish click so we can see exactly what
YouTube asks for. It does not try to bypass any verification.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "storage" / "automation" / "projects" / "YouTube Upload"))

import content
from playwright.sync_api import sync_playwright
from uploader import CDP_URL, YouTubeUploader

OUT_DIR = Path(__file__).resolve().parent
KIND = "indian-law"
DAY = "2026-10-23"


def snapshot(page, tag):
    data = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll(
            'tp-yt-paper-dialog, ytcp-dialog, yt-confirm-dialog-renderer, ' +
            'ytd-modal-with-title-and-button-renderer, [role=dialog]')]
            .filter(visible)
            .map(d => (d.innerText || '').trim())
            .filter(Boolean);
        const buttons = [...document.querySelectorAll('button, ytcp-button, [role=button], a')]
            .filter(visible)
            .map(b => (b.innerText || b.getAttribute('aria-label') || '').trim())
            .filter(Boolean)
            .slice(0, 80);
        return {
            url: location.href,
            title: document.title,
            dialogs,
            buttons,
            body: document.body.innerText.slice(0, 4000),
        };
    }""")
    print(f"\n===== {tag} =====")
    print("URL", data["url"])
    print("TITLE", data["title"])
    print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:5000])
    print("BUTTONS", json.dumps(data["buttons"], ensure_ascii=False, indent=1)[:4000])
    print("BODY", data["body"].replace("\n", " | ")[:3500])
    path = OUT_DIR / f"tmp_yt_publish_{tag}.png"
    page.screenshot(path=str(path), full_page=False)
    print("SCREENSHOT", path)
    return data


def main():
    videos = [v for v in content.discover_videos(DAY, [KIND])]
    if not videos:
        print("No video for", DAY, KIND)
        return 1
    video = videos[0]
    video["_meta"] = content.build_meta(video)
    print("VIDEO", video["mp4"])
    print("TITLE", video["_meta"]["title"])

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        page = browser.contexts[0].new_page()
        u = YouTubeUploader(page)
        try:
            u._open_upload()
            u._attach_file(video["mp4"])
            u._wait_for_details()
            u._fill("Title", "#title-textarea", video["_meta"]["title"])
            u._fill("Description", "#description-textarea", video["_meta"]["description"])
            u._fill_tags(video["_meta"].get("tags") or "")
            u._go_to_visibility()
            u._pick_visibility("public")
            snapshot(page, "before_publish")

            publish = page.locator("ytcp-button#publish-button").first
            print("PUBLISH_COUNT", publish.count(), "VISIBLE", publish.is_visible() if publish.count() else None)
            if publish.count():
                publish.click(timeout=15000)
            else:
                # Fallback to the same logic as the real uploader.
                clicked = u._click_button_named("Publish")
                print("FALLBACK_PUBLISH_CLICKED", clicked)

            # Give YouTube time to show a verification dialog or publish.
            for delay, tag in ((2, "after_publish_2s"), (8, "after_publish_10s"), (20, "after_publish_30s")):
                time.sleep(delay if tag == "after_publish_2s" else (6 if tag == "after_publish_10s" else 20))
                snapshot(page, tag)

            print("\nPAGE LEFT OPEN FOR INSPECTION (script will not close it).")
            time.sleep(2)
        except Exception as exc:
            print("DIAG_ERROR", type(exc).__name__, str(exc)[:1200])
            try:
                snapshot(page, "error_state")
            except Exception as snap_exc:
                print("SNAP_ERROR", str(snap_exc)[:300])
            raise
        finally:
            # Do not close the page here; leave it for inspection. The caller
            # can close it manually or a later script can reuse it.
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
