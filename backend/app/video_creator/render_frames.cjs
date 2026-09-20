// Chromium's text shaping preserves Tamil vowel signs and ligatures on Windows.
const path = require('path');
const fs = require('fs');
const root = path.resolve(__dirname, '../../..');
const { chromium } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
const folder = process.argv[2];
const { points, day, kind = 'history', backgrounds = [] } = JSON.parse(fs.readFileSync(path.join(folder, 'frames.json'), 'utf8'));
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:720}, deviceScaleFactor:1});
    await page.setContent(`<html><head><meta charset="utf-8"><style>
      *{box-sizing:border-box}body{margin:0;background:#101b30;color:white;font-family:'Nirmala UI',sans-serif}
      #background{position:absolute;inset:0;width:1280px;height:720px;object-fit:cover;z-index:-1}
      article{margin:30px 32px;height:660px;border:2px solid #30c6b080;border-radius:28px;padding:32px 38px;background:linear-gradient(90deg,#101b30e8,#101b3070)}
      header{color:#54e3c6;font-size:25px}h1{color:#ffce73;font-size:66px;margin:22px 0}
      main{font-size:34px;line-height:1.6;height:340px;background:#071426a8;border-radius:16px;padding:12px 16px;text-shadow:0 2px 4px #000}p{margin:0 0 20px}footer{position:absolute;bottom:44px;font-size:18px;color:#cbd5e1;max-width:1120px}
      body.photo article{background:linear-gradient(90deg,#071426ed 0%,#071426bb 65%,#07142618 100%)}
      body.photo main{width:840px;background:#07142680}
      body.photo footer{background:#071426d9;padding:4px 8px;border-radius:6px;font-size:16px}
    </style></head><body><img id="background"/><article><header></header><h1></h1><main lang="ta"></main><footer></footer></article></body></html>`);
    for(let i=0;i<points.length;i++) {
      await page.evaluate(async ({point,day,i,kind,count,background})=>{
        const image = document.querySelector('#background');
        if (background) { image.src=background.image; await image.decode(); }
        else { image.removeAttribute('src'); }
        const law = kind === 'indian-law';
        const photo = background?.provider === 'pexels';
        document.body.classList.toggle('photo', photo);
        document.querySelector('header').textContent=`${law ? 'INDIAN LAW — DAILY 5 ACTS' : 'DAY OF HISTORY'} | ${day} | ${i+1}/${count}`;
        const title=document.querySelector('h1');
        title.textContent=law ? point.title : point.year;
        title.style.fontSize=law ? '30px' : '66px';
        title.style.minHeight=law ? (photo ? '60px' : '85px') : '';
        document.querySelector('footer').textContent=law ? 'Indian central Acts · Educational overview · Sources: India Code' : 'Wikipedia via History API · AI Tamil narration';
        if (photo) document.querySelector('footer').textContent += ` | Illustrative photo: ${background.photographer} / Pexels`;
        else if (background) document.querySelector('footer').textContent += ` | Illustration: ${background.topic}`;
        const main=document.querySelector('main');
        main.style.height=law ? (photo ? '405px' : '370px') : '340px';
        main.style.lineHeight=law ? '1.4' : '1.6';
        main.replaceChildren(...point.lines.map(text=>{const p=document.createElement('p');p.textContent=text;p.style.marginBottom=law ? '10px' : '20px';return p;}));
        main.style.fontSize='34px';
        for(let size=34;main.scrollHeight>main.clientHeight && size>24;size-=2) main.style.fontSize=`${size-2}px`;
        if(main.scrollHeight>main.clientHeight) throw new Error('Tamil summary is too long for the frame');
      }, {point:points[i],day,i,kind,count:points.length,background:backgrounds[i]});
      await page.screenshot({path:path.join(folder,`scene-${i+1}.png`)});
    }
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
