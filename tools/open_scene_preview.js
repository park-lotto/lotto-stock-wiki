const puppeteer = require('puppeteer');

const url = process.argv[2] || 'http://127.0.0.1:8770/out/scene-style-ui-showcase.html';

(async () => {
  const browser = await puppeteer.launch({
    headless: false,
    channel: 'chrome',
    defaultViewport: null,
    args: ['--start-maximized'],
  });
  const pages = await browser.pages();
  const page = pages[0] || await browser.newPage();
  await page.goto(url, {waitUntil: 'networkidle0'});
  await page.bringToFront();
  console.log(`SCENE_PREVIEW_OPEN ${url}`);
  await new Promise(() => {});
})().catch(error => {
  console.error(error);
  process.exit(1);
});
