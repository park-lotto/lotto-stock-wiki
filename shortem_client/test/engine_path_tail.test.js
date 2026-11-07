import { test } from 'node:test';
import assert from 'node:assert/strict';
import { systemPathTail } from '../server/engine_bridge.js';
test('맥 엔진 PATH 에 기본 명령 폴더가 들어간다(11-05 박상혁 #7942)', () => {
  assert.match(systemPathTail('darwin'), /\/usr\/bin/);
  assert.match(systemPathTail('darwin'), /(^|:)\/bin(:|$)/);
  assert.match(systemPathTail('win32', 'C:/Windows'), /System32$/);
  assert.equal(systemPathTail('win32', ''), '');
});
