const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 900 });
  await page.goto('http://127.0.0.1:8770/out/scene-style-ui-showcase.html?visual=13', { waitUntil: 'networkidle0' });
  for (const index of [5, 8, 10]) {
    await page.evaluate(i => document.querySelector(`[data-p20="${i}"]`).click(), index);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.screenshot({ path: `out/preset-${index}-qa.png` });
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
