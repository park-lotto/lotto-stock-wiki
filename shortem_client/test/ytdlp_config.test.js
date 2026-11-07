import test from 'node:test';
import assert from 'node:assert/strict';
import { ytdlpConfig } from '../server/logins.js';

test('쿠키로 받을 때 JS 실행기(숏클 node)와 ejs 를 함께 켠다(11-03 n challenge)', () => {
  const c = ytdlpConfig('C:\\Users\\x\\.shortem\\sessions\\cookies.txt', 'C:\\S\\tools\\node\\node.exe');
  assert.match(c, /^# coding: utf-8\n/);
  assert.match(c, /--cookies "C:\/Users\/x\/\.shortem\/sessions\/cookies\.txt"/);
  assert.match(c, /--js-runtimes node:"C:\/S\/tools\/node\/node\.exe"/);
  assert.match(c, /--remote-components ejs:github/);
});
