import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

test('옛 판이 쓴 yt-dlp 설정(--cookies 한 줄)은 엔진 환경을 만들 때 지금 꼴로 다시 쓴다(11-03 윤상길)', async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'ytc-'));
  process.env.SHORTEM_HOME = home;
  const L = await import('../server/logins.js?' + Date.now());
  const env0 = L.engineCookieEnv();
  assert.equal(env0.XDG_CONFIG_HOME, undefined);          // 쿠키 없음 = 손대지 않음
  L.writeCookies([{ domain: '.youtube.com', name: 'SID', value: 'v', path: '/', expires: 0 }]);
  const cfg = path.join(home, 'ytdlp', 'yt-dlp', 'config');
  fs.writeFileSync(cfg, '--cookies "x"\n');               // 옛 판 꼴
  const env = L.engineCookieEnv();
  assert.ok(env.XDG_CONFIG_HOME);
  const now = fs.readFileSync(cfg, 'utf8');
  assert.match(now, /--js-runtimes node:/);
  assert.match(now, /^# coding: utf-8/);
  assert.equal(L.syncYtdlpConfig(), false);                 // 같으면 다시 안 쓴다
});
