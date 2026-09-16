// 로컬 제작소(8769) 장면꾸미기 화면이 최신 시안 UI와 같은지 실제 DOM으로 대조한다.
// "같을 것이다" 금지 — 화면에 실제로 있는 컨트롤을 뽑아서 센다.
const puppeteer = require('puppeteer');

const JOB = process.argv[2] || 'a00f46d2142b';

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const out = { job: JOB, errors: [] };
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1800, height: 1050 });
    page.on('pageerror', e => out.errors.push(String(e.message)));

    await page.goto('http://127.0.0.1:8769/produce.html', { waitUntil: 'networkidle2', timeout: 60000 });
    await page.evaluate(j => { MIX_JOB = j; document.querySelector('[data-step="3"]').style.display = 'block'; }, JOB);
    await page.click('[onclick="openSceneStyleEditor()"]');
    await page.waitForSelector('dialog[open] iframe');
    const fh = await page.$('dialog[open] iframe');
    out.iframeSrc = await page.$eval('dialog[open] iframe', e => e.src);
    const frame = await fh.contentFrame();
    await frame.waitForFunction(
      () => document.querySelector('[data-connection-status]')?.textContent.includes('연결했습니다'),
      { timeout: 60000 });

    // 본문 모드로 넘겨야 채널명/본문제목/장면자막 칸이 보인다(훅은 제목1/2).
    await frame.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === '본문');
      if (b) b.click();
    });
    await new Promise(r => setTimeout(r, 600));

    out.tabs = await frame.$$eval('.tool-tabs button', els => els.map(e => e.textContent.trim()));
    out.presetCount = await frame.$$eval('[data-preset-id], .preset-card', els => els.length);
    // 화면에 실제로 떠 있는 라벨만 센다(숨은 것 제외).
    out.labels = await frame.evaluate(() => [...document.querySelectorAll('label, .field-label, .row-label, h4, .section-title')]
      .filter(e => e.offsetParent !== null)
      .map(e => e.textContent.trim()).filter(t => t && t.length < 24));
    out.buttons = await frame.evaluate(() => [...document.querySelectorAll('button')]
      .filter(e => e.offsetParent !== null)
      .map(e => e.textContent.trim()).filter(Boolean));
    out.inputs = await frame.evaluate(() => [...document.querySelectorAll('[data-bind]')]
      .map(e => ({ bind: e.dataset.bind, value: (e.value || '').slice(0, 40), shown: e.offsetParent !== null })));
    out.assetVersions = await frame.evaluate(() => [...document.querySelectorAll('script[src], link[href]')]
      .map(e => e.src || e.href).filter(u => /precision20|scene-style|continuous20/.test(u)));

    console.log(JSON.stringify(out, null, 1));
  } catch (e) {
    out.fatal = String(e.message);
    console.log(JSON.stringify(out, null, 1));
    process.exit(1);
  } finally { await browser.close(); }
})();
