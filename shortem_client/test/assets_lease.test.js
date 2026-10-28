// 자산 캐시(내용주소·영수증·sha 대조·30일·LRU·회수 삭제) + 임대(두 기기 409·하트비트 lease_lost·3회 실패)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs, withFake } from './helpers.js';

freshDirs('assets');
const fake = await withFake({ ttl: 2 });
const { fetchJobAssets, gcCache, clearCache, cachePath } = await import('../server/assets.js');
const { Lease } = await import('../server/lease.js');
const { api } = await import('../server/api.js');
test.after(() => fake.close());

const DEV_A = 'machine-A', DEV_B = 'machine-B';
const asDev = id => { process.env.SHORTEM_MACHINE_ID = id; };

test('자산: 참조분만 받고 내용주소로 캐시 · 영수증 · 두 번째는 캐시 적중', async () => {
  asDev(DEV_A);
  await api.license();
  const L = new Lease('j_assets01', { hbMs: 100000 });
  await L.acquire();
  const r = await fetchJobAssets({ profileId: 'cp_sseol01', jobId: 'j_assets01', leaseId: L.id });
  assert.ok(r.bundle.frame && r.bundle.rules && r.bundle.options);
  const ids = Object.keys(r.table);
  assert.deepEqual(ids.filter(i => i.startsWith('font:')).sort(), ['font:CcSpoqaHanSansNeo-Bold', 'font:SBAggroB', 'font:TmonMonsori'], '틀이 참조하는 글꼴 3개만');
  const names = fs.readdirSync(path.join(process.env.SHORTEM_HOME, 'cache'));
  assert.ok(names.every(n => /^[0-9a-f]{64}$/.test(n)), '파일명 = sha256(프리셋·글꼴 이름 없음)');
  assert.equal(fs.readdirSync(path.join(process.env.SHORTEM_HOME, 'receipts')).length, names.length);
  const r2 = await fetchJobAssets({ profileId: 'cp_sseol01', jobId: 'j_assets01', leaseId: L.id });
  assert.equal(r2.stats.hits, r2.stats.count);
  // 캐시 파일을 바꿔치기하면 다시 받는다(sha 대조)
  const one = Object.values(r.table)[0];
  fs.writeFileSync(cachePath(one.sha256), 'tampered');
  const r3 = await fetchJobAssets({ profileId: 'cp_sseol01', jobId: 'j_assets01', leaseId: L.id });
  assert.equal(r3.stats.hits, r3.stats.count - 1);
  assert.notEqual(fs.readFileSync(cachePath(one.sha256), 'utf8'), 'tampered');
  await L.release();
});

test('자산: 30일 미사용 삭제 · 총량 넘으면 오래된 것부터', () => {
  const dir = path.join(process.env.SHORTEM_HOME, 'cache');
  const before = fs.readdirSync(dir).length;
  const now = Date.now();
  assert.equal(gcCache(now + 31 * 86400000).removed, before, '31일 뒤면 전부 삭제');
  fs.mkdirSync(dir, { recursive: true });
  for (let i = 0; i < 3; i++) {
    const sha = String(i).repeat(64);
    fs.writeFileSync(path.join(dir, sha), Buffer.alloc(1000));
    fs.mkdirSync(path.join(process.env.SHORTEM_HOME, 'receipts'), { recursive: true });
    fs.writeFileSync(path.join(process.env.SHORTEM_HOME, 'receipts', sha + '.json'), JSON.stringify({ sha256: sha, last_used: now - (3 - i) * 1000 }));
  }
  const g = gcCache(now, 2000);
  assert.equal(g.removed, 1);
  assert.ok(!fs.existsSync(path.join(dir, '0'.repeat(64))), '가장 오래 안 쓴 것이 지워짐');
  clearCache('revoked');
  assert.ok(!fs.existsSync(dir), '회수면 캐시 통째로 삭제');
});

test('임대: 두 번째 기기는 409 busy_other_device · 같은 기기 재취득은 같은 lease', async () => {
  asDev(DEV_A); await api.license();
  asDev(DEV_B); await api.license();
  asDev(DEV_A);
  const A = new Lease('j_two01', { hbMs: 100000 });
  const a1 = await A.acquire();
  const a2 = await A.acquire();
  assert.equal(a1.lease_id, a2.lease_id, '멱등');
  asDev(DEV_B);
  const B = new Lease('j_two02', { hbMs: 100000 });
  await assert.rejects(() => B.acquire(), e => e.status === 409 && e.code === 'busy_other_device' && /다른 기기/.test(e.msg));
  asDev(DEV_A);
  await A.release();
  asDev(DEV_B);
  await B.acquire();
  assert.ok(B.active, '앞 기기가 반납하면 둘째 기기 가능');
  await B.release();
});

test('임대: 강제 해제 → 하트비트 409 lease_lost · 네트워크 3회 실패 → lost', async () => {
  asDev(DEV_A);
  const L = new Lease('j_hb01', { hbMs: 100000 });
  await L.acquire();
  assert.equal(await L.heartbeat(), true);
  await fetch(fake.url + '/__test/force_release');
  assert.equal(await L.heartbeat(), false);
  assert.equal(L.lost, true); assert.equal(L.lostReason, 'lease_lost');
  const M = new Lease('j_hb02', { hbMs: 100000 });
  await M.acquire();
  const base = process.env.SHORTEM_BASE;
  process.env.SHORTEM_BASE = 'http://127.0.0.1:9';   // 아무도 안 듣는 곳
  for (let i = 0; i < 3; i++) await M.heartbeat();
  process.env.SHORTEM_BASE = base;
  assert.equal(M.lost, true); assert.equal(M.lostReason, 'heartbeat_fail');
  await M.release();
});

test('라이선스: 셋째 기기는 device_limit · 위조 키는 bad_key', async () => {
  asDev('machine-C');
  await assert.rejects(() => api.license(), e => e.code === 'device_limit');
  const k = process.env.SHORTEM_LICENSE;
  process.env.SHORTEM_LICENSE = k.slice(0, -1) + (k.endsWith('0') ? '1' : '0');
  asDev(DEV_A);
  await assert.rejects(() => api.license(), e => e.code === 'bad_key');
  process.env.SHORTEM_LICENSE = k;
});
