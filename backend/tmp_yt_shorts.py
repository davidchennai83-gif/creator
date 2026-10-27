import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_shorts.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[0]
    print("URL", page.url)

    tabs = page.locator("tp-yt-paper-tab, [role=tab]")
    print("TAB_COUNT", tabs.count())
    for i in range(tabs.count()):
        t = tabs.nth(i)
        try:
            print("TAB", i, repr(t.inner_text()[:60]), t.get_attribute("aria-selected"), t.is_visible())
        except Exception as exc:
            print("TAB_ERR", i, exc)

    inputs = page.locator("input")
    print("INPUT_COUNT", inputs.count())
    for i in range(min(inputs.count(), 20)):
        inp = inputs.nth(i)
        try:
            print("INPUT", i, repr(inp.get_attribute("placeholder")), repr(inp.get_attribute("aria-label")), inp.is_visible())
        except Exception:
            pass

    for sel in ("ytcp-video-row", "ytcp-video-list-cell", "ytcp-content-row", "ytcp-video-row *"):
        loc = page.locator(sel)
        print("SEL", sel, "COUNT", loc.count())

    # Click the Shorts tab.
    try:
        shorts_tab = page.get_by_role("tab", name="Shorts", exact=True)
        print("SHORTS_TAB_COUNT", shorts_tab.count())
        shorts_tab.first.click(timeout=8000)
        page.wait_for_timeout(2500)
        print("CLICKED_SHORTS")
    except Exception as exc:
        print("SHORTS_CLICK_ERR", str(exc)[:300])

    for sel in ("ytcp-video-row", "ytcp-video-list-cell", "ytcp-content-row"):
        loc = page.locator(sel)
        print("AFTER_SEL", sel, "COUNT", loc.count())
        if loc.count():
            texts = [t.strip().replace("\n", " | ") for t in loc.all_inner_texts() if t.strip()]
            print(json.dumps(texts[:40], ensure_ascii=False, indent=1)[:8000])

    # Main content text, excluding script tags.
    try:
        main_text = page.locator("ytcp-app, ytcp-content, #main, body").first.inner_text()
    except Exception:
        main_text = ""
    print("MAIN_TEXT_TAIL", main_text[-3500:].replace("\n", " | "))

    try:
        page.screenshot(path=str(OUT), full_page=False)
        print("SCREENSHOT", OUT)
    except Exception as exc:
        print("SCREENSHOT_ERR", exc)

    browser.close()
