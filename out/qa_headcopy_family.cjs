const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
  });
  const page = await browser.newPage();
  await page.setViewport({width: 1500, height: 1100, deviceScaleFactor: 1});
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8894/produce', {waitUntil: 'networkidle0'});
  await page.waitForFunction(() => typeof frPick === 'function');
  await page.evaluate(async () => {
    const data = await (await fetch('/api/produce/frame/presets')).json();
    FR_PRESETS = data.presets || [];
  });
  const result = await page.evaluate(() => {
    window._hcCopies = [{
      label: '결과형',
      text: '칼질 포기자를 살린\n한국 천재의 발명품',
      subline: '텀블러처럼 생긴 주방도구의 정체?',
      upload_title: '칼질 포기자를 살린 한국 천재의 발명품',
    }];
    frPick('sul_even');
    useHeadcopy(0);
    const frame = STATE.deco.template.frame;
    return {
      family: currentCopyFamily(),
      headcopy: document.getElementById('hcText').value,
      sublineInput: document.getElementById('frTitle').value,
      sublineState: frame.title,
      preset: frame.preset,
    };
  });
  await page.evaluate(() => {
    const panel = document.getElementById('hcText').closest('.panel');
    document.querySelectorAll('.panel').forEach(p => { p.style.display = p === panel ? 'block' : 'none'; });
    panel.scrollIntoView({block: 'start'});
  });
  const panel = await page.$('#hcText');
  const owner = await panel.evaluateHandle(el => el.closest('.panel'));
  await owner.asElement().screenshot({path: 'out/qa_headcopy_family.png'});
  await page.evaluate(() => {
    const tab = [...document.querySelectorAll('button')]
      .find(b => (b.textContent || '').trim().includes('헤드카피'));
    if (tab) tab.click();
  });
  await new Promise(r => setTimeout(r, 200));
  await owner.asElement().screenshot({path: 'out/qa_headcopy_family_head.png'});
  console.log(JSON.stringify({result, errors}, null, 2));
  await browser.close();
  if (errors.length || result.family !== 'youtube_reveal'
      || result.sublineInput !== '텀블러처럼 생긴 주방도구의 정체?'
      || result.sublineState !== result.sublineInput) process.exit(1);
})().catch(e => { console.error(e); process.exit(1); });
