const puppeteer = require('puppeteer');

const url = process.argv[2] || 'http://127.0.0.1:8770/out/scene-style-ui-showcase.html?qa=5';
const testValues = {
  channel: '채널명테스트123',
  hook1: '수정해도깨지지않는긴제목',
  hook2: '두번째제목도영역안에맞춤',
  bodyTitle: '본문제목도길이에맞춰안전하게표시',
  caption: '현재장면자막도서로영향없이변경',
};

async function settle(page) {
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1728, height: 960 });
  const runtimeErrors = [];
  page.on('pageerror', (error) => runtimeErrors.push(String(error)));
  page.on('requestfailed', (request) => runtimeErrors.push(`${request.url()} ${request.failure()?.errorText || 'failed'}`));
  await page.goto(url, { waitUntil: 'networkidle0' });

  const report = await page.evaluate(async (values) => {
    const rows = window.PRECISION20;
    const preview = document.querySelector('#a-live-preview');
    const sleepFrames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const inputValues = () => Object.fromEntries([...document.querySelectorAll('.layout-a [data-bind]')].map((el) => [el.dataset.bind, el.value]));
    const select = async (index) => {
      document.querySelector(`[data-p20="${index}"]`).click();
      await sleepFrames();
    };
    const frame = async (kind) => {
      document.querySelector(`.layout-a [data-frame="${kind}"]`).click();
      await sleepFrames();
    };
    const drawnBoxes = (isShortem, kind) => {
      const selector = isShortem
        ? kind === 'hook'
          ? '.brand-row b,.hook-copy strong,.hook-copy em,.hook-band'
          : '.brand-row b,.shortem-body-channel,.body-title-area b,.body-band'
        : '.precision-text';
      return [...preview.querySelectorAll(selector)].filter((el) => {
        const style = getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
      });
    };
    const failures = [];
    const results = [];

    for (let index = 0; index < rows.length; index += 1) {
      const preset = rows[index];
      await select(index);
      const visibleFields = [...document.querySelectorAll('.layout-a .field:not([hidden])')];
      if (visibleFields.some((field) => field.querySelectorAll('[data-font-step]').length !== 2)) failures.push(`${preset.name}: 글자 크기 버튼 누락`);
      for (const field of visibleFields) {
        const output = field.querySelector('.font-stepper output');
        const beforeScale = output?.textContent;
        field.querySelector('[data-font-step="0.08"]')?.click();
        await sleepFrames();
        if (!output || output.textContent === beforeScale) failures.push(`${preset.name}/${field.dataset.fieldKey}: 글자 크기 + 버튼 작동 실패`);
        field.querySelector('[data-font-step="-0.08"]')?.click();
        await sleepFrames();
      }
      const before = inputValues();
      const channel = document.querySelector('[data-bind="channel"]');
      channel.value = `${before.channel}d`;
      channel.dispatchEvent(new Event('input', { bubbles: true }));
      await sleepFrames();
      const after = inputValues();
      const changed = Object.keys(after).filter((key) => before[key] !== after[key]);
      if (changed.join(',') !== 'channel') failures.push(`${preset.name}: 채널명 수정이 ${changed.join(',')} 필드에 영향`);

      await select(index);
      for (const kind of ['hook', 'body']) {
        await frame(kind);
        for (const input of document.querySelectorAll('.layout-a .field:not([hidden]) [data-bind]')) {
          input.value = values[input.dataset.bind] || '테스트';
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        await sleepFrames();
        const rect = preview.getBoundingClientRect();
        const boxes = drawnBoxes(preset.id === 's0101', kind);
        for (const el of boxes) {
          const box = el.getBoundingClientRect();
          const horizontalOverflow = box.left < rect.left - 3 || box.right > rect.right + 3 || el.scrollWidth > el.clientWidth + 2;
          if (horizontalOverflow) failures.push(`${preset.name}/${kind}: ${el.textContent.trim()} 가로 넘침`);
        }
        const sourceOk = preset.id === 's0101'
          ? decodeURIComponent(getComputedStyle(preview).backgroundImage).includes(kind === 'hook' ? '숏템_훅' : '숏템_본문')
          : preview.querySelector('.precision-base').getAttribute('src') === (kind === 'hook' ? preset.hook_image : preset.body_image);
        if (!sourceOk) failures.push(`${preset.name}/${kind}: 원본 이미지 전환 실패`);
        results.push({ preset: preset.name, kind, fields: [...document.querySelectorAll('.layout-a .field:not([hidden]) [data-bind]')].map((el) => el.dataset.bind), drawn: boxes.length });
      }

      if (index > 0) {
        await select(0);
        const base = preview.querySelector('.precision-base');
        const expectedShortemFrame = preview.classList.contains('is-body') ? '숏템_본문' : '숏템_훅';
        if (!preview.classList.contains('template-shortem') || getComputedStyle(base).display !== 'none' || !decodeURIComponent(getComputedStyle(preview).backgroundImage).includes(expectedShortemFrame)) {
          failures.push(`${preset.name}에서 숏템 기본형으로 복귀 실패`);
        }
      }
    }
    const imagesFailed = [...document.images].filter((img) => img.complete && img.naturalWidth === 0).map((img) => img.src);
    return { count: rows.length, results, failures, imagesFailed };
  }, testValues);

  await settle(page);
  report.runtimeErrors = runtimeErrors;
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
  process.exit(report.failures.length || report.imagesFailed.length || report.runtimeErrors.length ? 1 : 0);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
