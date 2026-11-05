// 영상 받기 계정 연결(관제 234 5판, 사장님 10-19 "인스타·틱톡 등 본인 PC 에서 되게 / 우리도 처음에 내 PC 안에서 했으니까").
//   우리 PC 방식 그대로: 로그인된 브라우저 쿠키 → yt-dlp(유튜브·틱톡·인스타) · 인스타 세션 파일(media_download 가 쓰는 storage_state 꼴).
//   회원이 자기 크롬 창(숏템 전용 프로필 ~/.shortem/browser)에서 직접 로그인한다 — 비밀번호는 우리가 보지도 치지도 않는다.
//   받는 판단의 주인은 엔진 shopping_shorts/media_download.download_any — 여기는 쿠키 파일만 만든다.
import fs from 'node:fs';
import path from 'node:path';
import { spawn, execFile } from 'node:child_process';
import { createRequire } from 'node:module';
import { homeDir, ensureDir, writeFileIn } from './paths.js';
import { toolPath } from './tools_paths.js';
import { audit } from './audit.js';

const require = createRequire(import.meta.url);
export const PLATFORMS = Object.freeze({
  instagram: { name: '인스타그램', url: 'https://www.instagram.com/accounts/login/', domain: 'instagram.com', ok: ['sessionid'] },
  tiktok: { name: '틱톡', url: 'https://www.tiktok.com/login', domain: 'tiktok.com', ok: ['sessionid', 'sid_tt'], optional: true },   // 안 되면 막지 않고 안내(사장님 11-02)
  youtube: { name: '유튜브', url: 'https://accounts.google.com/ServiceLogin?continue=https%3A%2F%2Fwww.youtube.com%2F', domain: 'youtube.com', ok: ['__Secure-3PSID', 'SAPISID'] },
});
// 빠진 로그인 — required 는 첫 제작을 막고 optional 은 회원에게 안내만 한다(준비 점검 두 곳이 여기를 부른다)
export function missingLogins(connected) {
  const miss = Object.entries(PLATFORMS).filter(([k]) => !connected[k]);
  return { required: miss.filter(([, p]) => !p.optional), optional: miss.filter(([, p]) => p.optional) };
}
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
  syncYtdlpConfig();
  return Object.fromEntries(Object.entries(PLATFORMS).map(([k, pf]) => [k, loggedIn(keep, pf)]));
}

// yt-dlp 설정 한 곳 — 쿠키로 받으면 유튜브가 'n challenge' 를 내고, JS 실행기가 없으면 'The page needs to be reloaded' 로 받기가 죽는다
//   (11-03 회원 박준영 실측: 쿠키 없음 통과·쿠키 있음 실패·숏클 node + ejs 받기면 통과). 숏클이 함께 깐 node 를 쓴다.
export function ytdlpConfig(cookies, node) {
  const q = p => `"${String(p).replace(/\\/g, '/')}"`;
  return '# coding: utf-8\n' + `--cookies ${q(cookies)}\n` + (node ? `--js-runtimes node:${q(node)}\n--remote-components ejs:github\n` : '');
}
// (판단 주인 — yt-dlp 설정 파일 내용) 지금 코드가 만들 내용과 다르면 다시 쓴다. 쿠키를 다시 뽑을 때만 쓰면 옛 판이 쓴 설정
//   (--cookies 한 줄, JS 실행기 없음)이 남아 유튜브 받기가 계속 죽었다(11-03 윤상길 1.0.75 시험 다운로드 2회 실패)
export function syncYtdlpConfig() {
  const want = ytdlpConfig(cookiesFile(), nodeForYtdlp());
  const f = path.join(homeDir(), 'ytdlp', 'yt-dlp', 'config');
  let have = null;
  try { have = fs.readFileSync(f, 'utf8'); } catch { /* 없음 = 쓴다 */ }
  if (have !== want) writeFileIn(homeDir(), path.join('ytdlp', 'yt-dlp', 'config'), want);
  return have !== want;
}
function nodeForYtdlp() {
  try { return toolPath('node'); } catch { return process.execPath; }      // 설치본이 아니면 지금 도는 node
}

// 숏템 전용 프로필의 크롬 본체 찾기(CS #76) — 창을 닫아도 크롬이 뒤에 남으면 exit 이 오지 않아 waiting 이 굳고,
//   다음 실행은 창 없는 프로세스에 넘겨져 화면에 아무것도 안 뜬다. 윈도만 잰다. 못 재면 null(옛 동작 그대로).
export function pickProfileProcs(raw, profile) {
  let rows;
  try { rows = JSON.parse(raw || '[]'); } catch { return null; }
  const norm = t => String(t || '').replace(/\\/g, '/').toLowerCase();
  const want = norm(profile);
  return (Array.isArray(rows) ? rows : [rows]).filter(r => r && norm(r.cmd).includes(want)).map(r => ({ pid: +r.pid, win: +r.win > 0 }));
}
const PS_PROCS = "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*--user-data-dir=*' -and $_.CommandLine -notlike '*--type=*' } | "
  + "ForEach-Object { $g = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; [pscustomobject]@{ pid = $_.ProcessId; cmd = $_.CommandLine; win = [int64]$g.MainWindowHandle } } | ConvertTo-Json -Compress";
