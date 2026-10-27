import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_settings.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].new_page()
    page.goto("https://studio.youtube.com/channel/UCbvF3kubhzam4EqbnOa4QbQ/settings/channel",
              wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(5000)
    print("URL", page.url)
    print("TITLE", page.title())
    data = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const tabs = [...document.querySelectorAll('tp-yt-paper-tab, [role=tab], a')]
            .filter(visible).map(t => ({ text: (t.innerText || '').trim().slice(0, 80), href: t.href || '' }))
            .filter(x => x.text).slice(0, 80);
        const body = document.body.innerText;
        return { body: body.slice(0, 5000), tabs };
    }""")
    print("BODY", data["body"].replace("\n", " | ")[:4500])
    print("TABS", json.dumps(data["tabs"], ensure_ascii=False, indent=1)[:4000])
    page.screenshot(path=str(OUT), full_page=False, timeout=20000)
    print("SCREENSHOT", OUT)
    page.close()
    browser.close()
