import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'perm-'));
process.env.SHORTEM_HOME = tmp;
const { syncPermissions, TOOLS_ALLOW } = await import('../server/guide_sync.js');

test('파일이 없으면 만들고, 회원 칸은 지키며, 깨진 파일은 덮지 않는다', () => {
  const f = path.join(tmp, '.claude', 'settings.json');
  assert.equal(syncPermissions(tmp), true);
  assert.deepEqual(JSON.parse(fs.readFileSync(f, 'utf8')).permissions.allow, TOOLS_ALLOW);
  fs.writeFileSync(f, JSON.stringify({ env: { A: '1' }, permissions: { allow: ['Read', 'WebFetch(domain:x.com)'], deny: ['Bash(rm:*)'] } }));
  syncPermissions(tmp);
  const j = JSON.parse(fs.readFileSync(f, 'utf8'));
  assert.equal(j.env.A, '1');
  assert.deepEqual(j.permissions.deny, ['Bash(rm:*)']);
  assert.ok(j.permissions.allow.includes('WebFetch(domain:x.com)') && j.permissions.allow.includes('PowerShell'));
  fs.writeFileSync(f, '{깨짐');
  assert.equal(syncPermissions(tmp), false);
  assert.equal(fs.readFileSync(f, 'utf8'), '{깨짐');
});
