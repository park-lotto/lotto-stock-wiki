// 한 편 끝까지(가짜 서버 + 시험 영상, 목소리 없음) — 노출 검사 · 완료 정리 · 감사 로그 · 제작 호출 0 · 임대 끊김 멈춤/재개
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs, withFake, synthVideo, SCRIPT_OK, allKeys, numberPaths } from './helpers.js';

freshDirs('flow');
process.env.SHORTEM_HB_MS = '150';
const fake = await withFake({ ttl: 60 });
const video = synthVideo();
const { make, settle, current } = await import('../server/runner.js');
const { shape, secretNumbers, FORBIDDEN_KEYS } = await import('../server/firewall.js');
const { readLicense } = await import('../server/license.js');
test.after(() => fake.close());

const ALLOWED_NUM = new Set(['progress.no', 'progress.total', 'progress.elapsed_sec', 'need.slots[].no', 'need.title_lines', 'need.scenes']);
let secret = new Set();
const responses = [];
async function call(args, waitMs = 600000) {
  const o = await make(args, undefined, { waitMs });
  const job = o.job_id ? current(o.job_id) : null;
  if (job && job.bundle) secret = secretNumbers(job.bundle.frame, job.bundle.rules);
  const s = shape(o, secret);
  responses.push(s);
  return s;
}

