// Animated end-card: an accent-themed outro that asks viewers to Like, Share and
// Subscribe. Renders frame-accurate stills (frame_000000.png...) into the seq
// folder named in frames.json -> outro.out, so the normal compositor can treat
// the end-card as one more scene with a crossfade into it.
//
// Fully deterministic: every position is a pure function of the frame time, so a
// re-render is byte-identical. No external images or fonts beyond Nirmala UI.
const path = require('path');
const fs = require('fs');
const root = path.resolve(__dirname, '../../..');
const { chromium } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
const folder = process.argv[2];
const config = JSON.parse(fs.readFileSync(path.join(folder, 'frames.json'), 'utf8'));
const outro = config.outro || {};
const theme = config.theme || {};
const FPS = outro.fps || 24;
const SECONDS = outro.seconds || 3.4;
const FRAMES = Math.max(1, Math.round(SECONDS * FPS));
const accent = theme.accent || '#5eead4';
const badge = outro.badge || theme.badge || '';
const channel = outro.channel || '';
const tagline = outro.tagline || 'தினமும் புது வீடியோ';
const outDir = path.join(folder, outro.out || 'seq-outro');
fs.mkdirSync(outDir, { recursive: true });

const ICON = {
  like: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10.5V21"/><path d="M7 21H4.2A1.2 1.2 0 0 1 3 19.8v-8.1a1.2 1.2 0 0 1 1.2-1.2H7"/><path d="M7 10.5l4.3-7.2a2 2 0 0 1 3.5 1.2L14.2 9h4.5a2 2 0 0 1 2 2.4l-1.3 6.7A2.4 2.4 0 0 1 17 20H7"/></svg>',
  share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="2.7"/><circle cx="6" cy="12" r="2.7"/><circle cx="18" cy="19" r="2.7"/><path d="M8.6 13.4l6.8 4M15.4 6.6l-6.8 4"/></svg>',
  bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8.5a6 6 0 1 0-12 0c0 6.5-2.6 8.5-2.6 8.5h17.2S18 15 18 8.5"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>',
};

