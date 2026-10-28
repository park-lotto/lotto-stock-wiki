// 회원 PC 설정 화면 손 점검(관제 234 5판, 사장님 "보여주기식 하지 말고 버튼 하나씩 확인") — 고객처럼 실제 크롬으로 열어 누른다.
//   단추마다: 누르기 전/후 미리보기(엔진 렌더러) 그림을 찍어 픽셀이 실제로 바뀌는지 + 설정 파일에 저장됐는지 잰다.
//   돌리기: node test/ui_check.js   (엔진 = ../칼카피숏템엔진, 개발 PC 라 프리셋을 빌리지 않고 엔진 폴더 것을 쓴다)
//   결과: 점검 표(콘솔) + 화면 그림(SHORTEM_TEST_TMP/ui_check/*.png). 하나라도 '안 바뀜'이면 rc=1.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { freshDirs, TMP_ROOT } from './helpers.js';
import { ENGINE } from './fake_server.js';

const req = createRequire(new URL('../server/index.js', import.meta.url));
const puppeteer = (await import(pathToFileURL(req.resolve('puppeteer-core')).href)).default;
const root = freshDirs('ui_check');
const OUT = path.join(TMP_ROOT, 'ui_check');
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
process.env.SHORTEM_ENGINE = ENGINE;
process.env.SHORTEM_DEV_PRESET = 'channel/sseolpulda/preset/A_흰바탕창/창아래_검정';
process.env.SHORTEM_NO_BROWSER = '1';
const PID = 'p_5844fd05ae';
fs.writeFileSync(path.join(process.env.SHORTEM_HOME, 'profiles.json'), JSON.stringify({ presets: [{ id: PID, name: '제품비하인드썰형', desc: '브랜드·제품의 숨은 뒷이야기를 썰로' }, { id: 'p_0000000001', name: '샤크탱크+리뷰형', desc: '시험용 두 번째 카드' }] }));
const { startUi } = await import('../server/local_ui.js');
const ui = await startUi();

const browser = await puppeteer.launch({ executablePath: process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'shell', args: ['--no-first-run', '--disable-gpu'], defaultViewport: { width: 1300, height: 1000 } });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e.message || e)));
page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
// 틀 고르기 목록의 작은 그림(편집기 전용·미리보기 무관)·탭 아이콘은 없어도 된다
page.on('response', r => { if (r.status() >= 400 && !/\/thumbnails\/|favicon/.test(r.url())) errors.push(`${r.status()} ${decodeURIComponent(new URL(r.url()).pathname)}`); });
await page.goto(ui.url, { waitUntil: 'networkidle0' });

const settings = () => JSON.parse(fs.readFileSync(path.join(process.env.SHORTEM_HOME, 'settings.json'), 'utf8'));
const drawn = () => page.evaluate(() => window.__drawn || 0);
// 다시 그림이 실제로 끝날 때까지(그린 횟수가 늘 때까지) — '그리는 중' 표시만 보면 저장→그리기 시작 전에 통과해 옛 그림을 찍는다(10-19 거짓 통과 2번째)
const idle = async (d0) => {
  if (d0 !== undefined) await page.waitForFunction(d => (window.__drawn || 0) > d, { timeout: 90000 }, d0);
  await page.waitForFunction(() => document.getElementById('busy').hidden, { timeout: 90000 }); await new Promise(r => setTimeout(r, 700)); };
const shot = async name => { const el = await page.$('#phone'); const f = path.join(OUT, name + '.png'); await el.screenshot({ path: f }); return crypto.createHash('sha1').update(fs.readFileSync(f)).digest('hex'); };
const rows = [];
async function check(name, act, saved) {
  const before = await shot(name + '_전');
  const d0 = await drawn();
  await act();
  await idle(d0);
  const after = await shot(name + '_후');
  let ok = true, why = '';
  try { ok = saved(settings()); } catch (e) { ok = false; why = String(e.message); }
  rows.push({ 단추: name, 그림바뀜: before !== after, 저장됨: ok, why });
}

// 1) 프리셋 카드 → 화면 탭으로 넘어간다
await page.waitForSelector('[data-preset]');
{ const d = await drawn(); await page.click(`[data-preset="${PID}"]`); await idle(d); }
const step = await page.$eval('.step.on span:last-child', e => e.textContent);
rows.push({ 단추: '프리셋 카드', 그림바뀜: null, 저장됨: settings().current === PID, why: `넘어간 탭=${step}` });
await shot('0_처음');

// 2) 채널명(틀에 채널명 칸이 있는 프리셋일 때만 그림이 바뀐다)
await check('채널명', async () => { await page.$eval('#cname', e => { e.value = ''; }); await page.type('#cname', '우리채널테스트'); await page.$eval('#cname', e => e.dispatchEvent(new Event('change', { bubbles: true }))); },
  s => s.channels[PID].pack.brand.channel_name === '우리채널테스트');
