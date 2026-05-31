const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 2200 });

  const filePath = 'file:///C:/Users/TheRose/Desktop/%EB%A1%9C%EB%98%90%EC%9D%98%20%EC%A3%BC%EC%8B%9D/out/thumbnail_abc.html';
  await page.goto(filePath);
  await page.waitForTimeout(800);

  // C안 = 마지막 .thumb
  const thumbs = await page.$$('.thumb');
  const cAn = thumbs[thumbs.length - 1];
  const outPath = 'C:\\Users\\TheRose\\Desktop\\로또의 주식\\out\\thumbnail_C_final.png';
  await cAn.screenshot({ path: outPath });
  console.log('saved:', outPath);
  await browser.close();
})();
