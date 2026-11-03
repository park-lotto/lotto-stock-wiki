import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'vc-'));
process.env.SHORTEM_HOME = tmp;
process.env.SHORTEM_VCRT_FORCE = '1';
const { syncVcrt } = await import('../server/vcrt_sync.js');

test('없는 런타임만 채우고 이미 있는 파일은 건드리지 않는다', () => {
  const src = path.join(tmp, 'src'), dst = path.join(tmp, 'dst');
  fs.mkdirSync(src); fs.mkdirSync(dst);
  fs.writeFileSync(path.join(src, 'msvcp140.dll'), 'new');
  fs.writeFileSync(path.join(src, 'vcruntime140.dll'), 'new');
  fs.writeFileSync(path.join(dst, 'vcruntime140.dll'), 'old');
  assert.equal(syncVcrt({ src, dst }).copied, 1);
  assert.equal(fs.readFileSync(path.join(dst, 'msvcp140.dll'), 'utf8'), 'new');
  assert.equal(fs.readFileSync(path.join(dst, 'vcruntime140.dll'), 'utf8'), 'old');
  assert.equal(syncVcrt({ src, dst }).copied, 0);
});
