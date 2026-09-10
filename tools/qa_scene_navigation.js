const puppeteer = require('puppeteer');

const url = process.argv[2] || 'http://127.0.0.1:8770/out/scene-style-ui-showcase.html?scene-nav=12';

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 900 });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(url, { waitUntil: 'networkidle0' });
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

  const result = await page.evaluate(async () => {
    const wait = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const current = () => document.querySelector('[data-scene-current]').textContent;
    const click = selector => document.querySelector(selector).click();
    const channelBox = () => document.querySelector('.precision-patch[data-edit-bind="channel"]').getBoundingClientRect().width;
    const captionTop = () => document.querySelector('.precision-text[data-edit-bind="caption"]').getBoundingClientRect().top;
    const report = {};
    const panes = [...document.querySelectorAll('.layout-a>.pane')].map(el => Math.round(el.getBoundingClientRect().width));
    const phoneRect = document.querySelector('#a-live-preview').getBoundingClientRect();
    const firstThumb = document.querySelector('.layout-a .preset-card img').getBoundingClientRect();
    report.layout = { panes, phone: [Math.round(phoneRect.width), Math.round(phoneRect.height)], thumbnail: [Math.round(firstThumb.width), Math.round(firstThumb.height)] };

    report.initialScene = current();
    click('[data-scene-step="1"]'); await wait();
    report.nextScene = current();
    report.bodySelected = document.querySelector('[data-frame="body"]').classList.contains('active');
    report.captionReadonly = document.querySelector('[data-bind="caption"]').readOnly;

    const centerTop = captionTop();
    click('[data-caption-position="-1"]'); await wait();
    const upperTop = captionTop();
    click('[data-caption-position="1"]'); await wait();
    const lowerTop = captionTop();
    click('[data-caption-position="0"]'); await wait();
    report.captionMovement = { upper: upperTop < centerTop, lower: lowerTop > centerTop, reset: Math.abs(captionTop() - centerTop) < 1 };
    for (let i = 0; i < 10; i += 1) { click('[data-scene-step="1"]'); await wait(); }
    report.lastScene = current();
    report.nextDisabledAtEnd = document.querySelector('[data-scene-step="1"]').disabled;
    for (let i = 0; i < 11; i += 1) { click('[data-scene-step="-1"]'); await wait(); }
    report.firstSceneAgain = current();
    report.previousDisabledAtStart = document.querySelector('[data-scene-step="-1"]').disabled;

    click('[data-frame="hook"]'); await wait();
    const input = document.querySelector('[data-bind="channel"]');
    const beforeWidth = channelBox();
    input.value = '숏템OOOOOO'; input.dispatchEvent(new Event('input', { bubbles: true })); await wait();
    const grownWidth = channelBox();
    click('[data-field-key="channel"] [data-font-step="-0.08"]'); await wait();
    click('[data-field-key="channel"] [data-field-reset]'); await wait();
    report.channel = { beforeWidth, grownWidth, expanded: grownWidth > beforeWidth, valueReset: input.value === '숏템', sizeReset: document.querySelector('[data-field-key="channel"] output').textContent === '100%' };
    report.fieldResets = {};
    for (const bind of ['hook1', 'hook2']) {
      const fieldInput = document.querySelector(`[data-bind="${bind}"]`);
      const presetValue = fieldInput.value;
      fieldInput.value += 'TEST'; fieldInput.dispatchEvent(new Event('input', { bubbles: true })); await wait();
      click(`[data-field-key="${bind}"] [data-font-step="-0.08"]`); await wait();
      click(`[data-field-key="${bind}"] [data-field-reset]`); await wait();
      report.fieldResets[bind] = fieldInput.value === presetValue && document.querySelector(`[data-field-key="${bind}"] output`).textContent === '100%';
    }
    report.guide = document.querySelector('.caption-guide').textContent;
    click('[data-scene-step="1"]'); await wait();
    return report;
  });

  await settle();
  await page.screenshot({ path: 'out/scene-navigation-qa.png', fullPage: false });
  console.log(JSON.stringify({ ...result, errors }, null, 2));
  const ok = result.initialScene === '1' && result.nextScene === '2' && result.bodySelected && result.captionReadonly
    && Object.values(result.captionMovement).every(Boolean) && result.channel.expanded
    && result.lastScene === '12' && result.nextDisabledAtEnd && result.firstSceneAgain === '1' && result.previousDisabledAtStart
    && result.layout.panes[0] >= 400 && result.layout.panes[2] >= 480 && result.layout.phone[1] >= 560 && result.layout.thumbnail[0] >= 75
    && result.channel.valueReset && result.channel.sizeReset && Object.values(result.fieldResets).every(Boolean) && errors.length === 0;
  await browser.close();
  process.exit(ok ? 0 : 1);
})().catch(error => { console.error(error); process.exit(1); });
