import json

from playwright.sync_api import sync_playwright

JS = """
() => {
  const rows = [...document.querySelectorAll('ytcp-video-row, ytcp-video-list-cell, ytcp-content-row')]
    .map(r => (r.innerText || '').trim())
    .filter(Boolean);
  const tabs = [...document.querySelectorAll('tp-yt-paper-tab, [role=tab]')]
    .map(t => ({ text: (t.innerText || '').trim(), selected: t.getAttribute('aria-selected') || t.hasAttribute('selected') }))
    .filter(t => t.text);
  const leaf = [...document.querySelectorAll('*')]
    .filter(e => e.children.length === 0)
    .map(e => (e.textContent || '').trim())
    .filter(t => /verify|verification|private|draft|unlisted|restricted|limited/i.test(t));
  const body = document.body.innerText;
  return { rows, tabs, leaf: [...new Set(leaf)].slice(0, 40), bodyTail: body.slice(Math.max(0, body.length - 5000)) };
}
"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = browser.contexts[0].pages[0]
    print("URL", pg.url)
    print(json.dumps(pg.evaluate(JS), ensure_ascii=False, indent=1)[:12000])
    browser.close()
