const puppeteer = require('puppeteer');

const url = process.argv[2] || 'http://127.0.0.1:8770/out/scene-style-ui-showcase.html?all-layout=13';

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 900 });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(url, { waitUntil: 'networkidle0' });
  const report = await page.evaluate(async () => {
    const wait = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const rows = window.PRECISION20;
    const failures = [];
    for (let index = 0; index < rows.length; index += 1) {
      document.querySelector(`[data-p20="${index}"]`).click(); await wait();
      for (const kind of ['hook', 'body']) {
        document.querySelector(`[data-frame="${kind}"]`).click(); await wait();
        const preview = document.querySelector('#a-live-preview').getBoundingClientRect();
        for (const el of document.querySelectorAll('#a-live-preview .precision-text')) {
          const rect = el.getBoundingClientRect();
          const range = document.createRange(); range.selectNodeContents(el);
          const content = range.getBoundingClientRect();
          const horizontal = content.left < Math.max(preview.left, rect.left) - 3 || content.right > Math.min(preview.right, rect.right) + 3;
          const vertical = content.top < preview.top - 2 || content.bottom > preview.bottom + 2;
          if (horizontal || vertical) failures.push({ preset: rows[index].name, kind, bind: el.dataset.editBind, text: el.textContent.trim(), horizontal, vertical, previewY: [Math.round(preview.top), Math.round(preview.bottom)], boxY: [Math.round(rect.top), Math.round(rect.bottom)], contentY: [Math.round(content.top), Math.round(content.bottom)], client: [el.clientWidth, el.clientHeight], scroll: [el.scrollWidth, el.scrollHeight], font: getComputedStyle(el).fontSize });
        }
      }
    }
    return { presets: rows.length, screens: rows.length * 2, failures };
  });
  console.log(JSON.stringify({ ...report, errors }, null, 2));
  await browser.close();
  process.exit(report.failures.length || errors.length ? 1 : 0);
})().catch(error => { console.error(error); process.exit(1); });
