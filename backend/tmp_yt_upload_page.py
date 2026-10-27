import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_upload_page.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].new_page()
    page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(7000)
    print("URL", page.url)
    print("TITLE", page.title())
    data = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, ytd-modal-with-title-and-button-renderer, yt-confirm-dialog-renderer, [role=dialog]')]
            .filter(visible).map(d => (d.innerText || '').trim()).filter(Boolean);
        const buttons = [...document.querySelectorAll('button, ytcp-button, [role=button], a')]
            .filter(visible).map(b => (b.innerText || b.getAttribute('aria-label') || '').trim()).filter(Boolean)
            .filter(t => /verify|verification|confirm|identity|phone|continue|upload|sign in|not now|next|cancel|save|publish/i.test(t))
            .slice(0, 40);
        return { body: document.body.innerText.slice(0, 3500), dialogs, buttons };
    }""")
    print("BODY", data["body"].replace("\n", " | ")[:3000])
    print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:2500])
    print("BUTTONS", json.dumps(data["buttons"], ensure_ascii=False, indent=1)[:2500])
    page.screenshot(path=str(OUT), full_page=False)
    print("SCREENSHOT", OUT)
    page.close()
    browser.close()
