const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch({headless: true});
  const page = await browser.newPage();
  await page.setViewport({width: 1728, height: 960});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto('http://127.0.0.1:8770/out/scene-style-ui-showcase.html?motion-test=1', {waitUntil: 'networkidle0'});
  await page.screenshot({path: path.join(process.env.TEMP, 'scene-hook-motion-preview.png')});
  const result = await page.evaluate(async () => {
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const panel = document.querySelector('.hook-motion');
    const buttons = [...document.querySelectorAll('[data-hook-motion]')];
    const effects = [];
    for (const button of buttons) {
      button.click();
      effects.push({name: button.dataset.hookMotion, animations: document.querySelector('#a-live-preview').getAnimations({subtree: true}).length});
      await sleep(760);
    }
    const speeds = [];
    for (const button of document.querySelectorAll('[data-hook-speed]')) {
      button.click();
      const animation = document.querySelector('#a-live-preview').getAnimations({subtree: true})[0];
      speeds.push({name: button.textContent, duration: animation?.effect?.getTiming().duration || 0});
      await sleep(1100);
    }
    const input = document.querySelector('[data-bind="hook1"]');
    input.value += '가';
    input.dispatchEvent(new Event('input', {bubbles: true}));
    await sleep(50);
    const inputTriggeredAnimations = document.querySelector('#a-live-preview').getAnimations({subtree: true}).length;
    document.querySelector('[data-frame="body"]').click();
    const hiddenOnBody = panel.hidden;
    document.querySelector('[data-frame="hook"]').click();
    const visibleOnHook = !panel.hidden;
    document.querySelector('[data-template-mode="continuous"]').click();
    const hiddenOnContinuous = panel.hidden;
    return {buttonCount: buttons.length, speedCount: speeds.length, replayCount: document.querySelectorAll('[data-hook-motion-replay]').length, effects, speeds, inputTriggeredAnimations, hiddenOnBody, visibleOnHook, hiddenOnContinuous};
  });
  result.errors = errors;
  console.log(JSON.stringify(result, null, 2));
  const durations = result.speeds.map(speed => speed.duration);
  const failed = result.buttonCount !== 4 || result.speedCount !== 3 || result.replayCount !== 0 || result.effects.some(effect => effect.animations === 0) || !(durations[0] > durations[1] && durations[1] > durations[2]) || result.inputTriggeredAnimations !== 0 || !result.hiddenOnBody || !result.visibleOnHook || !result.hiddenOnContinuous || errors.length;
  await browser.close();
  process.exit(failed ? 1 : 0);
})().catch(error => { console.error(error); process.exit(1); });
