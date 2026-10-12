// 실제 라이브 작업(a00f46d2142b)을 로컬 제작소(8769)에서 열어 장면꾸미기 화면을 찍는다.
// 진짜 사진·자막 위에 템플릿이 입혀진 모습을 보기 위한 로컬 확인용.
const puppeteer = require('puppeteer'), fs = require('fs'), path = require('path');

const JOB = process.argv[2] || 'a00f46d2142b';
const OUT = path.resolve(process.argv[3] || '.tmp/live-demo/shots');
const PRESETS = (process.argv[4] || 't01,t11').split(',');

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({ headless: true });
  const report = { job: JOB, shots: [], errors: [] };
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1800, height: 1050 });
    page.on('pageerror', e => report.errors.push(String(e.message)));

    await page.goto('http://127.0.0.1:8769/produce.html', { waitUntil: 'networkidle2', timeout: 60000 });
    await page.evaluate(j => { MIX_JOB = j; document.querySelector('[data-step="3"]').style.display = 'block'; }, JOB);
    await page.$eval('[onclick="openSceneStyleEditor()"]', e => e.scrollIntoView());
    await page.click('[onclick="openSceneStyleEditor()"]');
    await page.waitForSelector('dialog[open] iframe');
    const frame = await (await page.$('dialog[open] iframe')).contentFrame();
    await frame.waitForFunction(
      () => document.querySelector('[data-connection-status]')?.textContent.includes('연결했습니다'),
      { timeout: 60000 });

    report.scenes = await frame.$eval('[data-scene-total]', e => e.textContent);
    report.caption0 = await frame.$eval('[data-bind="caption"]', e => e.value);

    for (const preset of PRESETS) {
      // 템플릿을 실제 화면 상태로 갈아끼운다(snapshot→load = 화면이 쓰는 같은 경로).
      await frame.evaluate(p => {
        const s = window.sceneStyle.snapshot();
        s.presetId = p;
        window.sceneStyle.load(window.sceneStyle.context(), s);
      }, preset);
      // 사진이 실제로 그려진 뒤에 찍는다 — 로딩 전 촬영은 검정 화면이 된다.
      await frame.waitForFunction(() => {
        const m = document.querySelector('.precision-media');
        return !m || (m.complete && m.naturalWidth > 0) || m.readyState >= 2;
      }, { timeout: 20000 }).catch(() => {});
      await new Promise(r => setTimeout(r, 900));
      const file = path.join(OUT, `live_${preset}.png`);
      await page.screenshot({ path: file });
      report.shots.push(file);
    }
    console.log(JSON.stringify(report, null, 1));
  } catch (e) {
    report.fatal = String(e.message);
    console.log(JSON.stringify(report, null, 1));
    process.exit(1);
  } finally { await browser.close(); }
})();
