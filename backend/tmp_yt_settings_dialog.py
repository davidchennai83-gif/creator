import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_settings_dialog.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[0]
    print("URL", page.url)
    try:
        page.get_by_text("Settings", exact=True).first.click(timeout=8000)
        print("SETTINGS_CLICKED")
    except Exception as exc:
        print("SETTINGS_CLICK_ERR", str(exc)[:400])
    page.wait_for_timeout(2500)
    data = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog]')]
            .filter(visible).map(d => (d.innerText || '').trim()).filter(Boolean);
        const tabs = [...document.querySelectorAll('tp-yt-paper-tab, [role=tab], a, button, ytcp-button')]
            .filter(visible).map(t => ({ tag: t.tagName, text: (t.innerText || '').trim().slice(0, 80),
                                        href: t.href || '', id: t.id || '' }))
            .filter(x => x.text).slice(0, 120);
        return { url: location.href, dialogs, tabs };
    }""")
    print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:6000])
    print("TABS", json.dumps(data["tabs"], ensure_ascii=False, indent=1)[:5000])
    page.screenshot(path=str(OUT), full_page=False, timeout=20000)
    print("SCREENSHOT", OUT)
    browser.close()
