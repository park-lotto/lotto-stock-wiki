// #4356(11-04 김만기): VMake 키가 'app_key:secret' 꼴이 아니라 지우기가 전부 서명 오류 — 키를 넣을 때 꼴을 안 봐 제작 도중에야 드러났다.
//   키 꼴 = KEY_SERVICES[service].shape(정규식) 한 곳. saveKey 는 거절, readKey 는 없는 키로(준비 점검이 다시 넣으라고 한다).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('key_shape');
const { saveKey, readKey } = await import('../server/engine/voice.js');
const { homeDir } = await import('../server/paths.js');

test('VMake 키는 app_key:secret 꼴만 저장', () => {
  const bad = saveKey('vmake', 'abcdefghijklmnopqrstuvwxyz123456');
  assert.equal(bad.ok, false);
  assert.match(bad.why, /:/);
  assert.equal(saveKey('vmake', 'appkey1234567890:secret1234567890').ok, true);
});

test('이미 저장된 꼴 틀린 VMake 키는 없는 키로 본다', () => {
  fs.mkdirSync(path.join(homeDir(), 'keys'), { recursive: true });
  fs.writeFileSync(path.join(homeDir(), 'keys', 'vmake'), 'abcdefghijklmnopqrstuvwxyz123456');
  assert.equal(readKey('vmake'), '');
});
