import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

test('일레븐랩스 키는 sk_ 로 시작해야 저장되고, 틀린 꼴은 없는 키로 본다(11-03 키 ID 400)', async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'el-'));
  process.env.SHORTEM_HOME = home;
  const V = await import('../server/engine/voice.js?' + Date.now());
  const bad = V.saveKey('elevenlabs', 'abcdef0123456789abcdef0123456789');
  assert.equal(bad.ok, false);
  assert.match(bad.why, /sk_/);
  assert.equal(V.saveKey('elevenlabs', 'sk_' + 'a'.repeat(40)).ok, true);
  assert.equal(V.readKey('elevenlabs'), 'sk_' + 'a'.repeat(40));
  fs.writeFileSync(path.join(home, 'keys', 'elevenlabs'), 'abcdef0123456789abcdef0123456789');
  assert.equal(V.readKey('elevenlabs'), '');
  assert.ok(fs.existsSync(path.join(home, 'keys', 'elevenlabs')));     // 지우지 않는다
});
