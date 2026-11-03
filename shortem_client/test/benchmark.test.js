// 고급반 벤치마킹(관제 304) — 기본반 거절 · 빌린 파일만 풀고 지우기 · 내 프리셋 저장 · 제작 길. 영상 재현은 tools/claude_portal/benchmark_check.py.
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs, withFake } from './helpers.js';
import { startFakeServer } from './fake_server.js';

const root = freshDirs('benchmark');
const E = path.join(root, 'engine');
fs.mkdirSync(path.join(E, 'tools', 'calcopy'), { recursive: true });
process.env.SHORTEM_ENGINE = E;
process.env.SHORTEM_WAIT_SEC = '20';

// 가짜 엔진 입구 — 진짜 bench_member 와 같은 꼴(마지막 줄 JSON·결과 폴더)
const BENCH = `import argparse, json
from pathlib import Path
ap = argparse.ArgumentParser()
for k in ("--out", "--name", "--n", "--channel"):
    ap.add_argument(k, default="")
ap.add_argument("--video", action="append", default=[])
a = ap.parse_args()
d = Path(a.out) / "channel" / "my_abc" / "preset" / "틀"
d.mkdir(parents=True)
(d / "manifest.json").write_text('{"slug":"my_abc"}', encoding="utf-8")
(d / "frame.json").write_text("{}", encoding="utf-8")
print(json.dumps({"ok": True, "name": a.name, "slug": "my_abc", "presets": [{"style": "틀", "sources": ["v1", "v2"]}], "failed": [{"video": "v3", "why": "x"}]}, ensure_ascii=False))
`;
const MAKE = `import json, sys
print(json.dumps({"sid": "abcdefabcdef", "state": "candidates", "candidates": [{"n": 1, "title": " ".join(sys.argv[1:]), "total": 1, "line": "", "scores": {}, "made": 0}]}, ensure_ascii=False))
`;
function zipOf(files) {
  const py = 'import io,json,sys,zipfile\nb=io.BytesIO()\nz=zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED)\nfor k,v in json.loads(sys.stdin.buffer.read().decode("utf-8")).items(): z.writestr(k,v)\nz.close()\nsys.stdout.buffer.write(b.getvalue())';
  return execFileSync('py', ['-c', py], { input: JSON.stringify(files) });
}
const ZIP = zipOf({ 'tools/calcopy/engine/bench_member.py': BENCH, 'tools/calcopy/engine/analyze.py': 'x=1', 'tools/calcopy/make.py': 'DO_NOT_COPY=1' });
fs.writeFileSync(path.join(E, 'tools', 'calcopy', 'make.py'), MAKE);

const fake = await withFake({ benchmark: { tier: 'advanced', zip: ZIP } });
const low = await startFakeServer({ benchmark: { tier: 'basic', zip: ZIP } });
test.after(async () => { await fake.close(); await low.close(); });

const B = await import('../server/benchmark.js');
const P = await import('../server/preset_rent.js');
const M = await import('../server/my_presets.js');
const F = await import('../server/make_flow.js');
const { readSettings, useCatalog } = await import('../server/local_settings.js');
useCatalog({ default_pack: {}, preset_defaults: {} });
const URL_CH = 'https://www.youtube.com/@somechannel';
const { api } = await import('../server/api.js');
await api.license();                                     // 기기 등록(회원은 shortem_setup 때)
const leftovers = () => fs.existsSync(path.join(E, 'tools', 'calcopy', 'engine'));

test('기본반은 쉬운 문구로 멈추고 아무것도 받지 않는다', async () => {
  const keep = process.env.SHORTEM_BASE;
  process.env.SHORTEM_BASE = low.url;
  try {
    await api.license();
    const o = await B.benchStart({ channel: URL_CH, name: '내 틀' });
    assert.equal(o.fail.why, '채널 벤치마킹은 고급반에서 제공돼요');
    assert.match(o.fail.fix, /고급반/);
    assert.equal(o.fail.retry_ok, false);
    assert.equal(leftovers(), false);
  } finally { process.env.SHORTEM_BASE = keep; }
});

