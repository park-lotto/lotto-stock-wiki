import test from 'node:test';
import assert from 'node:assert/strict';
import { missingLogins } from '../server/logins.js';

test('틱톡만 빠지면 막지 않고 안내만', () => {
  const r = missingLogins({ youtube: true, instagram: true, tiktok: false });
  assert.deepEqual(r.required, []);
  assert.deepEqual(r.optional.map(([k]) => k), ['tiktok']);
});

test('유튜브·인스타가 빠지면 그대로 막는다', () => {
  const r = missingLogins({ tiktok: true });
  assert.deepEqual(r.required.map(([k]) => k).sort(), ['instagram', 'youtube']);
});