test('한 편 끝까지 + 응답 노출 0 + 완료 뒤 규격 삭제', { timeout: 600000 }, async () => {
  let r = await call({ step: 'setup', profile_id: 'cp_sseol01', source: { kind: 'local_video', path: video } });
  assert.equal(r.progress.name, '대본'); assert.equal(r.need.kind, 'script');
  assert.ok(r.data && r.data.notice, '외부 글은 data + 머리글');
  const id = r.job_id;
  // 반려 루프: 말투 섞임 → 방향 힌트만
  r = await call({ step: 'script', job_id: id, payload: { title: SCRIPT_OK.title, lines: [...SCRIPT_OK.lines.slice(0, 4), '모두가 놀랐습니다'] } });
  assert.equal(r.progress.status, 'need_input');
  assert.ok(r.hints.some(h => /5번 줄 말투를 반말로/.test(h)), JSON.stringify(r.hints));
  // 틀린 단계로 부르면 거절 + 안내
  r = await call({ step: 'review', job_id: id, payload: { ok: true } });
  assert.ok(r.hints.some(h => /step="script"/.test(h)));
  r = await call({ step: 'script', job_id: id, payload: SCRIPT_OK });
  assert.equal(r.progress.name, '장면 계획'); assert.equal(r.need.kind, 'plan_ok');
  assert.ok(r.need.scenes > 0);
  // 승인 전 음성 단계 진입 없음(TTS 0)
  assert.ok(!fs.existsSync(path.join(process.env.SHORTEM_WORK, 'jobs', id, 'voice')));
  r = await call({ step: 'plan', job_id: id, payload: { approve: true } });
  assert.equal(r.progress.name, '확인', JSON.stringify(r)); assert.equal(r.need.kind, 'review'); assert.equal(r.need.verdict, '통과');
  assert.ok(fs.existsSync(r.need.video));
  r = await call({ step: 'review', job_id: id, payload: { ok: true } });
  assert.equal(r.progress.name, '완료'); assert.equal(r.progress.status, 'done');
  await settle(id);

  // ① 응답 전부: 금지 키 0 · 허용 경로 밖 숫자 0 · 규격 숫자 0
  for (const s of responses) {
    const keys = allKeys(s);
    for (const k of FORBIDDEN_KEYS) assert.ok(!keys.has(k), `응답에 금지 키 ${k}`);
    for (const p of numberPaths(s)) assert.ok(ALLOWED_NUM.has(p), `허용 밖 숫자 ${p}`);
    const txt = JSON.stringify({ ...s, data: undefined });
    for (const n of [1462, 1006, 93.2, -7.4, 6.8, 2.18]) assert.ok(!txt.includes(String(n)), `규격 숫자 ${n} 노출`);
  }
  // 음성 대조(이 검사가 실제로 잡는지): 가르기 전 state 에는 frame 이 있었다 → 검사 함수는 잡는다
  assert.ok(allKeys({ bundle: { frame: {} } }).has('frame'));

  // ② 완료 뒤 state.json: 규격·자산표·계획 수치 없음
  const st = JSON.parse(fs.readFileSync(path.join(process.env.SHORTEM_WORK, 'jobs', id, 'state.json'), 'utf8'));
  const sk = allKeys(st);
  for (const k of ['frame', 'rules', 'bundle', 'options', 'assets', 'plan', 'tl', 'render']) assert.ok(!sk.has(k), `완료 state 에 ${k}`);
  assert.ok(st.final && fs.existsSync(st.final));
  assert.ok(!fs.existsSync(path.join(process.env.SHORTEM_WORK, 'jobs', id, 'render')), '렌더 임시(틀 그림·필터 그래프) 삭제');

  // ③ 감사 로그: 키·URL·좌표 0
  const log = fs.readFileSync(path.join(process.env.SHORTEM_HOME, 'audit.jsonl'), 'utf8');
  assert.ok(!log.includes(readLicense()));
  assert.ok(!/https?:\/\//.test(log));
  for (const n of ['1462', '"x":', '"y":', 'filter_complex', 'overlay=']) assert.ok(!log.includes(n), `감사 로그에 ${n}`);

  // ④ 서버 호출은 license·lease·assets·blob 뿐(제작 호출 0)
  const routes = new Set(fake.state.log.map(l => l.route.replace(/\/blob\/.*/, '/blob/*').replace(/\/pack\/.*/, '/pack/*')));
  for (const r2 of routes) assert.ok(['/api/claude/license', '/api/claude/lease', '/api/claude/assets', '/api/claude/blob/*', '/api/claude/pack/*', '/__test/force_release'].includes(r2), `제작 외 호출 ${r2}`);
  assert.ok(!fs.existsSync(path.join(process.env.SHORTEM_WORK, 'out', 'FAILED.json')));
});

test('임대 끊김: 렌더 중 강제 해제 → 그 단계까지만 하고 멈춤 → resume 으로 재개', { timeout: 600000 }, async () => {
  let r = await call({ step: 'setup', profile_id: 'cp_item01', source: { kind: 'local_video', path: video } });
  const id = r.job_id;
  r = await call({ step: 'script', job_id: id, payload: SCRIPT_OK });
  assert.equal(r.need.kind, 'plan_ok');
  r = await call({ step: 'plan', job_id: id, payload: { approve: true } }, 0);   // 기다리지 않고 바로
  await new Promise(res => setTimeout(res, 300));
  await fetch(fake.url + '/__test/force_release');
  await settle(id);
  const j = current(id);
  assert.equal(j.status, 'failed', JSON.stringify(j.fail));
  assert.match(j.fail.why, /임대/);
  assert.equal(j.fail.retry_ok, true);
  assert.ok(['render', 'check', 'voice'].includes(j.cur));
  r = await call({ step: 'resume', job_id: id });
  assert.equal(r.need && r.need.kind, 'review', JSON.stringify(r));
});

test('다른 기기 작업 중이면 시작 거절(busy_other_device)', { timeout: 120000 }, async () => {
  const r = await call({ step: 'setup', profile_id: 'cp_sseol01' }, 30000);   // 기기 A 가 임대를 쥔 채 소재 대기
  assert.equal(r.need.kind, 'source');
  process.env.SHORTEM_MACHINE_ID = 'other-machine';
  const { resetLicenseCache } = await import('../server/runner.js');
  resetLicenseCache();
  const r2 = await call({ step: 'setup', profile_id: 'cp_sseol01' }, 30000);
  delete process.env.SHORTEM_MACHINE_ID;
  assert.equal(r2.progress.status, 'failed');
  assert.match(r2.fail.why, /다른 기기/);
});
