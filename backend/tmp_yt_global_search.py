import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_global_search.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[0]
    print("URL", page.url)

    # Open search if needed.
    inp = page.locator("input[placeholder='Search across your channel']").first
    if not (inp.count() and inp.is_visible()):
        page.locator("ytcp-icon-button[aria-label='Search'], #search-icon").first.click(timeout=5000)
        page.wait_for_timeout(600)

    for query in ("PROBE -- delete me", "Indian Law – 23 Oct 2026", "Thirukkural – 23 Oct 2026"):
        print("=== QUERY", query, "===")
        try:
            inp = page.locator("input[placeholder='Search across your channel']").first
            inp.click(timeout=3000)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            inp.fill(query)
        except Exception as exc:
            print("FILL_ERR", str(exc)[:200])
            break
        page.wait_for_timeout(2500)
        # Print visible result-ish elements.
        data = page.evaluate("""() => {
            const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            const txt = el => (el.innerText || '').trim();
            const sels = ['ytcp-search-result', 'ytcp-video-row', 'ytcp-entity-card', '[role=option]', 'ytd-video-renderer'];
            const out = {};
            for (const s of sels) {
                out[s] = [...document.querySelectorAll(s)].filter(visible).map(txt).filter(Boolean).slice(0, 12);
            }
            return { url: location.href, body: document.body.innerText.slice(0, 2500), out };
        }""")
        print(json.dumps(data, ensure_ascii=False, indent=1)[:8000])
        page.screenshot(path=str(OUT), full_page=False)
        print("SCREENSHOT", OUT)

    browser.close()