function profileProcs() {
  if (process.platform !== 'win32') return Promise.resolve(null);
  return new Promise(res => execFile('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', PS_PROCS], { windowsHide: true, timeout: 15000 },
    (e, out) => res(e ? null : pickProfileProcs(out, profileDir()))));
}
const killProcs = ps => Promise.all(ps.map(p => new Promise(res => execFile('taskkill', ['/PID', String(p.pid), '/T', '/F'], { windowsHide: true }, () => res()))));

// 로그인 창 열기 — 보통 크롬 창 그대로(원격 제어 포트 없이: 구글이 그런 창의 로그인을 '안전하지 않은 브라우저'로 막는다).
//   회원이 로그인하고 창을 닫으면 같은 프로필에서 쿠키를 뽑는다. 바로 돌아오고, 결과는 status() 로 본다.
// (판단 주인 — 로그인 창을 어떻게 여나) 'add' = 전용 크롬 창이 이미 떠 있다 → 그 크롬에 요청한 곳 창을 더 연다 · 'replace' = 창 없이 남은 크롬 → 치우고 새로 · 'new' = 새로.
//   창을 잴 수 없는 PC(procs null)는 앞 창이 안 끝났으면 'add'.
export function openPlan(procs, open) {
  if (procs === null) return open && !open.done ? 'add' : 'new';
  if (procs.some(p => p.win)) return 'add';
  if (procs.length || (open && !open.done)) return 'replace';
  return 'new';
}

// 회원 Claude 에게 줄 말 — 이미 떠 있던 크롬에 더 열었으면 그 창을 모두 닫아야 쿠키가 읽힌다
export function loginOpenedText(r, name, platform = process.platform) {
  // 맥 크롬은 창을 다 닫아도 앱이 살아 있어 로그인 저장(쿠키 읽기)이 안 된다 — Cmd+Q 로 끝내야 한다(11-05 박상혁 #7756)
  const mac = platform === 'darwin' ? ' 맥에서는 창을 닫는 것만으로는 저장이 안 됩니다 — 로그인한 뒤 그 크롬에서 Cmd+Q 로 크롬을 완전히 끝내 주세요.' : '';
  return loginOpenedTextBase(r, name) + mac;
}
function loginOpenedTextBase(r, name) {
  if (r.already) return `이미 떠 있는 숏클 전용 크롬에 ${name} 창을 열었습니다. 그 창에서 ${name}에 로그인한 뒤, 숏클 전용 크롬 창을 모두 닫아 주세요(앞에 열린 다른 사이트 창 포함 — 다 닫아야 저장됩니다). 닫으면 shortem_login(action="status") 로 확인하세요`;
  return `고객에게: 영상 수집 절차에 세션 기록이 한 번 필요합니다. 열린 크롬 창에서 ${name}에 로그인한 뒤 창을 닫아 주세요. 닫으면 shortem_login(action="status") 로 확인하세요`;
}

export async function openLogin(platform) {
  const pf = PLATFORMS[platform];
  if (!pf) return { ok: false, why: '모르는 곳입니다' };
  const exe = browserExe();
  if (!exe) return { ok: false, why: '이 PC 에 크롬·엣지가 없습니다 — 크롬을 설치한 뒤 다시 해 주세요' };
  if (refreshing) await refreshing;       // 쿠키를 읽는 동안 새 창을 열면 그 프로세스로 넘겨져 창이 안 뜬다
  const procs = await profileProcs();
  const how = openPlan(procs, open);
  if (how === 'add') {
    // 11-05 박은숙 #6491: 전용 크롬 창이 이미 있으면(앞 플랫폼 창) 요청한 곳을 열지 않고 '열림'만 돌려줘, 회원이 인스타 창을 끝내 못 봤다.
    //   같은 프로필로 한 번 더 띄우면 떠 있는 크롬에 새 창으로 넘어간다(실측 0.2초 code 21). 쿠키는 그 크롬이 닫힐 때 앞 감시가 모든 곳을 같이 읽는다.
    try { spawn(exe, [`--user-data-dir=${profileDir()}`, '--new-window', pf.url], { detached: false, stdio: 'ignore', windowsHide: false }); } catch { /* 떠 있는 창에서 직접 */ }
    return { ok: true, already: true, platform, with: open && !open.done ? open.platform : null };
  }
  if (how === 'replace') {        // 창 없이 남은 크롬 — 치우고 새로 연다. 지난 창의 쿠키 읽기는 새 창을 닫을 때 같이 된다
    if (open) { open.done = true; open.replaced = true; }
    await killProcs(procs || []);
    await new Promise(r => setTimeout(r, 800));
  }
  const proc = spawn(exe, [`--user-data-dir=${profileDir()}`, '--no-first-run', '--no-default-browser-check', '--disable-background-mode', '--new-window', pf.url],
    { detached: false, stdio: 'ignore', windowsHide: false });
  open = { proc, platform, done: false, result: null };
  const me = open;
  const kill = setTimeout(() => { try { proc.kill(); } catch { /* 이미 닫힘 */ } }, 20 * 60 * 1000);
  let exited = false;
  const exitP = new Promise(res => proc.on('exit', () => { exited = true; res(); }));
  waitLoginClosed({ exited: exitP, isExited: () => exited }).then(async how => {
    clearTimeout(kill);
    me.done = true;
    if (me.replaced) return;
    const st = await refreshCookies();
    me.result = st.connected;
    audit('login', { platform, result: st.connected[platform] ? 'ok' : 'not_logged_in', how });
  }).catch(() => { me.done = true; });
  return { ok: true, platform, opened: true };
}

