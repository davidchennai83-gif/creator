import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_videos_tab.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[0]
    print("URL", page.url)

    links = page.evaluate("""() => [...document.querySelectorAll('a')]
        .map(a => ({ text: (a.innerText || '').trim().slice(0, 50), href: a.href }))
        .filter(x => x.href.includes('/videos') || x.href.includes('/content'))
        .filter((v, i, arr) => arr.findIndex(y => y.href === v.href) === i)
        .slice(0, 30)""")
    print("LINKS", json.dumps(links, ensure_ascii=False, indent=1))

    # Open search and search for the missing video.
    try:
        search_btn = page.locator("ytcp-icon-button[aria-label='Search'], #search-icon").first
        if search_btn.count():
            search_btn.click(timeout=5000)
            print("SEARCH_BTN_CLICKED")
    except Exception as exc:
        print("SEARCH_BTN_ERR", str(exc)[:200])
    page.wait_for_timeout(800)
    inp = page.locator("input[placeholder='Search across your channel']").first
    print("INPUT_VISIBLE", inp.count(), inp.is_visible() if inp.count() else None)
    if inp.count() and inp.is_visible():
        inp.fill("Indian Law – 23 Oct 2026")
        inp.press("Enter")
        page.wait_for_timeout(3000)
        rows = page.locator("ytcp-video-row")
        print("SEARCH_ROWS", rows.count())
        for t in [x.strip().replace("\n", " | ") for x in rows.all_inner_texts() if x.strip()][:10]:
            print("SEARCH_ROW", t[:900])
        page.screenshot(path=str(OUT), full_page=False)
        print("SCREENSHOT", OUT)

    # Navigate directly to the Videos tab if the link exists.
    video_link = next((x["href"] for x in links if x["text"].strip() == "Videos"), None)
    print("VIDEO_LINK", video_link)
    if video_link and video_link != page.url:
        page.goto(video_link, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(3500)
        rows = page.locator("ytcp-video-row")
        print("VIDEOS_TAB_ROWS", rows.count())
        for t in [x.strip().replace("\n", " | ") for x in rows.all_inner_texts() if x.strip()][:20]:
            print("VIDEOS_TAB_ROW", t[:900])
        page.screenshot(path=str(OUT), full_page=False)
        print("SCREENSHOT2", OUT)

    browser.close()