// 2판(관제 319): 띄우기 = 서버 지시서 고리. 가짜 지시서: bench_start → 회원 과제(시험 편) → 답 → 완성(preset·zip)
const BSID = 'b0b0b0b0b0b0';
const ESID = 'e0e0e0e0e0e0';
const steps = [];
function benchServer() {
  steps.length = 0;
  fake.state.stepHandler = body => {
    steps.push(body);
    if (body.step === 'bench_start') return { code: 200, json: { ok: true, sid: BSID, status: 'review', message: '시험 영상 만들기 중', stage: { no: 5, total: 11, text: '시험 영상 만들기' }, next_payload: 'b1',
      review: [{ id: 'bm_trial', model: 'opus', ask: '만들기: shortem_make(step="start", preset="{preset_id}")', need: ['work_dir', 'ok'],
        meta: { kind: 'member_task', tool: 'shortem_make', preset: { slug: 'my_abc', style: '틀', dir: 'channel/my_abc/preset/틀' }, source: { channel: URL_CH }, try: 0 } }] } };
    return { code: 200, json: { ok: true, sid: BSID, status: 'done', message: '완성', stage: { no: 11, total: 11, text: '완성' }, next_payload: 'b2',
      preset: { slug: 'my_abc', style: '틀', name: '내 틀', zip: 'out/my_abc_틀.zip', other_styles: [] } } };
  };
}

test('고급반은 빌려 지시서 고리로 돌리고, 시험 편 과제·완성 뒤 푼 파일만 지우고 내 프리셋으로 저장한다', async () => {
  const { flowRoot } = await import('../server/flow_driver.js');
  const { pending, answer, dataDir } = await import('../server/engine_bridge.js');
  const W = path.join(flowRoot(), BSID, 'job');
  const pd = path.join(W, 'channel', 'my_abc', 'preset', '틀');
  fs.mkdirSync(pd, { recursive: true });
  fs.writeFileSync(path.join(pd, 'manifest.json'), '{"slug":"my_abc"}');
  fs.writeFileSync(path.join(pd, 'frame.json'), '{}');
  fs.mkdirSync(path.join(W, 'out'), { recursive: true });
  fs.writeFileSync(path.join(W, 'out', 'my_abc_틀.zip'), 'zip');
  const mk = path.join(dataDir(), 'calcopy', 'make');
  fs.mkdirSync(path.join(mk, ESID, 'work', '3', '제작'), { recursive: true });
  fs.writeFileSync(path.join(mk, ESID, 'work', '3', '제작', 'final.mp4'), 'v');
  fs.writeFileSync(path.join(mk, `${ESID}.json`), JSON.stringify({ sid: ESID, topic_id: 3 }));
  benchServer();
  let o = await B.benchStart({ channel: URL_CH, name: '내 틀', n: 2 });
  assert.equal(steps[0].step, 'bench_start');
  assert.equal(steps[0].source.url, URL_CH);
  assert.equal(steps[0].n, 2);
  assert.equal(o.need, 'ai', JSON.stringify(o));
  assert.match(o.next, /shortem_benchmark\(step="wait", sid="b0b0b0b0b0b0"\)/);
  assert.ok(leftovers(), '흐름 동안은 빌린 엔진 파일을 둔다');
  const tmp = M.listMine().filter(p => p.slug === 'my_abc');
  assert.equal(tmp.length, 1);
  const q = pending().find(x => x.req.tag === 'bm_trial');
  assert.ok(q.req.prompt.includes(`preset="${tmp[0].id}"`));
  assert.equal(answer(q.id, { work_dir: ESID, ok: true }).ok, true);
  o = await B.benchWait(BSID);
  assert.equal(o.need, 'done', JSON.stringify(o));
  assert.deepEqual(steps[1].replies, { bm_trial: { work_dir: `trial/t0_${ESID}`, ok: true } });
  assert.match(o.next, /preset_name="내 틀"/);
  assert.equal(fs.readFileSync(path.join(process.env.SHORTEM_HOME, '내 프리셋', 'my_abc', 'my_abc_틀.zip'), 'utf8'), 'zip');
  for (let i = 0; i < 50 && (leftovers() || fs.existsSync(path.join(E, '.bench_rented.json'))); i++) await new Promise(r => setTimeout(r, 100));
  assert.equal(leftovers(), false, '빌린 엔진 파일이 남았다');
  assert.equal(fs.existsSync(path.join(E, '.bench_rented.json')), false);
  assert.equal(fs.readFileSync(path.join(E, 'tools', 'calcopy', 'make.py'), 'utf8'), MAKE, '이미 있던 엔진 파일을 덮으면 안 된다');
  assert.equal(M.listMine().filter(p => p.slug === 'my_abc').length, 1, '임시 시험본은 정식본으로 갈아 끼워진다(한 벌)');
  const [mine] = M.listMine();
  assert.equal(mine.name, '내 틀');
  assert.equal(mine.channel, URL_CH);
  assert.equal(readSettings().current, mine.id);
  assert.match(mine.id, /^p_[0-9a-f]{10}$/);
  assert.equal(fs.existsSync(path.join(M.myRoot(), '_keep')), false, '둔 벌이 남지 않는다');
  assert.equal(fs.existsSync(path.join(W, 'trial')), false, '시험 편 폴더는 끝 정리 때 지운다');
  assert.equal(fs.existsSync(path.join(mk, ESID, 'work', '3', '제작')), false, '엔진 쪽 원본은 옮겨져 없다(두 벌 아님)');
  const v = M.withMine({ presets: [{ id: 'p_0000000000', name: '서버판' }], entitled_presets: ['p_0000000000'] });
  assert.deepEqual(v.presets.map(p => p.name), ['서버판', '내 틀']);
  assert.ok(v.entitled_presets.includes(mine.id));
});

