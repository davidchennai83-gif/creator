import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "storage" / "automation" / "projects" / "YouTube Upload"))

import content
from playwright.sync_api import sync_playwright
from uploader import CDP_URL, YouTubeUploader

OUT = Path(__file__).resolve().parent / "tmp_yt_verify_next_screen.png"


def visible_state(page):
    return page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog], c-wiz')]
            .filter(visible).map(d => (d.innerText || '').trim()).filter(Boolean);
        const buttons = [...document.querySelectorAll('button, [role=button], a, ytcp-button')]
            .filter(visible).map(b => (b.innerText || b.getAttribute('aria-label') || '').trim())
            .filter(Boolean).slice(0, 80);
        return { url: location.href, title: document.title,
                 body: document.body.innerText.slice(0, 4000), dialogs, buttons };
    }""")


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    videos = content.discover_videos("2026-10-23", ["health"])
    video = videos[0]
    video["_meta"] = content.build_meta(video)
    page = browser.contexts[0].new_page()
    u = YouTubeUploader(page)
    try:
        u._open_upload()
        u._attach_file(video["mp4"])
        u._wait_for_details()
        u._fill("Title", "#title-textarea", video["_meta"]["title"])
        u._fill("Description", "#description-textarea", video["_meta"]["description"])
        u._go_to_visibility()
        u._pick_visibility("public")
        time.sleep(1)

        page.get_by_text("Verify", exact=True).first.click(timeout=8000)
        page.wait_for_timeout(1200)
        ver = page.locator("tp-yt-paper-dialog").filter(has_text="One-time verification needed").first
        ver.get_by_role("button", name="Next", exact=True).click(timeout=8000)
        page.wait_for_timeout(1200)

        adv = page.locator("tp-yt-paper-dialog").filter(has_text="Get advanced features").first
        adv.locator("tp-yt-paper-radio-button").first.click(force=True, timeout=5000)
        page.wait_for_timeout(500)
        adv.get_by_role("button", name="Next", exact=True).click(timeout=8000)
        page.wait_for_timeout(5000)

        print("PAGES", [(i, pg.url, pg.title()) for i, pg in enumerate(browser.contexts[0].pages)])
        for i, pg in enumerate(browser.contexts[0].pages):
            try:
                state = visible_state(pg)
            except Exception:
                continue
            if not state["body"] and not state["dialogs"]:
                continue
            print(f"--- PAGE {i} ---")
            print("URL", state["url"])
            print("TITLE", state["title"])
            print("BODY", state["body"].replace("\n", " | ")[:3000])
            print("DIALOGS", json.dumps(state["dialogs"], ensure_ascii=False, indent=1)[:3000])
            print("BUTTONS", json.dumps(state["buttons"], ensure_ascii=False, indent=1)[:2000])
            try:
                pg.screenshot(path=str(OUT.with_name(f"tmp_yt_verify_next_screen_{i}.png")),
                              full_page=False, timeout=20000)
                print("SCREENSHOT", OUT.with_name(f"tmp_yt_verify_next_screen_{i}.png"))
            except Exception as exc:
                print("SCREENSHOT_ERR", str(exc)[:200])
    finally:
        try:
            page.close()
        except Exception:
            pass
        browser.close()
