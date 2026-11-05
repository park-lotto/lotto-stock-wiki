import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

test('시험 다운로드도 제작 받기와 같은 쿠키 환경(engineCookieEnv)을 쓴다', () => {
  const s = fs.readFileSync(new URL('../server/selftest.js', import.meta.url), 'utf8');
  const body = s.slice(s.indexOf('async function testDownload'), s.indexOf('\n}\n', s.indexOf('async function testDownload')));
  assert.match(body, /engineCookieEnv\(\)/);
});