await check('제목 글꼴', () => page.click('[data-font="title_font"][data-v="BMJUA"]'), s => s.channels[PID].pack.text.title_font === 'BMJUA');
// 자막 탭
await page.click('[data-k="cap"]');
await check('자막 글꼴', () => page.click('[data-font="caption_font"][data-v="BlackHanSans"]'), s => s.channels[PID].pack.text.caption_font === 'BlackHanSans');
await check('외곽선', () => page.$eval('#outline', e => { e.value = '10'; e.dispatchEvent(new Event('change', { bubbles: true })); }), s => s.channels[PID].pack.text.caption.outline_px === 10);
await check('낱말 강조 색', () => page.click('[data-emph="color"]'), s => s.channels[PID].pack.text.caption.emphasis.style === 'color');
await check('외곽선 색 흰색', () => page.$eval('#olcolor', e => { e.value = '#ffffff'; e.dispatchEvent(new Event('change', { bubbles: true })); }), s => s.channels[PID].pack.text.caption.outline_rgb.join() === '255,255,255');
await check('자막 등장 톡', () => page.click('[data-enter="pop"]'), s => s.channels[PID].pack.text.caption.enter.kind === 'pop');
// 장면 단추
const nScenes = await page.$$eval('#scenes button', b => b.length);
await check('장면 2', () => page.click('#scenes button:nth-child(2)'), () => true);
// 소리 탭(그림은 안 바뀌는 게 맞다 — 저장만 잰다)
await page.click('[data-k="sound"]');
{ const d = await drawn(); await page.click('[data-voice]:not(.on)'); await idle(d); }
rows.push({ 단추: '목소리', 그림바뀜: null, 저장됨: !!settings().channels[PID].pack.tts.voice_id, why: '소리는 그림 대신 저장으로 잰다' });
// Claude 가 같은 파일을 바꾸면 화면도 따라오나(3초 주기)
const { savePack } = await import('../server/local_settings.js');
const b4 = await shot('9_claude_전');
const d9 = await drawn();
await savePack(PID, { text: { title_font: 'JalnanGothic' } });
await idle(d9);
rows.push({ 단추: 'Claude 가 바꿈(제목 글꼴)', 그림바뀜: b4 !== await shot('9_claude_후'), 저장됨: settings().channels[PID].pack.text.title_font === 'JalnanGothic', why: '' });
// 기본값으로
{ const d = await drawn(); await page.click('#reset'); await idle(d); }
rows.push({ 단추: '프리셋 기본값으로', 그림바뀜: null, 저장됨: !settings().channels[PID], why: '' });

// 미리보기 = 완성본 렌더인가: 화면을 1080 폭(배율 1)로 키워 찍고, 같은 팩으로 공식 렌더 경로가 찍은 장면과 겹친다
await page.click('[data-k="cap"]');
{ const d = await drawn(); await page.click('[data-font="caption_font"][data-v="BMJUA"]'); await idle(d); }
await page.setViewport({ width: 1500, height: 2100 });
await page.addStyleTag({ content: '.main{grid-template-columns:minmax(0,1fr) 1080px!important}.phone{width:1080px!important;border-radius:0!important;border:0!important}' });
await page.evaluate(() => dispatchEvent(new Event('resize')));
async function compare(label, idxs) {
for (const idx of idxs) {
  { const d = await drawn(); await page.click(`#scenes button:nth-child(${idx + 1})`); await idle(d); }
  const el = await page.$('#phone');
  const uiPng = path.join(OUT, `대조_${label}_${idx}.png`);
  await el.screenshot({ path: uiPng });
  const packJson = path.join(OUT, 'pack.json');
  const { packFor } = await import('../server/local_settings.js');
  fs.writeFileSync(packJson, JSON.stringify(await packFor(PID)));
  const work = path.join(OUT, `render_${label}_${idx}`);
  const { execFileSync } = await import('node:child_process');
  const r = JSON.parse(execFileSync('py', [fileURLToPath(new URL('./ui_vs_render.py', import.meta.url)), ENGINE, process.env.SHORTEM_DEV_PRESET, packJson, String(idx), uiPng, work],
    { env: { ...process.env, PYTHONUTF8: '1' } }).toString().trim().split(/\r?\n/).pop());
  rows.push({ 단추: `화면=렌더 ${label} 장면${idx + 1}`, 그림바뀜: r.diff_ratio < 0.01, 저장됨: r.ui_ink > 0.01, why: `차이 ${(r.diff_ratio * 100).toFixed(2)}% · 잉크 화면 ${r.ui_ink} / 렌더 ${r.render_ink}` });
}
}
await compare('프리셋틀', [0, 1]);
// 숏템메이커 템플릿으로 바꾸고 같은 대조(템플릿 그림 = 공식 렌더 경로)
await page.click('[data-k="screen"]');
const b5 = await shot('템플릿_전');
const d5 = await drawn();
await page.click('[data-tpl="story:t11"]');
await idle(d5);
rows.push({ 단추: '템플릿 썰 스타일 01', 그림바뀜: b5 !== await shot('템플릿_후'), 저장됨: settings().channels[PID].pack.template.id === 't11', why: '' });
await compare('템플릿', [0]);
{ const d = await drawn(); await page.click('[data-tpl="none"]'); await idle(d); }
rows.push({ 단추: '프리셋 틀 그대로', 그림바뀜: null, 저장됨: settings().channels[PID].pack.template === 'none', why: '' });
// 화면 스타일이 렌더러 스타일과 같은 글인가(두 벌 어긋남 방지)
const rjs = fs.readFileSync(path.join(ENGINE, 'tools', 'render_scene_style.js'), 'utf8');
const css = await page.evaluate(() => [EXPORT_CSS, EXPORT_CSS2]);
rows.push({ 단추: '렌더러 스타일 같음', 그림바뀜: null, 저장됨: css.every(c => rjs.includes(c)), why: '' });
console.table(rows);
console.log(`장면 수 ${nScenes} · 화면 오류 ${errors.length}`, errors.slice(0, 5));
console.log('그림:', OUT);
await browser.close();
const bad = rows.filter(r => r.저장됨 === false || r.그림바뀜 === false);
process.exit(bad.length || errors.length ? 1 : 0);