// 다시 켬 시험 — 앞 프로그램이 디스크에 남긴 흐름 상태만 있고 메모리(흐름 목록·끝 고리·빌림)는 비어 있다
function origAndTrial(slug, origName, trialName) {
  const src = path.join(root, 'src_' + slug);
  fs.mkdirSync(path.join(src, 'channel', slug, 'preset', '틀'), { recursive: true });
  fs.writeFileSync(path.join(src, 'channel', slug, 'preset', '틀', 'frame.json'), '"원래"');
  const [orig] = M.addMine(src, { slug, name: origName, presets: [{ style: '틀', sources: ['a'] }] }, '');
  assert.equal(M.keepMine(slug), true);
  fs.writeFileSync(path.join(src, 'channel', slug, 'preset', '틀', 'frame.json'), '"시험"');
  M.addMine(src, { slug, name: trialName, presets: [{ style: '틀', sources: [] }] }, '');
  return orig;
}
function diskFlow(sid, f) {
  const { flowRoot } = F_;
  fs.mkdirSync(path.join(flowRoot(), sid, 'job'), { recursive: true });
  fs.writeFileSync(path.join(flowRoot(), sid, 'flow.json'), JSON.stringify({ sid, preset: 'bench', created: Date.now(), ...f }));
}
const F_ = await import('../server/flow_driver.js');

