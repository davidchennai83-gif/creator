import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_settings_channel.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[0]
    print("URL", page.url)
    try:
        page.get_by_role("button", name="Expand menu").click(timeout=8000)
        print("EXPANDED")
    except Exception as exc:
        print("EXPAND_ERR", str(exc)[:300])
    page.wait_for_timeout(800)
    try:
        page.get_by_text("Settings", exact=True).click(timeout=8000)
        print("SETTINGS_CLICKED")
    except Exception as exc:
        print("SETTINGS_ERR", str(exc)[:400])
    page.wait_for_timeout(2000)
    data = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog]')]
            .filter(visible).map(d => (d.innerText || '').trim()).filter(Boolean);
        const tabs = [...document.querySelectorAll('tp-yt-paper-tab, [role=tab]')]
            .filter(visible).map(t => (t.innerText || '').trim()).filter(Boolean);
        return { url: location.href, dialogs, tabs };
    }""")
    print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:7000])
    print("TABS", json.dumps(data["tabs"], ensure_ascii=False, indent=1)[:2000])

    # Click the Channel settings tab if present.
    try:
        page.get_by_role("tab", name="Channel", exact=True).first.click(timeout=6000)
        print("CHANNEL_TAB_CLICKED")
        page.wait_for_timeout(1500)
    except Exception as exc:
        print("CHANNEL_TAB_ERR", str(exc)[:300])

    data2 = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog]')]
            .filter(visible).map(d => (d.innerText || '').trim()).filter(Boolean);
        const hits = [...document.querySelectorAll('button, ytcp-button, a, span, div')]
            .filter(visible).map(e => (e.innerText || '').trim()).filter(t => /advanced|verify|verification/i.test(t))
            .filter((v, i, arr) => arr.indexOf(v) === i).slice(0, 40);
        return { dialogs, hits };
    }""")
    print("AFTER_CHANNEL", json.dumps(data2, ensure_ascii=False, indent=1)[:9000])
    try:
        page.screenshot(path=str(OUT), full_page=False, timeout=20000)
        print("SCREENSHOT", OUT)
    except Exception as exc:
        print("SCREENSHOT_ERR", str(exc)[:300])
    browser.close()
