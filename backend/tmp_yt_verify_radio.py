import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "storage" / "automation" / "projects" / "YouTube Upload"))

import content
from playwright.sync_api import sync_playwright
from uploader import CDP_URL, YouTubeUploader

OUT = Path(__file__).resolve().parent / "tmp_yt_verify_radio.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    videos = content.discover_videos("2026-10-23", ["health"])
    video = videos[0]
    video["_meta"] = content.build_meta(video)
    page = browser.contexts[0].new_page()
    u = YouTubeUploader(page)
    try:
        u._open_upload()
        u._attach_file(video["mp4"])
        u._wait_for_details()
        u._fill("Title", "#title-textarea", video["_meta"]["title"])
        u._fill("Description", "#description-textarea", video["_meta"]["description"])
        u._go_to_visibility()
        u._pick_visibility("public")
        time.sleep(1)

        # Open the verification dialogs.
        page.get_by_text("Verify", exact=True).first.click(timeout=8000)
        page.wait_for_timeout(1500)
        verification_dialog = page.locator("tp-yt-paper-dialog").filter(
            has_text="One-time verification needed").first
        print("VERIFICATION_DIALOG_COUNT", page.locator("tp-yt-paper-dialog").filter(
            has_text="One-time verification needed").count())
        verification_dialog.get_by_role("button", name="Next", exact=True).click(timeout=8000)
        page.wait_for_timeout(1500)

        dialog = page.locator("tp-yt-paper-dialog").filter(has_text="Get advanced features").first
        print("ADV_DIALOG_COUNT", page.locator("tp-yt-paper-dialog").filter(has_text="Get advanced features").count())
        info = dialog.evaluate("""(d) => {
            const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            const radios = [...d.querySelectorAll('tp-yt-paper-radio-button, ytcp-radio-button, input[type=radio], tp-yt-paper-checkbox, input[type=checkbox]')]
                .map(r => ({ tag: r.tagName, name: r.getAttribute('name'), value: r.getAttribute('value'),
                             checked: r.checked, ariaChecked: r.getAttribute('aria-checked'),
                             text: (r.innerText || '').trim().slice(0, 200), disabled: r.disabled,
                             outer: r.outerHTML.slice(0, 500) }));
            const buttons = [...d.querySelectorAll('button, ytcp-button')]
                .map(b => ({ text: (b.innerText || '').trim(), disabled: b.disabled,
                             ariaDisabled: b.getAttribute('aria-disabled'),
                             outer: b.outerHTML.slice(0, 300) }));
            return { radios, buttons, text: d.innerText };
        }""")
        print(json.dumps(info, ensure_ascii=False, indent=1)[:10000])

        # Select the first option, then check Next again.
        try:
            first = dialog.locator("tp-yt-paper-radio-button, ytcp-radio-button, input[type=radio]").first
            print("FIRST_RADIO_COUNT", first.count())
            if first.count():
                first.click(force=True, timeout=5000)
                page.wait_for_timeout(800)
                print("FIRST_RADIO_CLICKED")
        except Exception as exc:
            print("FIRST_RADIO_ERR", str(exc)[:400])
            try:
                dialog.evaluate("""(d) => {
                    const r = d.querySelector('tp-yt-paper-radio-button, ytcp-radio-button, input[type=radio]');
                    if (r) r.click();
                }""")
                print("FIRST_RADIO_JS_CLICKED")
            except Exception as exc2:
                print("FIRST_RADIO_JS_ERR", str(exc2)[:300])
        page.wait_for_timeout(800)

        after = dialog.evaluate("""(d) => {
            const next = [...d.querySelectorAll('button, ytcp-button')].find(b => (b.innerText || '').trim() === 'Next');
            return { text: d.innerText, nextDisabled: next ? next.disabled : null,
                     nextAria: next ? next.getAttribute('aria-disabled') : null };
        }""")
        print("AFTER_SELECT", json.dumps(after, ensure_ascii=False, indent=1)[:5000])
        page.screenshot(path=str(OUT), full_page=False, timeout=20000)
        print("SCREENSHOT", OUT)

        # If Next is enabled, click it and capture the next verification step.
        try:
            next_btn = dialog.get_by_role("button", name="Next", exact=True).first
            if next_btn.count() and not next_btn.get_attribute("aria-disabled") == "true":
                next_btn.click(timeout=8000)
                page.wait_for_timeout(3000)
                print("NEXT2_CLICKED")
                print("PAGES", [(i, pg.url, pg.title()) for i, pg in enumerate(browser.contexts[0].pages)])
                for i, pg in enumerate(browser.contexts[0].pages):
                    if "google.com" not in pg.url and "youtube.com" not in pg.url:
                        continue
                    try:
                        txt = pg.evaluate("() => document.body.innerText.slice(0, 3000)")
                        print(f"NEXT_PAGE {i} {pg.url} BODY", txt.replace("\n", " | ")[:2500])
                        pg.screenshot(path=str(OUT.with_name(f"tmp_yt_verify_radio_next_{i}.png")),
                                      full_page=False, timeout=20000)
                    except Exception as exc:
                        print("NEXT_PAGE_ERR", i, str(exc)[:200])
            else:
                print("NEXT_STILL_DISABLED")
        except Exception as exc:
            print("NEXT2_ERR", str(exc)[:400])
    finally:
        try:
            page.close()
        except Exception:
            pass
        browser.close()