test('다시 켰을 때 끝난 흐름·주인 없는 둔 벌 → 원래 내 프리셋을 되살리고 임시본을 지운다', async () => {
  const o1 = origAndTrial('my_r', '원래 r', '원래 r 시험');
  const o2 = origAndTrial('my_o', '원래 o', '원래 o 시험');         // 흐름 기록도 없이 둔 벌만 남은 경우
  const RS = 'c1c1c1c1c1c1';
  diskFlow(RS, { status: 'stop', fail: { why: '멈춤', retry_ok: false, server_stop: true }, bench: { name: '원래 r', channel: URL_CH, trial_slug: 'my_r' } });
  fs.mkdirSync(path.join(F_.flowRoot(), RS, 'job', 'trial', 't0_x'), { recursive: true });
  assert.equal(B.benchNow(), null, '메모리는 비어 있다(다시 켬)');
  await B.recoverBench();
  for (const [slug, o] of [['my_r', o1], ['my_o', o2]]) {
    assert.deepEqual(M.listMine().filter(p => p.slug === slug).map(p => [p.id, p.name]), [[o.id, o.name]], slug);
    assert.equal(fs.readFileSync(path.join(M.myRoot(), slug, 'preset', '틀', 'frame.json'), 'utf8'), '"원래"');
    assert.equal(fs.existsSync(path.join(M.myRoot(), '_keep', slug)), false);
  }
  assert.equal(M.listMine().some(p => /시험$/.test(p.name)), false, '임시본이 목록에 남지 않는다');
  assert.ok(JSON.parse(fs.readFileSync(path.join(F_.flowRoot(), RS, 'flow.json'), 'utf8')).bench.ended);
  assert.equal(fs.existsSync(path.join(F_.flowRoot(), RS, 'job', 'trial')), false);
  assert.equal(B.benchNow(), null);
});

test('다시 켰을 때 살아 있는 흐름은 이어 가고, 완성되면 정식 내 프리셋으로 한 번 올린다', async () => {
  const { aiRootDir, dataDir } = await import('../server/engine_bridge.js');
  const orig = origAndTrial('my_s', '복귀 틀', '복귀 틀 시험');
  const RS = 'c2c2c2c2c2c2';
  const E2 = 'e2e2e2e2e2e2';
  const W = path.join(F_.flowRoot(), RS, 'job');
  fs.mkdirSync(path.join(W, 'channel', 'my_s', 'preset', '틀'), { recursive: true });
  fs.writeFileSync(path.join(W, 'channel', 'my_s', 'preset', '틀', 'frame.json'), '"정식"');
  fs.mkdirSync(path.join(W, 'out'), { recursive: true });
  fs.writeFileSync(path.join(W, 'out', 'my_s_틀.zip'), 'zip2');
  const mk = path.join(dataDir(), 'calcopy', 'make');
  fs.mkdirSync(path.join(mk, E2, 'work', '5', '제작'), { recursive: true });
  fs.writeFileSync(path.join(mk, E2, 'work', '5', '제작', 'final.mp4'), 'v');
  fs.writeFileSync(path.join(mk, `${E2}.json`), JSON.stringify({ sid: E2, topic_id: 5 }));
  const q = path.join(aiRootDir(), 'flow_' + RS, 'req1');
  fs.mkdirSync(q, { recursive: true });
  fs.writeFileSync(path.join(q, 'answer.json'), JSON.stringify({ work_dir: E2, ok: true }));   // 꺼져 있는 동안 회원 Claude 가 답했다
  diskFlow(RS, { status: 'review', payload: 'r1', bench: { name: '복귀 틀', channel: URL_CH, trial_slug: 'my_s' },
    asks: [{ rid: 'bm_trial', dir: q, need: ['work_dir', 'ok'], task: { kind: 'member_task', try: 0, slug: 'my_s', preset_id: orig.id } }] });
  steps.length = 0;
  fake.state.stepHandler = body => { steps.push(body);
    return { code: 200, json: { ok: true, sid: RS, status: 'done', message: '완성', next_payload: 'r2', preset: { slug: 'my_s', style: '틀', name: '복귀 틀', zip: 'out/my_s_틀.zip', other_styles: [] } } }; };
  const r = await B.recoverBench();
  assert.equal(r.resumed, RS, '살아 있는 흐름은 지금 벤치마킹으로 다시 잡는다');
  assert.ok(fs.existsSync(path.join(M.myRoot(), '_keep', 'my_s')), '살아 있는 흐름의 둔 벌은 그대로(아직 끝나지 않음)');
  const o = await B.benchWait(RS);
  assert.equal(o.need, 'done', JSON.stringify(o));
  assert.deepEqual(steps.map(b => b.step), ['go']);
  assert.deepEqual(steps[0].replies, { bm_trial: { work_dir: `trial/t0_${E2}`, ok: true } });
  const mine = M.listMine().filter(p => p.slug === 'my_s');
  assert.deepEqual(mine.map(p => p.name), ['복귀 틀'], '정식본 한 벌');
  assert.equal(fs.readFileSync(path.join(M.myRoot(), 'my_s', 'preset', '틀', 'frame.json'), 'utf8'), '"정식"');
  assert.equal(fs.existsSync(path.join(M.myRoot(), '_keep', 'my_s')), false);
  assert.equal(fs.readFileSync(path.join(process.env.SHORTEM_HOME, '내 프리셋', 'my_s', 'my_s_틀.zip'), 'utf8'), 'zip2');
  assert.equal(readSettings().current, mine[0].id);
  assert.equal(fs.existsSync(path.join(W, 'trial')), false);
  assert.equal(B.benchNow(), null);
});

