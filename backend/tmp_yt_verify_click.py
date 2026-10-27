import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_verify_click.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    print("PAGES", [(i, pg.url, pg.title()) for i, pg in enumerate(browser.contexts[0].pages)])
    # Pick the page whose visible dialog mentions the daily limit.
    target = None
    for pg in browser.contexts[0].pages:
        try:
            txt = pg.locator("tp-yt-paper-dialog, ytcp-dialog, [role=dialog]").first.inner_text(timeout=2000)
        except Exception:
            continue
        if "daily upload limit" in txt.lower():
            target = pg
            print("TARGET", pg.url)
            break
    if target is None:
        target = browser.contexts[0].pages[-1]
        print("TARGET_FALLBACK", target.url)

    # Click the Verify button in the upload dialog.
    print("VERIFY_BUTTONS", target.get_by_role("button", name="Verify", exact=True).count())
    try:
        target.get_by_role("button", name="Verify", exact=True).first.click(timeout=8000)
        print("VERIFY_CLICKED")
    except Exception as exc:
        print("VERIFY_CLICK_ERR", str(exc)[:500])

    target.wait_for_timeout(4000)
    print("PAGES_AFTER", [(i, pg.url, pg.title()) for i, pg in enumerate(browser.contexts[0].pages)])
    for i, pg in enumerate(browser.contexts[0].pages):
        if "google.com" not in pg.url and "youtube.com" not in pg.url:
            continue
        try:
            data = pg.evaluate("""() => {
                const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, [role=dialog], c-wiz')]
                    .filter(visible).map(d => (d.innerText || '').trim()).filter(Boolean);
                return { url: location.href, title: document.title, body: document.body.innerText.slice(0, 2500), dialogs };
            }""")
            print(f"--- PAGE {i} {data['url']} ---")
            print("TITLE", data["title"])
            print("BODY", data["body"].replace("\n", " | ")[:2200])
            print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:2500])
            path = OUT.with_name(f"tmp_yt_verify_click_{i}.png")
            pg.screenshot(path=str(path), full_page=False)
            print("SCREENSHOT", path)
        except Exception as exc:
            print("PAGE_ERR", i, str(exc)[:300])

    browser.close()
