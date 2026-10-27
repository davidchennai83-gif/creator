import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_verify_next.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].pages[1]
    print("URL", page.url)
    dialog = page.locator("tp-yt-paper-dialog").filter(has_text="One-time verification needed").first
    print("DIALOG_COUNT", page.locator("tp-yt-paper-dialog").filter(has_text="One-time verification needed").count())
    try:
        dialog.get_by_role("button", name="Next", exact=True).click(timeout=8000)
        print("NEXT_CLICKED")
    except Exception as exc:
        print("NEXT_ERR", str(exc)[:600])
        # Fallback: JS click the Next button inside the verification dialog.
        clicked = page.evaluate("""() => {
            const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog')].filter(visible);
            const d = dialogs.find(x => /One-time verification needed/.test(x.innerText || ''));
            if (!d) return false;
            const btn = [...d.querySelectorAll('button, ytcp-button')].find(b => (b.innerText || '').trim() === 'Next');
            if (!btn) return false;
            btn.click();
            return true;
        }""")
        print("NEXT_JS_CLICKED", clicked)

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
                const buttons = [...document.querySelectorAll('button, [role=button], a')]
                    .filter(visible).map(b => (b.innerText || b.getAttribute('aria-label') || '').trim()).filter(Boolean).slice(0, 60);
                return { url: location.href, title: document.title, body: document.body.innerText.slice(0, 3000), dialogs, buttons };
            }""")
            print(f"--- PAGE {i} {data['url']} ---")
            print("TITLE", data["title"])
            print("BODY", data["body"].replace("\n", " | ")[:2600])
            print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:3500])
            print("BUTTONS", json.dumps(data["buttons"], ensure_ascii=False, indent=1)[:2000])
            path = OUT.with_name(f"tmp_yt_verify_next_{i}.png")
            try:
                pg.screenshot(path=str(path), full_page=False, timeout=20000)
                print("SCREENSHOT", path)
            except Exception as exc:
                print("SCREENSHOT_ERR", str(exc)[:200])
        except Exception as exc:
            print("PAGE_ERR", i, str(exc)[:300])

    browser.close()
