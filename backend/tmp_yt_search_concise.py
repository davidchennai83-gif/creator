import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_search_concise.png"

QUERIES = [
    "Day of History – 23 Oct 2026",
    "Indian Law – 23 Oct 2026",
    "Thirukkural – 23 Oct 2026",
    "Spoken English – 23 Oct 2026",
    "General Knowledge – 23 Oct 2026",
    "Health Tips – 23 Oct 2026",
    "Motivation – 23 Oct 2026",
    "Kids Learning – 23 Oct 2026",
    "Cartoon Story – 23 Oct 2026",
]

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[0]
    print("URL", page.url)

    inp = page.locator("input[placeholder='Search across your channel']").first
    if not (inp.count() and inp.is_visible()):
        page.locator("ytcp-icon-button[aria-label='Search'], #search-icon").first.click(timeout=5000)
        page.wait_for_timeout(600)

    for query in QUERIES:
        print("=== QUERY", query, "===")
        inp = page.locator("input[placeholder='Search across your channel']").first
        inp.click(timeout=3000)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        inp.fill(query)
        page.wait_for_timeout(2200)
        data = page.evaluate("""() => {
            const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            const body = document.body.innerText;
            const header = (body.match(/Videos \\(\\d+\\)/) || [''])[0];
            const rows = [...document.querySelectorAll('ytcp-video-row')]
                .filter(visible).map(r => (r.innerText || '').trim().replace(/\\n/g, ' | ')).filter(Boolean);
            const resultCards = [...document.querySelectorAll('ytcp-search-result, ytcp-entity-card, [role=option]')]
                .filter(visible).map(r => (r.innerText || '').trim().replace(/\\n/g, ' | ')).filter(Boolean);
            return { header, rows: rows.slice(0, 4), resultCards: resultCards.slice(0, 6), bodyHead: body.slice(0, 700).replace(/\\n/g, ' | ') };
        }""")
        print("HEADER:", data["header"])
        print("ROWS:", json.dumps(data["rows"], ensure_ascii=False)[:1800])
        print("CARDS:", json.dumps(data["resultCards"], ensure_ascii=False)[:900])
        print("BODY_HEAD:", data["bodyHead"][:500])
        page.screenshot(path=str(OUT), full_page=False)

    browser.close()
