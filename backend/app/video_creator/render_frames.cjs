// Chromium's text shaping preserves Tamil vowel signs and ligatures on Windows.
// Renders TWO layers for every scene:
//   scene-N.png   full-bleed background only
//   overlay-N.png transparent text layer
// The motion engine animates scene-N.png, then render.py composites overlay-N.png
// on top. Keeping the words out of the moving image means the Ken Burns camera
// never zooms, pans or clips the text. The background photo also stays visible:
// there is no opaque card and no per-line background behind the words.
const path = require('path');
const fs = require('fs');
const root = path.resolve(__dirname, '../../..');
const { chromium } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
const folder = process.argv[2];
const conf = JSON.parse(fs.readFileSync(path.join(folder, 'frames.json'), 'utf8'));
const { points, day, kind = 'history', backgrounds = [], theme = {} } = conf;
const accent = theme.accent || '#5eead4';
const badge = theme.badge || 'DAILY VIDEO';

const PAGE = `<html><head><meta charset="utf-8"><style>
  *{box-sizing:border-box;-webkit-font-smoothing:antialiased}
  html,body{margin:0;width:1080px;height:1920px;overflow:hidden}
  body{background:#0b1526;color:#fff;font-family:'Nirmala UI',sans-serif}
  #background{position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover;filter:saturate(1.04) contrast(1.02)}
  /* Soft top/bottom scrim: the photo stays clear in the middle, the lower text
     stays readable, and there is no card or box around the words. */
  .shade{position:absolute;inset:0;background:linear-gradient(180deg,
        rgba(4,10,20,.62) 0%,rgba(4,10,20,.20) 16%,rgba(4,10,20,0) 34%,
        rgba(4,10,20,0) 46%,rgba(4,10,20,.40) 64%,rgba(4,10,20,.78) 84%,rgba(4,10,20,.90) 100%)}
  .glow{position:absolute;inset:0;opacity:.28;background:radial-gradient(58% 38% at 50% 12%,__ACCENT__44,transparent 72%)}
  .grain{position:absolute;inset:0;opacity:.045;background-image:radial-gradient(#fff 1px,transparent 1px);background-size:26px 26px}
  /* 4:5-safe text area: Facebook crops a 1080x1920 upload to the centre 1080x1350.
     Keeping everything inside 60px sides and 300px top/bottom means the words are
     never cut off in the feed. */
  article{position:absolute;left:60px;right:60px;top:300px;bottom:320px;display:flex;flex-direction:column;
          justify-content:flex-end;gap:14px;padding:0 8px;color:#fff}
  .top{position:absolute;top:0;left:0;right:0;display:flex;align-items:center;justify-content:space-between;gap:16px}
  .badge{display:inline-flex;align-items:center;gap:10px;font-size:24px;font-weight:800;letter-spacing:.05em;
         color:__ACCENT__;background:none;border:0;border-radius:0;padding:0;
         text-shadow:0 2px 10px rgba(0,0,0,.88)}
  .step{font-size:22px;font-weight:700;color:__ACCENT__;border:0;border-radius:0;
        padding:0;background:none;text-shadow:0 2px 10px rgba(0,0,0,.88)}
  #product{position:absolute;top:76px;left:50%;transform:translateX(-50%);display:none;height:360px;
           width:min(86%,430px);border-radius:24px;background:#f8fafc;overflow:hidden;
           border:2px solid __ACCENT__aa;box-shadow:0 16px 38px #00000066}
  #product img{width:100%;height:100%;object-fit:contain}
  body.product #product{display:flex;align-items:center;justify-content:center}
  /* Keep the catalogue photo visible behind the text instead of a black wall. */
  body.product #background{filter:blur(18px) brightness(.58) saturate(1.05);transform:scale(1.06)}
  h1{color:#ffe6b0;font-size:54px;line-height:1.18;margin:0;font-weight:800;letter-spacing:0;
     text-shadow:0 3px 14px rgba(0,0,0,.72);text-wrap:balance}
  .rule{height:6px;width:150px;border-radius:999px;background:linear-gradient(90deg,__ACCENT__,__ACCENT__00);margin:2px 0}
  main{font-size:34px;line-height:1.48;margin:0;display:flex;flex-direction:column;gap:13px;
       color:#f7fbff;font-weight:500}
  main p{margin:0;padding:0;background:none;border:0;box-shadow:none;
         text-shadow:0 2px 10px rgba(0,0,0,.78);overflow-wrap:anywhere;word-break:break-word;hyphens:auto}
  footer{font-size:18px;color:#d7e3f4;margin-top:2px;line-height:1.4;opacity:.86;
         text-shadow:0 2px 8px rgba(0,0,0,.8);overflow-wrap:anywhere}
  body.photo footer{background:none;padding:0;border-radius:0;font-size:17px}
  /* Screenshot modes: background only, then a transparent text overlay. */
  body.capture-bg article{display:none}
  body.capture-overlay{background:transparent!important}
  body.capture-overlay #background,body.capture-overlay .shade,body.capture-overlay .glow,
  body.capture-overlay .grain{display:none}
</style></head><body>
  <img id="background"/><div class="shade"></div><div class="glow"></div><div class="grain"></div>
  <article>
    <div class="top"><span class="badge"></span><span class="step"></span></div>
    <div id="product"><img id="productImage" alt=""/></div>
    <h1></h1><div class="rule"></div>
    <main lang="ta"></main><footer></footer>
  </article>
</body></html>`.replace(/__ACCENT__/g, accent);

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
    await page.setContent(PAGE);

    for (let i = 0; i < points.length; i++) {
      const point = points[i];
      await page.evaluate(async ({ point, day, i, kind, count, background, badge }) => {
        const image = document.querySelector('#background');
        if (background) { image.src = background.image; try { await image.decode(); } catch (e) {} }
        else { image.removeAttribute('src'); }

        const law = kind === 'indian-law';
        const money = kind === 'make-money';
        const compact = law || money;
        const photo = background?.provider === 'pexels' || background?.provider === 'feed';
        const product = kind === 'meesho' && background?.provider === 'product';
        document.body.classList.toggle('photo', photo);
        document.body.classList.toggle('product', product);

        const productImage = document.querySelector('#productImage');
        if (product && background?.image) {
          productImage.src = background.image;
          try { await productImage.decode(); } catch (e) {}
        } else {
          productImage.removeAttribute('src');
        }

        document.querySelector('.badge').textContent = badge;
        document.querySelector('.step').textContent = `${i + 1} / ${count}`;

        const title = document.querySelector('h1');
        title.textContent = compact ? (point.title_display || point.title) : (point.year || point.title || '');
        let titleSize = product ? 42 : law ? 38 : money ? 46 : kind === 'meesho' ? 50 : kind === 'news' ? 48 : 54;
        title.style.fontSize = `${titleSize}px`;

        const demoProduct = kind === 'meesho' && (
          point.demo === true || /meesho\.com\/search|[?&]q=/i.test(point.affiliate_url || '')
        );
        let footer = law
          ? 'Indian central Acts · Educational overview · Sources: India Code'
          : money ? 'Educational ideas · Results vary · Not financial advice'
          : kind === 'meesho'
            ? `Tamil Budget Finds · ${demoProduct ? 'Demo product · Search link' : 'Affiliate link'} · Price may change`
          : kind === 'news'
            ? `செய்தி ஆதாரம்: ${point.source_name || 'RSS'} · ${point.published || day}`
          : kind === 'history' ? 'Wikipedia via History API · AI Tamil narration'
          : `${badge} · ${day}`;
        if (product) footer += demoProduct ? ' | Illustrative product image' : ' | Product image';
        else if (background?.provider === 'feed') footer += ' | Feed image';
        else if (photo) footer += ` | Illustrative photo: ${background.photographer} / Pexels`;
        else if (background) footer += ` | Illustration: ${background.topic}`;
        document.querySelector('footer').textContent = footer;

        const main = document.querySelector('main');
        main.replaceChildren(...((point.lines_display || point.lines || []).map(text => {
          const p = document.createElement('p'); p.textContent = text; return p;
        })));
        let bodySize = product ? 32 : compact ? 30 : 34;
        main.style.fontSize = `${bodySize}px`;

        // Shrink the body (then the title) until the whole stack sits below the
        // top badge and above the 4:5 crop line. No word is ever clipped.
        const article = document.querySelector('article');
        const footerEl = document.querySelector('footer');
        const productEl = document.querySelector('#product');
        const articleRect = article.getBoundingClientRect();
        const minTop = product ? (productEl.getBoundingClientRect().bottom + 18) : (articleRect.top + 86);
        const maxBottom = articleRect.bottom - 2;
        for (let guard = 0; guard < 60; guard++) {
          const titleTop = title.getBoundingClientRect().top;
          const bottom = footerEl.getBoundingClientRect().bottom;
          if (titleTop >= minTop && bottom <= maxBottom) break;
          if (bodySize > 24) { bodySize -= 1; main.style.fontSize = `${bodySize}px`; }
          else if (titleSize > 28) { titleSize -= 1; title.style.fontSize = `${titleSize}px`; }
          else break;
        }
        const titleTop = title.getBoundingClientRect().top;
        const bottom = footerEl.getBoundingClientRect().bottom;
        if (titleTop < minTop - 2 || bottom > maxBottom + 2) {
          throw new Error(`Tamil summary is too long for the 4:5 safe area (title top ${Math.round(titleTop)} < ${Math.round(minTop)} or footer ${Math.round(bottom)} > ${Math.round(maxBottom)})`);
        }
      }, { point, day, i, kind, count: points.length, background: backgrounds[i], badge });

      // Background-only still: this is what the motion engine animates.
      await page.evaluate(() => {
        document.documentElement.style.background = '#0b1526';
        document.body.style.background = '#0b1526';
        document.body.classList.remove('capture-overlay');
        document.body.classList.add('capture-bg');
      });
      await page.screenshot({ path: path.join(folder, `scene-${i + 1}.png`) });

      // Transparent text still: composited after the camera move, so words never zoom.
      await page.evaluate(() => {
        document.body.classList.remove('capture-bg');
        document.body.classList.add('capture-overlay');
        document.documentElement.style.background = 'transparent';
        document.body.style.background = 'transparent';
      });
      await page.screenshot({ path: path.join(folder, `overlay-${i + 1}.png`), omitBackground: true });
      await page.evaluate(() => {
        document.body.classList.remove('capture-overlay');
        document.documentElement.style.background = '#0b1526';
        document.body.style.background = '#0b1526';
      });
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