const PAGE = `<html><head><meta charset="utf-8"><style>
  *{box-sizing:border-box;-webkit-font-smoothing:antialiased}
  body{margin:0;width:1080px;height:1920px;overflow:hidden;color:#fff;font-family:'Nirmala UI',sans-serif;
       background:radial-gradient(120% 80% at 50% 32%, __ACCENT__26 0%, #0a1424 46%, #060d18 100%)}
  .glow{position:absolute;inset:0;background:radial-gradient(46% 30% at 50% 46%, __ACCENT__3d, transparent 70%)}
  .grain{position:absolute;inset:0;opacity:.05;background-image:radial-gradient(#fff 1px,transparent 1px);background-size:26px 26px}
  .wrap{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px;padding:80px 64px}
  .brand{font-size:30px;font-weight:700;letter-spacing:.22em;color:__ACCENT__;opacity:.95}
  .head{font-size:60px;font-weight:800;text-align:center;line-height:1.25;text-shadow:0 6px 22px #000b;
        background:__ACCENT__1f;border:2px solid __ACCENT__66;border-radius:34px;padding:22px 40px}
  .row{display:flex;align-items:center;justify-content:center;gap:30px;margin-top:6px}
  .btn{display:flex;flex-direction:column;align-items:center;gap:16px;width:250px;padding:34px 18px 28px;border-radius:34px;
       background:#0e1c31e6;border:2px solid __ACCENT__55;box-shadow:0 18px 44px #0008, inset 0 0 60px #ffffff0a}
  .btn .ico{width:96px;height:96px;color:__ACCENT__}
  .btn .ico svg{width:100%;height:100%}
  .btn .lbl{font-size:34px;font-weight:700;letter-spacing:.02em}
  .btn.sub{background:linear-gradient(180deg,#ff2f4d,#cf0626);border-color:#ff8ba0;box-shadow:0 22px 54px #ff2f4d55}
  .btn.sub .ico{color:#fff;transform-origin:50% 22%}
  .halo{position:absolute;border-radius:50%;border:3px solid __ACCENT__88}
  .tag{margin-top:10px;font-size:32px;color:#cfe0f2;text-align:center;line-height:1.4}
  .chan{margin-top:2px;font-size:28px;color:__ACCENT__;letter-spacing:.04em}
</style></head><body>
  <div class="glow"></div><div class="grain"></div>
  <div class="wrap">
    <div class="brand"></div>
    <div class="head"></div>
    <div class="row">
      <div class="btn like"><div class="ico">${ICON.like}</div><div class="lbl">லைக்</div></div>
      <div class="btn share"><div class="ico">${ICON.share}</div><div class="lbl">ஷேர்</div></div>
      <div class="btn sub"><div class="ico">${ICON.bell}</div><div class="lbl">சப்ஸ்கிரைப்</div></div>
    </div>
    <div class="tag"></div>
    <div class="chan"></div>
  </div>
</body></html>`.replace(/__ACCENT__/g, accent);

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
    await page.setContent(PAGE);
    await page.evaluate(({ badge, channel, tagline }) => {
      document.querySelector('.brand').textContent = badge;
      document.querySelector('.head').textContent = 'Like · Share · Subscribe';
      document.querySelector('.tag').textContent = tagline;
      document.querySelector('.chan').textContent = channel;
      document.querySelector('.chan').style.display = channel ? 'block' : 'none';
      window.__el = {
        head: document.querySelector('.head'),
        like: document.querySelector('.like'),
        share: document.querySelector('.share'),
        sub: document.querySelector('.sub'),
        bell: document.querySelector('.sub .ico'),
        wrap: document.querySelector('.wrap'),
        tag: document.querySelector('.tag'),
      };
    }, { badge, channel, tagline });

    for (let k = 0; k < FRAMES; k++) {
      const t = k / FPS;
      await page.evaluate(({ t }) => {
        const clamp01 = (x) => Math.min(1, Math.max(0, x));
        const easeOut = (x) => 1 - Math.pow(1 - clamp01(x), 3);
        const el = window.__el;
        // Staggered pop-in with a small overshoot, then settle.
        const pop = (start, dur) => {
          const p = clamp01((t - start) / dur);
          if (p <= 0) return { on: false, s: 0 };
          const overshoot = 1 + 0.16 * Math.sin(Math.PI * p);
          return { on: true, s: easeOut(p) * overshoot };
        };
        const head = pop(0.10, 0.50);
        el.head.style.opacity = head.on ? '1' : '0';
        el.head.style.transform = `scale(${head.on ? head.s : 0.6})`;

        [['like', 0.34], ['share', 0.62], ['sub', 0.90]].forEach(([key, start]) => {
          const b = pop(start, 0.50);
          const node = el[key];
          node.style.opacity = b.on ? '1' : '0';
          node.style.transform = `scale(${b.on ? b.s : 0.5})`;
        });

        // Bell swings (damped) once the subscribe button has landed.
        const bellT = Math.max(0, t - 1.25);
        const damp = Math.exp(-bellT * 1.4);
        const swing = 20 * Math.sin(2 * Math.PI * 2.1 * bellT) * damp + 2 * Math.sin(2 * Math.PI * 1.1 * t);
        el.bell.style.transform = `rotate(${swing.toFixed(2)}deg)`;

        // Pulsing halo behind the subscribe button.
        el.sub.style.boxShadow = `0 22px 54px #ff2f4d${Math.round(40 + 40 * (0.5 + 0.5 * Math.sin(2 * Math.PI * 0.85 * t))).toString(16).padStart(2, '0')}, 0 0 0 ${Math.round(6 + 10 * (0.5 + 0.5 * Math.sin(2 * Math.PI * 0.85 * t)))}px #ff2f4d33`;

        // Gentle whole-card float + tagline fade-in.
        el.wrap.style.transform = `translateY(${(-6 * Math.sin(2 * Math.PI * 0.28 * t)).toFixed(2)}px)`;
        const tag = clamp01((t - 1.15) / 0.6);
        el.tag.style.opacity = String(tag);
        el.tag.style.transform = `translateY(${(14 * (1 - easeOut(tag))).toFixed(2)}px)`;
      }, { t });
      await page.screenshot({ path: path.join(outDir, `f-${String(k + 1).padStart(6, '0')}.png`) });
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
