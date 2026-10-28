// 작업 기록지(server/work_log.js, 관제 263/265) — 완성본이 작업 폴더로 새로 나올 때 ~/.shortem/작업기록.jsonl 에 1줄,
//   같은 완성본을 다시 불러도 두 번 안 쓰고, 다시 만들기(새 파일)면 새 줄. 칸은 엔진 tools/calcopy/work_log.py FIELDS 와 같다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { freshDirs } from './helpers.js';

freshDirs('work_log');
const { shapeSession } = await import('../server/make_flow.js');
const { dataDir } = await import('../server/engine_bridge.js');
const W = await import('../server/work_log.js');
const { homeDir } = await import('../server/paths.js');

test('기록지 꼴 — 엔진과 같은 칸·KST·멈춘 편은 이유 필수·모르는 칸 거절', () => {
  assert.deepEqual(W.FIELDS, ['date', 'bench_channel', 'our_channel', 'style', 'person', 'product', 'bench_url', 'origin_url',
    'final_path', 'final_md5', 'drive_path', 'duration', 'made_by', 'status', 'note']);
  assert.match(W.nowKst(Date.UTC(2026, 9, 25, 15, 30, 0)), /^2026-10-26T00:30:00\+09:00$/);
  assert.throws(() => W.appendWorkLog({ status: 'stopped' }), /이유/);
  assert.throws(() => W.appendWorkLog({ colour: 1 }), /모르는 칸/);
  assert.equal(W.workLogPath(), path.join(homeDir(), '작업기록.jsonl'));
});

test('완성본 → 기록지 1줄(md5 = 파일), 다시 불러도 그대로, 새 판이면 새 줄', async () => {
  const tdir = path.join(dataDir(), 'calcopy', 'topics', '9');
  fs.mkdirSync(tdir, { recursive: true });
  fs.writeFileSync(path.join(tdir, 'final.mp4'), 'first');
  const S = { sid: 'abcdef012399', state: 'final_review', topic_id: 9, preset_id: 'p_kitchit', topic: { name: '박세리 선크림' } };
  const done = shapeSession(S);
  assert.equal(done.need, 'done');
  let rows = W.readWorkLog();
  assert.equal(rows.length, 1);
  const r = rows[0];
  assert.equal(r.final_path, done.video);
  assert.equal(r.final_md5, crypto.createHash('md5').update('first').digest('hex'));
  assert.equal(r.style, 'p_kitchit');
  assert.equal(r.status, 'delivered');
  assert.match(r.made_by, /^member:/);
  assert.match(r.date, /\+09:00$/);
  assert.ok(String(r.note).includes('박세리 선크림'));
  assert.equal(r.bench_channel, null);           // 모르는 칸은 null(벤치 이름은 회원 PC 에 없다)
  shapeSession(S);                                // 같은 완성본 다시 — 줄 안 늘어남
  assert.equal(W.readWorkLog().length, 1);
  await new Promise(res => setTimeout(res, 30));
  fs.writeFileSync(path.join(tdir, 'final.mp4'), 'second');   // 다시 만들기(restyle) = 새 파일
  shapeSession(S);
  rows = W.readWorkLog();
  assert.equal(rows.length, 2);
  assert.equal(rows[1].final_md5, crypto.createHash('md5').update('second').digest('hex'));
});
