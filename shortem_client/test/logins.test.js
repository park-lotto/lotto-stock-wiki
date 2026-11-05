// 영상 받기 계정 연결(관제 234 5판) — 쿠키 파일 꼴·연결 판정·엔진 환경 + 만든 파일을 yt-dlp 가 진짜로 읽는가
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { freshDirs } from './helpers.js';

freshDirs('logins');
const L = await import('../server/logins.js');
const far = Date.now() / 1000 + 86400 * 30;
const ck = [
  { name: 'sessionid', value: 'IGSESSION', domain: '.instagram.com', path: '/', expires: far, httpOnly: true, secure: true, sameSite: 'Lax' },
  { name: 'csrftoken', value: 'x', domain: '.instagram.com', path: '/', expires: far, httpOnly: false, secure: true },
  { name: 'ttwid', value: 'y', domain: '.tiktok.com', path: '/', expires: far, httpOnly: true, secure: true },
  { name: 'SAPISID', value: 'z', domain: '.youtube.com', path: '/', expires: far, httpOnly: false, secure: true },
  { name: 'other', value: 'q', domain: '.naver.com', path: '/', expires: far },
];

test('쿠키 → Netscape 한 파일·인스타 세션 JSON·yt-dlp 설정, 숏템이 쓸 곳만 담는다', () => {
  const r = L.writeCookies(ck);
  assert.deepEqual(r, { instagram: true, tiktok: false, youtube: true });
  const txt = fs.readFileSync(L.cookiesFile(), 'utf8');
  assert.match(txt, /^# Netscape HTTP Cookie File/);
  assert.match(txt, /#HttpOnly_\.instagram\.com\tTRUE\t\/\tTRUE\t\d+\tsessionid\tIGSESSION/);
  assert.ok(!txt.includes('naver'), '숏템과 무관한 사이트 쿠키는 안 담는다');
  const ig = JSON.parse(fs.readFileSync(L.igStateFile(), 'utf8'));
  assert.equal(ig.cookies.length, 2);
  assert.deepEqual(L.status().connected, { instagram: true, tiktok: false, youtube: true });
  const env = L.engineCookieEnv();
  assert.equal(env.INSTAGRAM_SESSION_PATH, L.igStateFile());
  const conf = fs.readFileSync(path.join(env.XDG_CONFIG_HOME, 'yt-dlp', 'config'), 'utf8');
  assert.ok(conf.includes(L.cookiesFile().replace(/\\/g, '/')));
});

// 바깥 사이트에 접속하지 않는다 — yt-dlp 는 --cookies 파일을 시작 때 읽어 꼴이 틀리면 'does not look like a Netscape format' 을 낸다(주소 없이도).
//   11-05: 실제 틱톡 주소로 종료코드 0 까지 요구해, 틱톡이 자동 접속에 챌린지 화면을 주자 쿠키 꼴과 무관하게 빨강 → 1.0.106 빠른배포가 멈췄다.
const ytdlpRead = (env) => {
  const r = spawnSync(process.platform === 'win32' ? 'py' : 'python3', ['-m', 'yt_dlp', '--verbose', '--simulate', 'notaurl'], { env, encoding: 'utf8', timeout: 120000 });
  return (r.stdout || '') + (r.stderr || '');
};

test('만든 쿠키 파일·설정을 yt-dlp 가 그대로 읽는다(파일 꼴 오류 없음)', () => {
  L.writeCookies(ck);
  const log = ytdlpRead({ ...process.env, ...L.engineCookieEnv() });
  assert.match(log, /User config .*yt-dlp.config.*--cookies/, '설정 파일을 안 읽었다');
  assert.doesNotMatch(log, /does not look like a Netscape format|skipping cookie file entry/i, log.slice(-500));
  assert.match(log, /not a valid URL/, '쿠키를 읽은 뒤 주소 단계까지 와야 한다 — ' + log.slice(-300));
});

test('사보타주: 쿠키 파일 꼴이 깨지면 위 시험이 잡는다', () => {
  L.writeCookies(ck);
  const keep = fs.readFileSync(L.cookiesFile(), 'utf8');
  try {
    fs.writeFileSync(L.cookiesFile(), 'this is not a cookie file\n\tbroken\tline\n');
    assert.match(ytdlpRead({ ...process.env, ...L.engineCookieEnv() }), /does not look like a Netscape format|skipping cookie file entry/i);
  } finally {
    fs.writeFileSync(L.cookiesFile(), keep);
  }
});

test('홈 경로에 한글이 있어도 yt-dlp 가 설정 파일을 읽는다(98 #158 — 한국어 윈도 cp949)', () => {
  L.writeCookies(ck);
  const conf = fs.readFileSync(path.join(L.engineCookieEnv().XDG_CONFIG_HOME, 'yt-dlp', 'config'), 'utf8');
  assert.match(conf, /^# coding: utf-8\n/, '첫 줄 인코딩 표기');
  // 같은 설정 꼴을 한글 폴더에 두고(쿠키 경로도 한글) yt-dlp 를 진짜로 돌린다 — 파싱 실패면 'Unable to parse'
  const dir = fs.mkdtempSync(path.join(path.dirname(L.cookiesFile()), '한글홈_'));
  fs.mkdirSync(path.join(dir, 'yt-dlp'), { recursive: true });
  fs.copyFileSync(L.cookiesFile(), path.join(dir, '쿠키.txt'));
  fs.writeFileSync(path.join(dir, 'yt-dlp', 'config'), conf.replace(/--cookies "[^"]+"/, `--cookies "${path.join(dir, '쿠키.txt').replace(/\\/g, '/')}"`));
  const r = spawnSync(process.platform === 'win32' ? 'yt-dlp' : 'yt-dlp', ['--simulate', 'notaurl'], { env: { ...process.env, XDG_CONFIG_HOME: dir }, encoding: 'utf8', timeout: 60000 });
  const log = (r.stdout || '') + (r.stderr || '');
  assert.doesNotMatch(log, /Unable to parse/, log.slice(-300));
  assert.match(log, /not a valid URL/, log.slice(-300));
});

test('만료된 로그인 쿠키는 연결 안 됨으로 본다', () => {
  L.writeCookies([{ ...ck[0], expires: Date.now() / 1000 - 10 }]);
  assert.equal(L.status().connected.instagram, false);
});

test('창 없이 남은 전용 프로필 크롬만 고른다(CS #76)', async () => {
  const { pickProfileProcs } = await import('../server/logins.js');
  const prof = 'C:\\Users\\A\\.shortem\\browser';
  const raw = JSON.stringify([
    { pid: 1, cmd: '"chrome.exe" --user-data-dir=C:\\Users\\A\\.shortem\\browser --no-first-run', win: 0 },
    { pid: 2, cmd: '"chrome.exe" --user-data-dir=C:\\Other', win: 100 },
    { pid: 3, cmd: '"chrome.exe" --user-data-dir=c:/users/a/.shortem/browser', win: 500 },
  ]);
  assert.deepEqual(pickProfileProcs(raw, prof), [{ pid: 1, win: false }, { pid: 3, win: true }]);
  assert.deepEqual(pickProfileProcs(JSON.stringify({ pid: 4, cmd: `x ${prof}`, win: 0 }), prof), [{ pid: 4, win: false }]);   // 한 건이면 배열이 아니다
  assert.deepEqual(pickProfileProcs('', prof), []);
  assert.equal(pickProfileProcs('깨진', prof), null);
});

test('쿠키 읽기는 프로필 잠김을 재시도하고 끝내 실패하면 알린다(CS #209)', async () => {
  const { retrying } = await import('../server/logins.js');
  let n = 0;
  const flaky = async () => { if (++n < 3) throw new Error('프로필 잠김'); return 'ok'; };
  assert.deepEqual(await retrying(flaky, [1, 1, 1], async () => {}), { ok: true, value: 'ok' });
  assert.equal(n, 3);
  const bad = await retrying(async () => { throw new Error('안 됨'); }, [1], async () => {});
  assert.equal(bad.ok, false);
  assert.match(bad.why, /안 됨/);
});
