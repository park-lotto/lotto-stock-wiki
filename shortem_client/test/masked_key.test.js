// 가려진 키는 저장하지 않고, 저장돼 있으면 없는 키로 본다(CS #453)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

process.env.SHORTEM_HOME = fs.mkdtempSync(path.join(os.tmpdir(), 'shortem-key-'));
const { saveKey, readKey, isMaskedKey, keyFile, keyStatus } = await import('../server/engine/voice.js');
const masked = 'abcd1234' + '•'.repeat(8) + 'wxyz9';

test('가린 표시값은 저장을 거절한다', () => {
  assert.equal(masked.length, 21);
  assert.equal(isMaskedKey(masked), true);
  const r = saveKey('typecast', masked);
  assert.equal(r.ok, false);
  assert.match(r.why, /가려진 키/);
  assert.equal(fs.existsSync(keyFile('typecast')), false);
});

test('이미 저장된 가린 값은 없는 키로 보고 치운다', () => {
  fs.mkdirSync(path.dirname(keyFile('gemini')), { recursive: true });
  fs.writeFileSync(keyFile('gemini'), masked);
  assert.equal(readKey('gemini'), '');
  assert.equal(fs.existsSync(keyFile('gemini')), false);
  assert.equal(keyStatus('gemini').present, false);
});

test('정상 키는 그대로', () => {
  assert.equal(saveKey('typecast', 'abcdefghijklmnop1234').ok, true);
  assert.equal(readKey('typecast'), 'abcdefghijklmnop1234');
});
