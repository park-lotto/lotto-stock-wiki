// 회원 PC 설정 화면 '완성본 받기' 손 점검 — 고객처럼 실제 크롬으로 열어 토큰 넣기 → 연결 → 확인 → 드라이브 켜기 → 시험 보내기.
//   텔레그램 = 가짜 봇 API(받은 영상 바이트를 센다) · 드라이브 = 임시 '내 드라이브' 폴더. 결과물(받은 영상·복사된 파일)로 판정.
//   돌리기: node test/deliver_ui_check.js  → JSON 한 줄 + 화면 그림(SHORTEM_TEST_TMP/deliver_ui/*.png). 어긋나면 rc=1.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { freshDirs, TMP_ROOT } from './helpers.js';
import { ENGINE } from './fake_server.js';

const req = createRequire(new URL('../server/index.js', import.meta.url));
const puppeteer = (await import(pathToFileURL(req.resolve('puppeteer-core')).href)).default;
const root = freshDirs('deliver_ui');
const OUT = path.join(TMP_ROOT, 'deliver_ui');
fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });
process.env.SHORTEM_ENGINE = ENGINE;
process.env.SHORTEM_DEV_PRESET = 'channel/sseolpulda/preset/A_흰바탕창/창아래_검정';
process.env.SHORTEM_NO_BROWSER = '1';
process.env.SHORTEM_DRIVE_ROOT = path.join(root, 'My Drive');
fs.mkdirSync(process.env.SHORTEM_DRIVE_ROOT);
fs.writeFileSync(path.join(process.env.SHORTEM_HOME, 'profiles.json'), JSON.stringify({ presets: [{ id: 'p_5844fd05ae', name: '제품비하인드썰형', desc: '' }] }));
const vdir = path.join(process.env.SHORTEM_WORK, '완성본'); fs.mkdirSync(vdir, { recursive: true });
const VNAME = '시험영상_aaaaaaaaaaaa.mp4';
execFileSync(process.env.FFMPEG || 'ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=1080x1920:rate=30:duration=2', '-pix_fmt', 'yuv420p', path.join(vdir, VNAME)]);   // 2초 시험 영상

const TOKEN = '123456789:AAHfakeTokenForShortemTests_0123456789ab';
const got = { videos: [], updates: [] };
const tg = http.createServer(async (rq, rs) => {
  const ch = []; for await (const d of rq) ch.push(d);
  const m = rq.url.match(/^\/bot([^/]+)\/(\w+)$/);
  const send = o => { rs.writeHead(200, { 'Content-Type': 'application/json' }); rs.end(JSON.stringify(o)); };
  if (!m || m[1] !== TOKEN) return send({ ok: false, description: 'Unauthorized' });
  if (m[2] === 'getMe') return send({ ok: true, result: { username: 'my_shortem_bot' } });
  if (m[2] === 'getUpdates') return send({ ok: true, result: got.updates });
  if (m[2] === 'sendVideo') got.videos.push(Buffer.concat(ch).length);
  return send({ ok: true, result: {} });
});
await new Promise(r => tg.listen(0, '127.0.0.1', r));
process.env.SHORTEM_TELEGRAM_API = `http://127.0.0.1:${tg.address().port}`;

const { startUi } = await import('../server/local_ui.js');
const ui = await startUi();
const browser = await puppeteer.launch({ executablePath: process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'shell', args: ['--no-first-run', '--disable-gpu'], defaultViewport: { width: 1300, height: 1000 } });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e.message || e)));
await page.goto(ui.url, { waitUntil: 'networkidle0' });
const out = {};
const click = async sel => { await page.waitForSelector(sel, { timeout: 15000 }); await page.click(sel); await new Promise(r => setTimeout(r, 700)); };
const text = sel => page.$eval(sel, e => e.innerText).catch(() => '');

await click('.step[data-k="videos"]');
await page.screenshot({ path: path.join(OUT, '1_처음.png') });
await page.type('#tgtoken', TOKEN);
await click('[data-dl="link"]');
out.after_link = await text('#board .sec');
await page.screenshot({ path: path.join(OUT, '2_연결.png') });
got.updates = [{ update_id: 1, message: { chat: { id: 777, type: 'private' }, text: '/start' } }];
await click('[data-dl="confirm"]');
await click('[data-dl="drive"]');
await click('[data-dl="test"]');
await page.waitForSelector('#dlmsg', { timeout: 30000 });
out.dlmsg = await text('#dlmsg');
await page.screenshot({ path: path.join(OUT, '3_시험보내기.png') });
await new Promise(r => setTimeout(r, 3500));                     // 3초마다 다시 읽어도 결과 줄이 남나
out.dlmsg_after_refresh = await text('#dlmsg');
const copied = path.join(process.env.SHORTEM_DRIVE_ROOT, '숏템완성본', VNAME);
out.drive_bytes = fs.existsSync(copied) ? fs.statSync(copied).size : 0;
out.src_bytes = fs.statSync(path.join(vdir, VNAME)).size;
out.tg_videos = got.videos;
out.errors = errors;
out.token_in_page = (await page.content()).includes(TOKEN);
await browser.close(); tg.close();
out.ok = /보냄/.test(out.dlmsg) && /저장됨/.test(out.dlmsg) && out.dlmsg_after_refresh === out.dlmsg && out.drive_bytes === out.src_bytes
  && got.videos.length === 1 && got.videos[0] > out.src_bytes && !errors.length && !out.token_in_page;
console.log(JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
