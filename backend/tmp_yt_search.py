import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_search.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[0]
    print("URL", page.url)

    # Go to the Videos tab.
    try:
        page.get_by_role("tab", name="Videos", exact=True).first.click(timeout=8000)
        page.wait_for_timeout(2000)
        print("CLICKED_VIDEOS")
    except Exception as exc:
        print("VIDEOS_CLICK_ERR", str(exc)[:200])

    rows = page.locator("ytcp-video-row")
    print("VIDEO_ROWS", rows.count())
    texts = [t.strip().replace("\n", " | ") for t in rows.all_inner_texts() if t.strip()]
    for t in texts[:18]:
        print("ROW", t[:600])

    # Find search controls.
    controls = page.locator("button, ytcp-icon-button, ytcp-button, input")
    print("CONTROL_COUNT", controls.count())
    for i in range(min(controls.count(), 80)):
        el = controls.nth(i)
        try:
            aria = el.get_attribute("aria-label") or ""
            ph = el.get_attribute("placeholder") or ""
            txt = (el.inner_text() or "").strip()[:40]
            if any(k in (aria + ph + txt).lower() for k in ("search", "filter")):
                print("CTRL", i, el.evaluate("e => e.tagName"), repr(aria), repr(ph), repr(txt), el.is_visible())
        except Exception:
            pass

    # Try to open search.
    opened = False
    for sel in ("ytcp-icon-button#search-icon", "#search-icon", "button[aria-label='Search']", "ytcp-button[aria-label='Search']"):
        try:
            el = page.locator(sel).first
            if el.count():
                el.click(timeout=4000)
                opened = True
                print("SEARCH_OPENED", sel)
                break
        except Exception as exc:
            print("SEARCH_OPEN_ERR", sel, str(exc)[:120])

    page.wait_for_timeout(800)
    inp = page.locator("input[placeholder='Search across your channel']").first
    print("SEARCH_INPUT_VISIBLE", inp.count(), inp.is_visible() if inp.count() else None)
    if inp.count() and inp.is_visible():
        inp.fill("Indian Law – 23 Oct 2026")
        inp.press("Enter")
        page.wait_for_timeout(3000)
        rows2 = page.locator("ytcp-video-row")
        print("SEARCH_ROWS", rows2.count())
        for t in [x.strip().replace("\n", " | ") for x in rows2.all_inner_texts() if x.strip()][:10]:
            print("SEARCH_ROW", t[:700])
        page.screenshot(path=str(OUT), full_page=False)
        print("SCREENSHOT", OUT)

    browser.close()
