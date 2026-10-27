import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_verify_options.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[1]
    print("URL", page.url)

    info = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog]')].filter(visible);
        const dialog = dialogs.find(d => /daily upload limit/i.test(d.innerText || ''));
        if (!dialog) return { found: false, dialogs: dialogs.map(d => (d.innerText||'').slice(0,300)) };
        const all = [...dialog.querySelectorAll('*')];
        const verifyEls = all.filter(el => (el.innerText || '').trim() === 'Verify')
            .map(el => ({ tag: el.tagName, id: el.id, cls: el.className, href: el.href || '', role: el.getAttribute('role'), outer: el.outerHTML.slice(0, 1200) }));
        const limitIdx = (dialog.innerText || '').indexOf('Daily upload limit');
        const html = dialog.innerHTML;
        const idx = html.indexOf('Daily upload limit');
        return { found: true, verifyEls, htmlAround: html.slice(Math.max(0, idx - 2500), idx + 2500), dialogText: dialog.innerText.slice(-1200) };
    }""")
    print(json.dumps(info, ensure_ascii=False, indent=1)[:12000])

    # Try clicking the Verify element with JS and see what happens.
    clicked = page.evaluate("""() => {
        const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog]')].filter(visible);
        const dialog = dialogs.find(d => /daily upload limit/i.test(d.innerText || ''));
        if (!dialog) return false;
        const el = [...dialog.querySelectorAll('*')].find(e => (e.innerText || '').trim() === 'Verify');
        if (!el) return false;
        el.click();
        return true;
    }""")
    print("JS_VERIFY_CLICKED", clicked)
    page.wait_for_timeout(4000)
    print("PAGES_AFTER", [(i, pg.url, pg.title()) for i, pg in enumerate(browser.contexts[0].pages)])
    for i, pg in enumerate(browser.contexts[0].pages):
        if "google.com" not in pg.url and "youtube.com" not in pg.url:
            continue
        try:
            data = pg.evaluate("""() => {
                const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog], c-wiz')]
                    .filter(visible).map(d => (d.innerText || '').trim()).filter(Boolean);
                return { url: location.href, title: document.title, body: document.body.innerText.slice(0, 3000), dialogs };
            }""")
            print(f"--- PAGE {i} {data['url']} ---")
            print("TITLE", data["title"])
            print("BODY", data["body"].replace("\n", " | ")[:2600])
            print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:3000])
            path = OUT.with_name(f"tmp_yt_verify_options_{i}.png")
            pg.screenshot(path=str(path), full_page=False)
            print("SCREENSHOT", path)
        except Exception as exc:
            print("PAGE_ERR", i, str(exc)[:300])

    browser.close()
