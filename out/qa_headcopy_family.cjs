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
    frPick('sul_even');
    delete STATE.deco.template.frame.copy_family_override;
  });
  await page.evaluate(() => {
    const panel = document.getElementById('hcText').closest('.panel');
    document.querySelectorAll('.panel').forEach(p => { p.style.display = p === panel ? 'block' : 'none'; });
    const tab = [...document.querySelectorAll('button')]
      .find(b => (b.textContent || '').trim().includes('헤드카피'));
    if (tab) tab.click();
    panel.scrollIntoView({block: 'start'});
  });
  const panel = await page.$('#hcText');
  const owner = await panel.evaluateHandle(el => el.closest('.panel'));
  const scenarios = [
    {
      family: 'youtube_reveal',
      text: '칼질 포기자를 살린\n한국 천재의 발명품',
      subline: '텀블러처럼 생긴 주방도구의 정체?',
    },
    {
      family: 'instagram_story',
      text: '시어머니가 줬다는데\n써보니 반전이었음',
      subline: '주방에서 이걸 꺼낸 이유',
    },
    {
      family: 'demo_direct',
      text: '양파를 넣고 누르면\n다지기가 끝남',
      subline: '칼질 없이 5초 만에 다지기',
    },
  ];
  const results = [];
  for (const scenario of scenarios) {
    const result = await page.evaluate(s => {
      STATE.script_copy_family = s.family;
      delete STATE.deco.template.frame.copy_family_override;
      window._hcCopies = [{
        label: '검증형', text: s.text, subline: s.subline,
        upload_title: s.text.replace('\n', ' '),
      }];
      window._hcPicked = 0;
      useHeadcopy(0);
      const frame = STATE.deco.template.frame;
      return {
        requested: s.family,
        resolved: currentCopyFamily(),
        headcopy: document.getElementById('hcText').value,
        sublineInput: document.getElementById('frTitle').value,
        sublineState: frame.title,
      };
    }, scenario);
    results.push(result);
    await new Promise(r => setTimeout(r, 150));
    await owner.asElement().screenshot({path: `out/qa_headcopy_family_${scenario.family}.png`});
  }
  const explicitTemplateFamily = await page.evaluate(() => {
    frPick('sul_even');
    return currentCopyFamily();
  });
  console.log(JSON.stringify({results, explicitTemplateFamily, errors}, null, 2));
  await browser.close();
  const bad = results.some((r, i) => r.resolved !== scenarios[i].family
    || r.headcopy !== scenarios[i].text
    || r.sublineInput !== scenarios[i].subline
    || r.sublineState !== r.sublineInput);
  if (errors.length || bad || explicitTemplateFamily !== 'youtube_reveal') process.exit(1);
})().catch(e => { console.error(e); process.exit(1); });
