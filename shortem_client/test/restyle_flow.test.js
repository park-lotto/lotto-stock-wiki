// 완성본 다시 만들기(restyle) — 렌더가 새 완성본을 썼으면 성공으로 답하고 완성본 폴더까지 바꾼다.
//   #749(강태경 글꼴)·#1553(정민혜 자막 위치): runner.log render ok·final.mp4 새 겉모습인데 '다시 만들지 못했습니다' —
//     실행기 render 가 출처 검사(jumps)로 ok:false(오류 문구 없음)를 줬고, restyle 은 처음 렌더 지시(원본 이름·글자 지우기·권고 넘기기)를 빼고 보냈다.
//   #1042(최일환): 안 끝난 편의 f.video 는 소재 주소 — 거기로 복사하다 ENOENT.
//   성공해도 완성본 폴더(작업 폴더/완성본) 복사(keepFinal)를 건너뛰어 회원 Claude 가 손으로 복사했다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { freshDirs } from './helpers.js';

freshDirs('restyle_flow');

// 가짜 실행기(엔진 자리는 처음 한 번 정해지므로 하나만) — 받은 지시를 남기고, FAKE_WRITE=1 이면 완성본을 새로 쓴 뒤 FAKE_RES 를 결과로
const eng = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'restyle-')), 'eng');
fs.mkdirSync(path.join(eng, 'tools', 'calcopy', 'hybrid'), { recursive: true });
for (const p of ['tools', 'tools/calcopy', 'tools/calcopy/hybrid']) fs.writeFileSync(path.join(eng, p, '__init__.py'), '');
fs.writeFileSync(path.join(eng, 'tools', 'calcopy', 'hybrid', 'runner_ops.py'), [
  'import json, os, sys, time',
  'from pathlib import Path',
  'W, do = Path(sys.argv[1]), json.load(open(sys.argv[2], encoding="utf-8"))',
  '(W.parent / "seen_do.json").write_text(json.dumps(do, ensure_ascii=False), encoding="utf-8")',
  'if os.environ.get("FAKE_WRITE") == "1":',
  '    time.sleep(0.05)',
  '    (W / do[0]["version"] / "render" / "final.mp4").write_text("new", encoding="utf-8")',
  'open(os.environ["SHORTEM_RESULT"], "w", encoding="utf-8").write(os.environ["FAKE_RES"])',
].join('\n'));
process.env.SHORTEM_ENGINE = eng;
process.env.SHORTEM_PYTHON = process.env.SHORTEM_PYTHON || execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c', 'import sys;print(sys.executable)']).toString().trim();
function fakeEngine(res, { write = true } = {}) {
  process.env.FAKE_RES = JSON.stringify(res);
  process.env.FAKE_WRITE = write ? '1' : '0';
}

const { flowRoot } = await import('../server/flow_driver.js');
const { makeStep } = await import('../server/make_flow.js');
const { workDir } = await import('../server/paths.js');

function flow(sid, extra) {   // 다 만든 편 — job/v1/render/final.mp4 = 옛 겉모습
  const fin = path.join(flowRoot(), sid, 'job', 'v1', 'render', 'final.mp4');
  fs.mkdirSync(path.dirname(fin), { recursive: true });
  fs.writeFileSync(fin, 'old');
  const past = new Date(Date.now() - 60000);
  fs.utimesSync(fin, past, past);
  fs.writeFileSync(path.join(flowRoot(), sid, 'flow.json'), JSON.stringify({ sid, status: 'done', video: fin, title: '제목', ...extra }));
  return fin;
}
const shelf = sid => path.join(workDir(), '완성본', `제목_${sid}.mp4`);
const seenDo = sid => JSON.parse(fs.readFileSync(path.join(flowRoot(), sid, 'seen_do.json'), 'utf8'))[0];

test('출처 검사(jumps)만 걸린 렌더는 성공 — 새 완성본을 완성본 폴더까지 바꾼다(#749·#1553)', async () => {
  fakeEngine({ restyle: { ok: false, jumps: ['컷 3 다른 재료 전환'] } });
  const sid = 'a1b2c3d4e5f6';
  flow(sid);
  const r = await makeStep({ step: 'restyle', sid });
  assert.equal(r.need, 'done', JSON.stringify(r));
  assert.equal(r.video, shelf(sid));
  assert.equal(fs.readFileSync(shelf(sid), 'utf8'), 'new', '회원이 보는 완성본이 새 겉모습');
});

test('처음 렌더 지시(원본 이름·글자 지우기·권고 넘기기)를 그대로 싣는다', async () => {
  fakeEngine({ restyle: { ok: true, jumps: [] } });
  const sid = 'b1b2c3d4e5f6';
  flow(sid, { renderDo: { id: 'r', cmd: 'render', version: 'v1', erase: true, waive: true, origin_names: ['orig.mp4'], other_faces: false } });
  const r = await makeStep({ step: 'restyle', sid });
  assert.equal(r.need, 'done', JSON.stringify(r));
  const d = seenDo(sid);
  assert.deepEqual([d.id, d.cmd, d.version, d.erase, d.waive, d.origin_names, d.other_faces], ['restyle', 'render', 'v1', true, true, ['orig.mp4'], false]);
});

test('안 끝난 편(f.video = 소재 주소)도 터지지 않고 완성본 폴더로 낸다(#1042)', async () => {
  fakeEngine({ restyle: { ok: true, jumps: [] } });
  const sid = 'c1b2c3d4e5f6';
  flow(sid, { status: 'error', video: 'https://www.youtube.com/shorts/abcdefghijk' });
  const r = await makeStep({ step: 'restyle', sid });
  assert.equal(r.need, 'done', JSON.stringify(r));
  assert.equal(fs.readFileSync(shelf(sid), 'utf8'), 'new');
});

test('오류·충돌·완성본을 안 쓴 렌더는 실패로 답한다', async () => {
  for (const [sid, res, write] of [['d1b2c3d4e5f6', { restyle: { ok: false, error: '관문 멈춤' } }, true],
    ['d2b2c3d4e5f6', { restyle: { ok: false, conflict: { cause: 'x' } } }, true],
    ['d3b2c3d4e5f6', { restyle: { ok: true } }, false]]) {
    fakeEngine(res, { write });
    flow(sid);
    const r = await makeStep({ step: 'restyle', sid });
    assert.ok(r.fail, `${sid} ${JSON.stringify(r)}`);
    assert.equal(fs.existsSync(shelf(sid)), false);
  }
});
