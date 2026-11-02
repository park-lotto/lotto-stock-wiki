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

test('고급반은 빌려 돌리고, 끝나면 푼 파일만 지우고 내 프리셋으로 저장한다', async () => {
  const o = await B.benchStart({ channel: URL_CH, name: '내 틀', n: 2 });
  assert.equal(o.need, 'done', JSON.stringify(o));
  assert.equal(o.info.failed_videos, 1);
  assert.match(o.next, /preset_name="내 틀"/);
  for (let i = 0; i < 50 && (leftovers() || fs.existsSync(path.join(E, '.bench_rented.json'))); i++) await new Promise(r => setTimeout(r, 100));
  assert.equal(leftovers(), false, '빌린 엔진 파일이 남았다');
  assert.equal(fs.existsSync(path.join(E, '.bench_rented.json')), false);
  assert.equal(fs.readFileSync(path.join(E, 'tools', 'calcopy', 'make.py'), 'utf8'), MAKE, '이미 있던 엔진 파일을 덮으면 안 된다');
  const [mine] = M.listMine();
  assert.equal(mine.name, '내 틀');
  assert.equal(mine.channel, URL_CH);
  assert.equal(readSettings().current, mine.id);
  assert.match(mine.id, /^p_[0-9a-f]{10}$/);
  const v = M.withMine({ presets: [{ id: 'p_0000000000', name: '서버판' }], entitled_presets: ['p_0000000000'] });
  assert.deepEqual(v.presets.map(p => p.name), ['서버판', '내 틀']);
  assert.ok(v.entitled_presets.includes(mine.id));
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
  assert.match((await B.benchWait('rabcdef')).hints[0], /기다릴 벤치마킹이 없습니다/);
  assert.match((await B.benchStart({ channel: 'https://tiktok.com/@x', name: 'x' })).hints[0], /채널 주소는/);
  assert.match((await B.benchStart({ name: 'x' })).hints[0], /채널 주소/);
  assert.match((await B.benchStart({ videos: ['https://evil.example/a'], name: 'x' })).hints[0], /영상 주소는/);
});