test('프로그램이 죽어 남은 파일은 다음에 켤 때 지운다 — 목록에 없는 파일은 안 지운다', () => {
  fs.mkdirSync(path.join(E, 'tools', 'calcopy', 'engine'), { recursive: true });
  fs.writeFileSync(path.join(E, 'tools', 'calcopy', 'engine', 'analyze.py'), 'x');
  fs.writeFileSync(path.join(E, '.bench_rented.json'), JSON.stringify(['tools/calcopy/engine/analyze.py']));
  assert.equal(B.sweepBench(E), true);
  assert.equal(fs.existsSync(path.join(E, 'tools', 'calcopy', 'engine', 'analyze.py')), false);
  assert.ok(fs.existsSync(path.join(E, 'tools', 'calcopy', 'make.py')));
});

test('묶음에 바깥 경로가 있으면 풀지 않는다', () => {
  assert.throws(() => B.unpackBench(zipOf({ '../evil.py': 'x' }), E), /바깥 경로/);
  assert.throws(() => B.unpackBench(zipOf({ 'server/x.py': 'x' }), E), /바깥 경로/);
});

test('내 프리셋은 서버를 안 부르고 엔진 길로 만든다 — 쓰는 동안만 channel 에 둔다', async () => {
  const [mine] = M.listMine();
  const r = await P.rentPreset({ engineRoot: E, presetId: mine.id });
  assert.equal(r.presetPath, `channel/my_abc/preset/틀`);
  assert.ok(fs.existsSync(path.join(E, 'channel', 'my_abc', 'preset', '틀', 'manifest.json')));
  await r.release();
  assert.equal(fs.existsSync(path.join(E, 'channel')), false);
  const o = await F.makeStep({ step: 'start', preset: mine.id });      // 영상 없이 = 벤치마킹한 채널에서 후보
  assert.equal(o.need, 'choose', JSON.stringify(o));
  assert.match(o.candidates[0].title, /--preset channel\/my_abc\/preset\/틀/);
  for (let i = 0; i < 50 && fs.existsSync(path.join(E, 'channel')); i++) await new Promise(r2 => setTimeout(r2, 100));
  assert.equal(fs.existsSync(path.join(E, 'channel')), false, '제작이 끝나면 내 프리셋 사본은 지운다');
  assert.match((await F.makeStep({ step: 'sources', preset: mine.id })).hints[0], /소재 창고가 없습니다/);
});

test('이어 부르기와 주소 검사', async () => {
  assert.match((await B.benchWait('aaaaaaaaaaaa')).hints[0], /기다릴 벤치마킹이 없습니다/);
  assert.match((await B.benchStart({ channel: 'https://tiktok.com/@x', name: 'x' })).hints[0], /채널 주소는/);
  assert.match((await B.benchStart({ name: 'x' })).hints[0], /채널 주소/);
  assert.match((await B.benchStart({ videos: ['https://evil.example/a'], name: 'x' })).hints[0], /영상 주소는/);
});
