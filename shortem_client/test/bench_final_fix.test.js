// 채널 벤치마킹 2판 최종 검토 고침(관제 319) — ① 실행 중 회원 Claude 요청(_runner)을 need:'ai' 로 알림(Ruling 16) ② keepMine 반쪽 백업
import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

const root = freshDirs('bench_final_fix');
const { shapeFlow } = await import('../server/flow_driver.js');
const { answer, pending } = await import('../server/engine_bridge.js');
const M = await import('../server/my_presets.js');
const AI = path.join(root, 'home', 'ai');

function runnerReq(id, madeAtSec) {
  const d = path.join(AI, '_runner', id);
  fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(d, 'request.json'), JSON.stringify({ id, tag: 'bench_ocr', tier: 'opus', prompt: '자막을 읽어라', parts: [], made_at: madeAtSec }));
  return d;
}

test('벤치 흐름 실행 중 그 실행기의 _runner 요청 → need:ai(review 때 문구 꼴) · 답하면 다시 wait', () => {
  const t0 = Date.now();
  const f = { sid: 'aaaaaaaaaaaa', bench: { name: 'n' }, status: 'execute', busy: true, runAt: t0, message: '벤치 뜯기 중' };
  assert.equal(shapeFlow(f).need, 'wait', '요청이 없으면 그대로 wait');
  const id = '20261104-120000-bench_ocr-abcdef';
  runnerReq(id, t0 / 1000 + 1);
  const s = shapeFlow(f);
  assert.equal(s.need, 'ai');
  assert.match(s.next, /shortem_ai\(action="list"\)/);
  assert.match(s.next, /shortem_benchmark\(step="wait", sid="aaaaaaaaaaaa"\)/);
  assert.deepEqual(s.hints, ['판정 요청입니다 — 고객에게 묻지 말고 바로 답하세요']);
  assert.ok(pending().some(p => p.id === id), 'shortem_ai list 가 그 요청을 본다');
  assert.equal(answer(id, { items: ['첫 줄'] }).ok, true);
  assert.equal(shapeFlow(f).need, 'wait', '답한 뒤에는 다시 기다리기');
  fs.rmSync(path.join(AI, '_runner'), { recursive: true, force: true });
});

test('지난 실행의 찌꺼기 _runner 요청·벤치 아닌 제작 흐름·실행기 안 도는 흐름은 need:ai 로 바뀌지 않는다', () => {
  const t0 = Date.now();
  runnerReq('20261104-110000-bench_ocr-000001', t0 / 1000 - 600);          // 이 실행 전에 만든 요청(실행기가 죽어 done 없음)
  const bench = { sid: 'bbbbbbbbbbbb', bench: { name: 'n' }, status: 'execute', busy: true, runAt: t0, message: 'm' };
  assert.equal(shapeFlow(bench).need, 'wait');
  runnerReq('20261104-120001-score-000002', t0 / 1000 + 1);
  const make = { sid: 'cccccccccccc', status: 'execute', busy: true, runAt: t0, message: 'm', preset: 'p_x' };
  assert.deepEqual(shapeFlow(make), { sid: 'cccccccccccc', message: 'm', need: 'wait', next: 'shortem_make(step="wait", sid="cccccccccccc")',
    hints: ['만드는 중입니다 — 같은 wait 를 다시 부르면 이어서 기다립니다. 셸·sleep 으로 기다리지 마세요'] }, '기존 제작 흐름 응답은 그대로');
  assert.equal(shapeFlow({ ...bench, busy: false }).need, 'wait', '실행기가 안 돌면(다시 켬) 찌꺼기를 이 흐름 것으로 보지 않는다');
  fs.rmSync(path.join(AI, '_runner'), { recursive: true, force: true });
});

function mine(slug, val) {
  const src = path.join(root, 'src_' + slug);
  fs.mkdirSync(path.join(src, 'channel', slug, 'preset', '틀'), { recursive: true });
  fs.writeFileSync(path.join(src, 'channel', slug, 'preset', '틀', 'frame.json'), JSON.stringify(val));
  fs.writeFileSync(path.join(src, 'channel', slug, 'preset', '틀', 'big.bin'), 'x'.repeat(1000));
  return M.addMine(src, { slug, name: '원래 ' + slug, presets: [{ style: '틀', sources: ['a'] }] }, '')[0];
}

test('keepMine: 지난번 복사가 중간에 끊긴 반쪽 _keep(표식 없음)·남은 .tmp 는 이미 둔 것으로 보지 않고 다시 둔다 → dropMine 이 원본을 되살린다', () => {
  const o = mine('my_half', '원래');
  const kd = path.join(M.myRoot(), '_keep', 'my_half');
  fs.mkdirSync(path.join(kd, 'files', 'preset'), { recursive: true });          // 반쪽: list.json 없음·파일 일부만
  fs.mkdirSync(path.join(M.myRoot(), '_keep', 'my_half.tmp', 'files'), { recursive: true });
  assert.equal(M.keepMine('my_half'), true, '반쪽은 다시 둔다');
  assert.ok(fs.existsSync(path.join(kd, 'list.json')));
  assert.equal(fs.readFileSync(path.join(kd, 'files', 'preset', '틀', 'big.bin'), 'utf8').length, 1000);
  assert.equal(fs.existsSync(path.join(M.myRoot(), '_keep', 'my_half.tmp')), false);
  assert.equal(M.keepMine('my_half'), false, '완성된 벌은 덮지 않는다');
  mine('my_half', '시험');                                                   // 임시본이 원래 것을 덮는다
  M.dropMine('my_half');
  assert.equal(fs.readFileSync(path.join(M.myRoot(), 'my_half', 'preset', '틀', 'frame.json'), 'utf8'), '"원래"');
  assert.deepEqual(M.listMine().filter(p => p.slug === 'my_half').map(p => p.id), [o.id]);
});

test('keepMine: 복사 도중 실패하면 _keep 자리는 비어 있다(반쪽이 완성본 자리에 남지 않는다)', () => {
  mine('my_fail', '원래');
  const keep = fs.cpSync;
  fs.cpSync = (a, b, o) => { keep(a, b, o); throw Object.assign(new Error('디스크 가득'), { code: 'ENOSPC' }); };
  try { assert.throws(() => M.keepMine('my_fail'), /디스크 가득/); } finally { fs.cpSync = keep; }
  assert.equal(fs.existsSync(path.join(M.myRoot(), '_keep', 'my_fail')), false);
  assert.ok(!M.keptSlugs().includes('my_fail'));
  assert.equal(M.keepMine('my_fail'), true, '다음 번에는 다시 둔다');
});