// (판단 주인 — 로그인 창이 닫혔나) 전용 프로필에 창 있는 크롬이 한 번 보인 뒤 없어지면 닫힌 것. 띄운 프로세스의 종료는 믿지 않는다 —
//   같은 프로필 크롬이 떠 있으면 넘기고 0.2초 만에 끝나고(실측 code 21), 관리자 권한이면 권한을 낮춰 다시 떠서 바로 끝난다(#4511·#4591 김효준).
//   창 없이 남은 크롬은 치운다(쿠키 읽기가 프로필을 열어야 한다). 창을 잴 수 없는 PC(procs null)는 옛 방식 = 프로세스 종료.
export async function waitLoginClosed({ exited, isExited = () => false, procs = profileProcs, kill = killProcs, sleep = ms => new Promise(r => setTimeout(r, ms)),
  every = 5000, limitMs = 20 * 60 * 1000, goneMs = 30000, clock = Date.now } = {}) {
  const t0 = clock();
  let seen = false, goneSince = null;
  while (clock() - t0 < limitMs) {
    const ps = await procs();
    if (ps === null) { await exited; return 'exit'; }
    if (ps.some(p => p.win)) { seen = true; goneSince = null; }
    else if (seen) { if (ps.length) await kill(ps); return 'closed'; }
    else if (!ps.length && isExited()) {                       // 창이 한 번도 안 떴고 크롬도 없다 — 잠깐 기다려 보고 포기
      goneSince = goneSince ?? clock();
      if (clock() - goneSince >= goneMs) return 'gone';
    }
    await sleep(every);
  }
  return 'timeout';
}

// 만들기 전마다 최신 쿠키로(유튜브는 1시간 안에도 세션이 돈다 — 우리 PC 08-31 실측). 로그인 창이 열려 있으면 건너뛴다(프로필 잠김).
//   ★창을 막 닫으면 프로필이 잠깐 잠겨 있다 — 한 번 실패로 끝내면 로그인했는데 '안 됨'으로 굳는다(CS #209). 재시도하고, 끝내 못 읽으면 status 로 알린다.
export async function retrying(fn, waits, sleep = ms => new Promise(r => setTimeout(r, ms))) {
  let last = null;
  for (const w of [0, ...waits]) {
    if (w) await sleep(w);
    try { return { ok: true, value: await fn() }; } catch (e) { last = e; }
  }
  return { ok: false, why: String((last && last.message) || last).slice(0, 160) };
}
let refreshing = null, refreshFailed = false;
export async function refreshCookies() {
  if (open && !open.done) return status();
  if (!fs.existsSync(path.join(profileDir(), 'Default'))) return status();
  const exe = browserExe();
  if (!exe) return status();
  if (refreshing) { await refreshing; return status(); }
  refreshing = retrying(async () => {
    let br = null;
    try {
      br = await puppeteer().launch({ executablePath: exe, headless: 'new', userDataDir: profileDir(), args: ['--no-first-run'] });
      writeCookies(await allCookies(br));
    } finally { if (br) await br.close().catch(() => {}); }
  }, [1500, 4000, 8000]);
  const r = await refreshing;
  refreshing = null;
  refreshFailed = !r.ok;
  if (!r.ok) audit('cookie_refresh', { result: 'fail', why: r.why });
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
  return { connected: out, waiting: !!(open && !open.done) ? open.platform : null, ...(refreshFailed ? { cookie_read_failed: true } : {}) };
}

// 엔진 실행 환경에 넣을 것 — 쿠키가 있을 때만(없으면 종전대로 무쿠키)
export function engineCookieEnv() {
  const env = {};
  if (fs.existsSync(cookiesFile())) {
    syncYtdlpConfig();                 // 엔진·점검이 이 설정을 읽기 직전 — 옛 판이 쓴 꼴이면 지금 꼴로
    env.XDG_CONFIG_HOME = path.join(homeDir(), 'ytdlp');
    env.YTDLP_COOKIES_YOUTUBE = cookiesFile();
    env.YTDLP_COOKIES_TIKTOK = cookiesFile();
  }
  if (fs.existsSync(igStateFile())) env.INSTAGRAM_SESSION_PATH = igStateFile();
  return env;
}
