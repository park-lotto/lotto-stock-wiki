// 영상 받기 계정 연결(관제 234 5판, 사장님 10-19 "인스타·틱톡 등 본인 PC 에서 되게 / 우리도 처음에 내 PC 안에서 했으니까").
//   우리 PC 방식 그대로: 로그인된 브라우저 쿠키 → yt-dlp(유튜브·틱톡·인스타) · 인스타 세션 파일(media_download 가 쓰는 storage_state 꼴).
//   회원이 자기 크롬 창(숏템 전용 프로필 ~/.shortem/browser)에서 직접 로그인한다 — 비밀번호는 우리가 보지도 치지도 않는다.
//   받는 판단의 주인은 엔진 shopping_shorts/media_download.download_any — 여기는 쿠키 파일만 만든다.
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { homeDir, ensureDir, writeFileIn } from './paths.js';
import { audit } from './audit.js';

const require = createRequire(import.meta.url);
export const PLATFORMS = Object.freeze({
  instagram: { name: '인스타그램', url: 'https://www.instagram.com/accounts/login/', domain: 'instagram.com', ok: ['sessionid'] },
  tiktok: { name: '틱톡', url: 'https://www.tiktok.com/login', domain: 'tiktok.com', ok: ['sessionid', 'sid_tt'] },
  youtube: { name: '유튜브', url: 'https://accounts.google.com/ServiceLogin?continue=https%3A%2F%2Fwww.youtube.com%2F', domain: 'youtube.com', ok: ['__Secure-3PSID', 'SAPISID'] },
});
const profileDir = () => ensureDir(homeDir(), 'browser');
const sessDir = () => ensureDir(homeDir(), 'sessions');
export const cookiesFile = () => path.join(sessDir(), 'cookies.txt');
export const igStateFile = () => path.join(sessDir(), 'instagram.json');
let open = null;   // {proc, platform, port, done}

// 로그인 창 = 회원 PC 의 보통 크롬(없으면 엣지). 렌더용 headless 크롬은 창이 없어 못 쓴다.
export function browserExe() {
  if (process.env.SHORTEM_LOGIN_BROWSER) return process.env.SHORTEM_LOGIN_BROWSER;
  const c = process.platform === 'win32'
    ? [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean).flatMap(d => [
      path.join(d, 'Google', 'Chrome', 'Application', 'chrome.exe'), path.join(d, 'Microsoft', 'Edge', 'Application', 'msedge.exe')])
    : process.platform === 'darwin' ? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']
      : ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/microsoft-edge'];
  return c.find(p => { try { return fs.statSync(p).isFile(); } catch { return false; } }) || null;
}

const puppeteer = () => require('puppeteer-core');

async function allCookies(browser) {
  const page = (await browser.pages())[0] || await browser.newPage();
  const cdp = await page.createCDPSession();
  const { cookies } = await cdp.send('Network.getAllCookies');
  await cdp.detach().catch(() => {});
  return cookies;
}

const loggedIn = (cookies, pf) => cookies.some(c => c.domain.replace(/^\./, '').endsWith(pf.domain) && pf.ok.includes(c.name) && c.value);

// 쿠키 → yt-dlp(Netscape) 한 파일(세 곳 모두) + 인스타 storage_state(JSON). 숏템 쓸 곳(세 도메인+구글)만 담는다.
export function writeCookies(cookies) {
  const keep = cookies.filter(c => ['instagram.com', 'tiktok.com', 'youtube.com', 'google.com'].some(d => c.domain.replace(/^\./, '').endsWith(d)));
  const lines = ['# Netscape HTTP Cookie File', '# 숏템이 이 PC 의 숏템 전용 브라우저 프로필에서 뽑았다(관제 234) — 남에게 보내지 마세요'];
  for (const c of keep) {
    const dom = (c.httpOnly ? '#HttpOnly_' : '') + c.domain;
    lines.push([dom, c.domain.startsWith('.') ? 'TRUE' : 'FALSE', c.path || '/', c.secure ? 'TRUE' : 'FALSE', c.expires > 0 ? Math.floor(c.expires) : 0, c.name, c.value].join('\t'));
  }
  writeFileIn(sessDir(), 'cookies.txt', lines.join('\n') + '\n', 0o600);
  const ig = keep.filter(c => c.domain.replace(/^\./, '').endsWith('instagram.com'))
    .map(c => ({ name: c.name, value: c.value, domain: c.domain, path: c.path || '/', expires: c.expires > 0 ? c.expires : -1, httpOnly: !!c.httpOnly, secure: !!c.secure, sameSite: c.sameSite || 'Lax' }));
  if (ig.length) writeFileIn(sessDir(), 'instagram.json', JSON.stringify({ cookies: ig, origins: [] }), 0o600);
  // 엔진의 yt-dlp 호출이 전부 이 쿠키를 쓰게(XDG_CONFIG_HOME/yt-dlp/config — exe·파이썬 모듈 둘 다 읽는다, 10-19 실측)
  //   ★첫 줄 '# coding: utf-8' — 없으면 한국어 윈도의 yt-dlp.exe 가 이 파일을 cp949 로 읽어, 홈 경로에 한글(사용자 이름)이 있으면
  //   'Unable to parse … config' 로 모든 받기가 즉시 죽는다(98 #158, 10-26 잇템로그 회원 실측 2/13 멈춤)
  writeFileIn(homeDir(), path.join('ytdlp', 'yt-dlp', 'config'), `# coding: utf-8\n--cookies "${cookiesFile().replace(/\\/g, '/')}"\n`);
  return Object.fromEntries(Object.entries(PLATFORMS).map(([k, pf]) => [k, loggedIn(keep, pf)]));
}

