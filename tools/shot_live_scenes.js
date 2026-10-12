// 실제 작업의 여러 장면을 넘겨가며 미리보기 영역만 잘라 찍는다.
// 훅 1장 + 본문 장면들이 실제 사진·자막 위에 어떻게 입혀지는지 보기 위함.
const puppeteer = require('puppeteer'), fs = require('fs'), path = require('path');

const JOB = process.argv[2] || 'a00f46d2142b';
const OUT = path.resolve(process.argv[3] || '.tmp/live-demo/scenes');
const PRESET = process.argv[4] || 't01';
const STEPS = (process.argv[5] || '0,4,8,12,16').split(',').map(Number);

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({ headless: true });
  const report = { job: JOB, preset: PRESET, shots: [], errors: [] };
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1800, height: 1050 });
    page.on('pageerror', e => report.errors.push(String(e.message)));

    await page.goto('http://127.0.0.1:8769/produce.html', { waitUntil: 'networkidle2', timeout: 60000 });
    await page.evaluate(j => { MIX_JOB = j; document.querySelector('[data-step="3"]').style.display = 'block'; }, JOB);
    await page.$eval('[onclick="openSceneStyleEditor()"]', e => e.scrollIntoView());
    await page.click('[onclick="openSceneStyleEditor()"]');
    await page.waitForSelector('dialog[open] iframe');
    const fh = await page.$('dialog[open] iframe');
    const frame = await fh.contentFrame();
    await frame.waitForFunction(
      () => document.querySelector('[data-connection-status]')?.textContent.includes('연결했습니다'),
      { timeout: 60000 });

    await frame.evaluate(p => {
      const s = window.sceneStyle.snapshot();
      s.presetId = p;
      window.sceneStyle.load(window.sceneStyle.context(), s);
    }, PRESET);

    let cur = 0;
    for (const target of STEPS) {
      while (cur < target) { await frame.click('[data-scene-step="1"]'); cur++; }
      await frame.waitForFunction(() => {
        const m = document.querySelector('.precision-media');
        return !m || (m.complete && m.naturalWidth > 0) || m.readyState >= 2;
      }, { timeout: 20000 }).catch(() => {});
      await new Promise(r => setTimeout(r, 800));

      const info = await frame.evaluate(() => ({
        caption: document.querySelector('[data-bind="caption"]')?.value || '',
        pos: document.querySelector('[data-scene-pos]')?.textContent || '',
      }));
      // 미리보기 무대만 잘라 찍는다 — 전체 화면은 UI가 대부분을 차지한다.
      const stage = await frame.$('.precision-stage, .layout-a .preview-stage, .stage');
      const file = path.join(OUT, `scene_${String(target).padStart(2, '0')}.png`);
      if (stage) await stage.screenshot({ path: file });
      else await page.screenshot({ path: file });
      report.shots.push({ step: target, pos: info.pos, caption: info.caption, file });
    }
    console.log(JSON.stringify(report, null, 1));
  } catch (e) {
    report.fatal = String(e.message);
    console.log(JSON.stringify(report, null, 1));
    process.exit(1);
  } finally { await browser.close(); }
})();
