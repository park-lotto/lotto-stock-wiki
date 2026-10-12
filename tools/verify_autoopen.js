// /꾸미기 로 들어갔을 때 장면꾸미기가 **실제로** 열리는지 확인한다.
// HTML 200 은 확인이 아니다 — 편집기가 뜨고 실제 자막이 붙어야 통과.
const puppeteer = require('puppeteer'), path = require('path'), fs = require('fs');

(async () => {
  const OUT = path.resolve('.tmp/live-demo/shots');
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({ headless: true });
  const r = { errors: [] };
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1800, height: 1050 });
    page.on('pageerror', e => r.errors.push(String(e.message)));

    await page.goto('http://127.0.0.1:8769/꾸미기', { waitUntil: 'networkidle2', timeout: 60000 });

    // 껍데기 → produce iframe → 편집기 iframe (2단 중첩)
    const shell = await (await page.waitForSelector('#f')).contentFrame();
    const dlg = await shell.waitForSelector('dialog[open] iframe', { timeout: 60000 });
    const editor = await dlg.contentFrame();
    await editor.waitForFunction(
      () => document.querySelector('[data-connection-status]')?.textContent.includes('연결했습니다'),
      { timeout: 60000 });

    r.status = await editor.$eval('[data-connection-status]', e => e.textContent.trim());
    r.total = await editor.$eval('[data-scene-total]', e => e.textContent);
    r.channel = await editor.$eval('[data-bind="channel"]', e => e.value);
    await new Promise(x => setTimeout(x, 900));
    r.shot = path.join(OUT, 'autoopen.png');
    await page.screenshot({ path: r.shot });
    r.ok = true;
    console.log(JSON.stringify(r, null, 1));
  } catch (e) {
    r.ok = false; r.fatal = String(e.message);
    console.log(JSON.stringify(r, null, 1));
    process.exit(1);
  } finally { await browser.close(); }
})();
