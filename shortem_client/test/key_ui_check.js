// 회원 PC 설정 화면 '목소리 키(타입캐스트)' 손 점검 — 실제 크롬으로 소리 단계 → 키 붙여 넣기 → 저장.
//   판정 = 결과물: 키 파일(~/.shortem/keys/typecast)에 그 값이 저장되고, 화면엔 지문만(키 값이 페이지에 없다). 틀린 모양은 거절.
//   돌리기: node test/key_ui_check.js → JSON 한 줄, 어긋나면 rc=1
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { freshDirs, TMP_ROOT } from './helpers.js';
import { ENGINE } from './fake_server.js';

const req = createRequire(new URL('../server/index.js', import.meta.url));
const puppeteer = (await import(pathToFileURL(req.resolve('puppeteer-core')).href)).default;
freshDirs('key_ui');
const OUT = path.join(TMP_ROOT, 'key_ui'); fs.mkdirSync(OUT, { recursive: true });
process.env.SHORTEM_ENGINE = ENGINE;
process.env.SHORTEM_DEV_PRESET = 'channel/sseolpulda/preset/A_흰바탕창/창아래_검정';
process.env.SHORTEM_NO_BROWSER = '1';
fs.writeFileSync(path.join(process.env.SHORTEM_HOME, 'profiles.json'), JSON.stringify({ presets: [{ id: 'p_5844fd05ae', name: '제품비하인드썰형', desc: '' }] }));
const KEY = '__plt_TestTypecastKey_0123456789abcdefXYZ';

const { startUi } = await import('../server/local_ui.js');
const ui = await startUi();
const browser = await puppeteer.launch({ executablePath: process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'shell', args: ['--no-first-run', '--disable-gpu'], defaultViewport: { width: 1300, height: 1000 } });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e.message || e)));
await page.goto(ui.url, { waitUntil: 'networkidle0' });
const click = async sel => { await page.waitForSelector(sel, { timeout: 15000 }); await page.click(sel); await new Promise(r => setTimeout(r, 800)); };
const out = {};
await click('.step[data-k="sound"]');
await page.type('#key_typecast', 'too short');
await click('[data-key="typecast"]');
out.reject_msg = await page.$eval('#board', e => e.innerText.includes('키 모양이 아닙니다')).catch(() => false);
const KEYS = { typecast: KEY, elevenlabs: 'sk_TestElevenKey_0123456789abcdef0123', coupang_access: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', coupang_secret: '0123456789abcdef0123456789abcdef01234567' };
for (const [s, v] of Object.entries(KEYS)) {
  await page.$eval('#key_' + s, e => { e.value = ''; });
  await page.type('#key_' + s, v);
  await click(`[data-key="${s}"]`);
}
await page.screenshot({ path: path.join(OUT, '소리_키저장.png') });
out.saved = Object.entries(KEYS).every(([s, v]) => { const f = path.join(process.env.SHORTEM_HOME, 'keys', s); return fs.existsSync(f) && fs.readFileSync(f, 'utf8') === v; });
out.shown_fp = await page.$eval('#board', e => (e.innerText.match(/✓ 넣음 · [0-9a-f]{12}/g) || []).length).catch(() => 0);
const html = await page.content();
out.key_in_page = Object.values(KEYS).some(v => html.includes(v));
const { keyEnv } = await import('../server/engine/voice.js');
const env = keyEnv();
out.env = Object.keys(env).sort();
out.errors = errors;
await browser.close();
out.ok = out.reject_msg && out.saved && out.shown_fp === 4 && !out.key_in_page && out.env.join() === 'COUPANG_ACCESS_KEY,COUPANG_SECRET_KEY,ELEVENLABS_API_KEY,TYPECAST_API_KEY' && !errors.length;
console.log(JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
