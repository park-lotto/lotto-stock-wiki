import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';

test('runOps 는 close 만 기다리지 않는다', () => {
  const s = fs.readFileSync(new URL('../server/engine_bridge.js', import.meta.url), 'utf8');
  assert.match(s, /proc\.on\('exit', \(\) => setTimeout\(finish, EXIT_GRACE_MS\)/);
});