// 로그인 창 열기 — 보통 크롬 창 그대로(원격 제어 포트 없이: 구글이 그런 창의 로그인을 '안전하지 않은 브라우저'로 막는다).
//   회원이 로그인하고 창을 닫으면 같은 프로필에서 쿠키를 뽑는다. 바로 돌아오고, 결과는 status() 로 본다.
export async function openLogin(platform) {
  const pf = PLATFORMS[platform];
  if (!pf) return { ok: false, why: '모르는 곳입니다' };
  const exe = browserExe();
  if (!exe) return { ok: false, why: '이 PC 에 크롬·엣지가 없습니다 — 크롬을 설치한 뒤 다시 해 주세요' };
  if (open && !open.done) return { ok: true, already: true, platform: open.platform };
  const proc = spawn(exe, [`--user-data-dir=${profileDir()}`, '--no-first-run', '--no-default-browser-check', '--new-window', pf.url],
    { detached: false, stdio: 'ignore', windowsHide: false });
  open = { proc, platform, done: false, result: null };
  const me = open;
  const kill = setTimeout(() => { try { proc.kill(); } catch { /* 이미 닫힘 */ } }, 20 * 60 * 1000);
  proc.on('exit', async () => {
    clearTimeout(kill);
    me.done = true;
    const st = await refreshCookies();
    me.result = st.connected;
    audit('login', { platform, result: st.connected[platform] ? 'ok' : 'not_logged_in' });
  });
  return { ok: true, platform, opened: true };
}

// 만들기 전마다 최신 쿠키로(유튜브는 1시간 안에도 세션이 돈다 — 우리 PC 08-31 실측). 로그인 창이 열려 있으면 건너뛴다(프로필 잠김).
export async function refreshCookies() {
  if (open && !open.done) return status();
  if (!fs.existsSync(path.join(profileDir(), 'Default'))) return status();
  const exe = browserExe();
  if (!exe) return status();
  let br = null;
  try {
    br = await puppeteer().launch({ executablePath: exe, headless: 'new', userDataDir: profileDir(), args: ['--no-first-run'] });
    writeCookies(await allCookies(br));
  } catch (e) {
    audit('cookie_refresh', { result: 'fail' });
  } finally { if (br) await br.close().catch(() => {}); }
  return status();
}

export function status() {
  let txt = '';
  try { txt = fs.readFileSync(cookiesFile(), 'utf8'); } catch { /* 아직 없음 */ }
  const now = Date.now() / 1000;
  const rows = txt.split('\n').filter(l => l && (!l.startsWith('#') || l.startsWith('#HttpOnly_'))).map(l => l.replace(/^#HttpOnly_/, '').split('\t'));
  const out = {};
  for (const [k, pf] of Object.entries(PLATFORMS)) {
    out[k] = rows.some(r => r[0].replace(/^\./, '').endsWith(pf.domain) && pf.ok.includes(r[5]) && r[6] && (r[4] === '0' || +r[4] > now));
  }
  return { connected: out, waiting: !!(open && !open.done) ? open.platform : null };
}

// 엔진 실행 환경에 넣을 것 — 쿠키가 있을 때만(없으면 종전대로 무쿠키)
export function engineCookieEnv() {
  const env = {};
  if (fs.existsSync(cookiesFile())) {
    env.XDG_CONFIG_HOME = path.join(homeDir(), 'ytdlp');
    env.YTDLP_COOKIES_YOUTUBE = cookiesFile();
    env.YTDLP_COOKIES_TIKTOK = cookiesFile();
  }
  if (fs.existsSync(igStateFile())) env.INSTAGRAM_SESSION_PATH = igStateFile();
  return env;
}
