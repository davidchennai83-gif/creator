"""Open YouTube's one-time verification dialog and leave it on screen.

This attaches one of the blocked videos, reaches the visibility step, opens the
daily-limit verification flow, selects the selfie-video option so that Next is
enabled, and then stops. It does not submit any identity information and does
not publish anything. The Chrome window is intentionally left open so the
channel owner can complete the face + ID steps.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "storage" / "automation" / "projects" / "YouTube Upload"))

import content
from playwright.sync_api import sync_playwright
from uploader import CDP_URL, YouTubeUploader

OUT = Path(__file__).resolve().parent / "tmp_yt_verify_open_for_user.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL, timeout=60000)
    videos = content.discover_videos("2026-10-23", ["health"])
    if not videos:
        raise SystemExit("No health video found")
    video = videos[0]
    video["_meta"] = content.build_meta(video)
    page = browser.contexts[0].new_page()
    page.bring_to_front()
    u = YouTubeUploader(page)

    u._open_upload()
    u._attach_file(video["mp4"])
    u._wait_for_details()
    u._fill("Title", "#title-textarea", video["_meta"]["title"])
    u._fill("Description", "#description-textarea", video["_meta"]["description"])
    u._go_to_visibility()
    u._pick_visibility("public")
    time.sleep(1)

    page.get_by_text("Verify", exact=True).first.click(timeout=10000)
    page.wait_for_timeout(1500)
    verification = page.locator("tp-yt-paper-dialog").filter(
        has_text="One-time verification needed").first
    verification.get_by_role("button", name="Next", exact=True).click(timeout=10000)
    page.wait_for_timeout(1500)

    advanced = page.locator("tp-yt-paper-dialog").filter(
        has_text="Get advanced features").first
    advanced.locator("tp-yt-paper-radio-button").first.click(force=True, timeout=8000)
    page.wait_for_timeout(800)
    next_button = advanced.get_by_role("button", name="Next", exact=True).first
    print("NEXT_ARIA_DISABLED", next_button.get_attribute("aria-disabled"))
    print("DIALOG_TEXT", advanced.inner_text()[:1200].replace("\n", " | "))
    page.screenshot(path=str(OUT), full_page=False, timeout=20000)
    print("SCREENSHOT", OUT)
    print("READY: the Chrome window has the verification dialog open.")
    print("Click Next, then record the 6-second selfie video and the government ID photo.")
    print("After approval, Cancel/discard this pending upload; the batch will upload the 8 missing videos.")
    page.bring_to_front()
    time.sleep(2)
    # Intentionally do not close the page or browser: the user needs the dialog.
