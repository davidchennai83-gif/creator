import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "tmp_yt_verify.png"

JS = """
() => {
  const visible = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const txt = el => (el.innerText || el.getAttribute('aria-label') || '').trim();
  const hits = [...document.querySelectorAll('button, ytcp-button, [role=button], a, tp-yt-paper-dialog, ytcp-dialog, ytd-modal-with-title-and-button-renderer, yt-confirm-dialog-renderer')]
    .filter(visible)
    .map(el => ({ tag: el.tagName, text: txt(el).slice(0, 300), href: el.href || '', id: el.id || '' }))
    .filter(x => /verify|verification|confirm|identity|phone|upload|eligible|restricted|unusual|captcha|2-step|two-step/i.test(x.text + ' ' + x.href))
    .filter((v, i, arr) => arr.findIndex(y => y.text === v.text && y.tag === v.tag) === i)
    .slice(0, 30);
  const dialogs = [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog, ytd-modal-with-title-and-button-renderer, yt-confirm-dialog-renderer')]
    .filter(visible)
    .map(d => (d.innerText || '').trim().slice(0, 1200))
    .filter(Boolean);
  return {
    url: location.href,
    title: document.title,
    body: document.body.innerText.slice(0, 3000),
    hits,
    dialogs
  };
}
"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = browser.contexts[0].pages
    print("PAGES", [(i, pg.url, pg.title()) for i, pg in enumerate(pages)])
    for i, pg in enumerate(pages):
        if "youtube.com" not in pg.url:
            continue
        try:
            data = pg.evaluate(JS)
        except Exception as exc:
            print(f"--- page {i} {pg.url} ERROR {exc}")
            continue
        print(f"--- page {i} {data['url']} ---")
        print("TITLE", data["title"])
        print("BODY", data["body"].replace("\n", " | ")[:2200])
        print("HITS", json.dumps(data["hits"], ensure_ascii=False, indent=1)[:3000])
        print("DIALOGS", json.dumps(data["dialogs"], ensure_ascii=False, indent=1)[:2000])
        if any(k in (data["body"] + " ".join(data["dialogs"])).lower() for k in ("verify", "verification", "confirm it", "identity")):
            try:
                pg.screenshot(path=str(OUT), full_page=False)
                print("SCREENSHOT", OUT)
            except Exception as exc:
                print("SCREENSHOT_ERROR", exc)
    browser.close()
