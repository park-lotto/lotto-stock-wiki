// 경로 감옥 · 응답 가르기 · 대본 린터 · 감사 로그 청소 — 렌더 없이 빠른 시험
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs, allKeys } from './helpers.js';

const root = freshDirs('unit');
const { jail, writeFileIn, JailError } = await import('../server/paths.js');
const { shape, secretNumbers, FORBIDDEN_KEYS, DATA_NOTICE, toToolResult } = await import('../server/firewall.js');
const { lintScript, rulesFrom, speechOf } = await import('../server/engine/script_lint.js');
const { audit } = await import('../server/audit.js');
const { normalizeFrame } = await import('../server/engine/frame.js');
const { chunkLine } = await import('../server/engine/plan.js');

test('경로 감옥: .. · 밖 절대경로 · 링크 폴더 거부, 안쪽은 허용', () => {
  const w = process.env.SHORTEM_WORK;
  assert.throws(() => jail(w, '../x'), JailError);
  assert.throws(() => jail(w, 'a/../../x'), JailError);
  assert.throws(() => jail(w, 'C:\\Windows\\x'), JailError);
  assert.throws(() => jail(w, '/etc/passwd'), JailError);
  assert.throws(() => writeFileIn(w, '..\\evil.txt', 'x'), JailError);
  const ok = jail(w, 'jobs/j_abc123/state.json');
  assert.ok(ok.startsWith(path.resolve(w)));
  // 링크(윈도 정션) 폴더 거부
  const outside = path.join(root, 'outside'); fs.mkdirSync(outside, { recursive: true });
  const link = path.join(w, 'link');
  try { fs.symlinkSync(outside, link, 'junction'); } catch { /* 권한 없으면 건너뜀 */ }
  if (fs.existsSync(link)) assert.throws(() => writeFileIn(w, 'link/x.txt', 'x'), JailError);
});

test('가르기: 금지 키(깊이 무관) 0 · 내부 경로 가림 · 규격 숫자 지움 · 줄 번호는 남김', () => {
  const secret = secretNumbers({ layers: [{ y: 1462, size: 66, letter_spacing: -7.4 }] }, { script: { line_max: 38 } });
  const job = path.join(process.env.SHORTEM_WORK, 'jobs', 'j_abc123', 'state.json');
  const out = path.join(process.env.SHORTEM_WORK, 'out', 'a.mp4');
  const raw = { job_id: 'j_abc123def', progress: { name: '대본', status: 'need_input' }, frame: { a: 1 }, rules: {}, bundle: {}, payload: {}, options: {},
    need: { kind: 'script', slots: [{ role: '훅', length: '짧게', threshold: 38 }], ask: '자막 y 1462 에 66 크기', url: 'http://x' },
    hints: ['3번 줄을 더 짧게', `기준 38자 넘음 ${job}`], fail: { where: '렌더', why: `파일 ${job}`, fix: `완성본 ${out}`, retry_ok: true, sha256: 'x' },
    data: { source_title: '외부 제목', rule_id: 'r1' } };
  const s = shape(raw, secret);
  const keys = allKeys(s);
  for (const k of FORBIDDEN_KEYS) assert.ok(!keys.has(k), `금지 키 ${k}`);
  const txt = JSON.stringify(s);
  const words = JSON.stringify({ need: s.need, hints: s.hints, why: s.fail.why });
  for (const n of ['1462', '66 ', '38', '-7.4']) assert.ok(!words.includes(n), `규격 숫자 ${n} 남음: ${words}`);
  assert.ok(txt.includes('3번 줄'));
  assert.ok(!txt.includes('state.json'), '내부 경로 가림');
  assert.ok(txt.includes('a.mp4'), '완성본 경로는 보임');
  assert.equal(s.data.notice, DATA_NOTICE);
  assert.deepEqual(s.steps, ['소재', '분석', '대본', '장면 계획', '음성', '렌더', '검사', '확인', '완료']);
  assert.equal(s.progress.no, 3); assert.equal(s.progress.total, 9);
  const r = toToolResult(s);
  assert.ok(r.content[0].text.startsWith(DATA_NOTICE));
});

test('대본 린터: 말투 섞임·긴 줄·근거 없는 숫자·제목 줄 수 → 방향 문장만(임계값 숫자 없음)', () => {
  const rules = rulesFrom({ script: { line_max: 38, title_line_max: 14, speech: 'banmal' } });
  const bad = lintScript({ title: '한 줄 제목', lines: ['이거 처음 보면 놀라요', '색깔 막대가 갑자기 움직였어 그리고 계속해서 끝도 없이 움직이고 또 움직이고 또 움직이고 또 움직이고 또 움직였어', '가격이 30만원이었어', '사람들이 놀랐대', '다들 좋아했어?'] }, rules, '소재 글', 2);
  assert.equal(bad.ok, false);
  const h = bad.hints.join(' / ');
  assert.match(h, /1번 줄 말투를 반말로/);
  assert.match(h, /2번 줄을 더 짧게/);
  assert.match(h, /3번 줄 숫자에 근거가 없다/);
  assert.match(h, /제목을 2줄로/);
  assert.match(h, /마지막 줄은 질문 말고 단정문으로/);
  assert.ok(!/38|14/.test(h), '임계값 숫자 노출 금지');
  const good = lintScript({ title: '집에서 만든\n미친 화면', lines: ['이거 처음 보면 놀라', '색깔 막대가 움직였어', '가격이 30만원이었대', '사람들이 다 놀랐어', '다들 좋아했어'] }, rules, '정가 30만원 짜리', 2);
  assert.equal(good.ok, true, good.hints.join(','));
  assert.equal(speechOf('그렇습니다.'), 'jondaet');
  assert.equal(speechOf('그랬어!'), 'banmal');
});

test('감사 로그: 키·URL·경로·긴 지문 값이 남지 않는다', () => {
  audit('test', { job: 'j_x', code: 'SHORTEM-L1.12.1.1.' + 'a'.repeat(32), result: 'https://x.y/blob/abc?sig=1', where: 'C:\\Users\\me\\.shortem\\keys\\typecast', assets: ['font:A'] });
  const log = fs.readFileSync(path.join(process.env.SHORTEM_HOME, 'audit.jsonl'), 'utf8');
  assert.ok(!log.includes('SHORTEM-L1.12'));
  assert.ok(!log.includes('https://'));
  assert.ok(!log.includes('keys\\\\typecast') && !log.includes('keys/typecast'));
});

test('틀 정규화: $per_video 기본값 · 여러 틀 span · 못 받은 글꼴 대체', () => {
  const f = { canvas: [1080, 1920], frames: [
    { id: 'hook', span: '$per_video', layers: [{ kind: 'bg', rgb: [0, 0, 0] }, { kind: 'text', role: 'title', x: 540, y: 200, w: 1000, lines: 2, font: 'Nope', size: '$per_video', rgb: '$per_video', text: '$per_video' }] },
    { id: 'body', span: '$per_video', layers: [{ kind: 'bg', rgb: [255, 255, 255] }, { kind: 'video', x: 0, y: 400, w: 1080, h: 1000 }, { kind: 'text', role: 'caption', x: 540, y: '$per_video', w: 1000, font: 'A', size: 60, rgb: [0, 0, 0], enter: '$per_video' }, { kind: 'text', role: 'label', x: 10, y: 10, w: 100, font: 'A', size: 20, rgb: [0, 0, 0], text: '$per_video' }] }] };
  const s = normalizeFrame(f, { title: '가\n나', firstSpanEnd: 2, fonts: new Set(['A']) });
  assert.deepEqual(s.frames.map(x => x.span), [[0, 2], [2, null]]);
  const t = s.frames[0].layers.find(l => l.role === 'title');
  assert.equal(t.size, 96); assert.deepEqual(t.rgb, [255, 255, 255]); assert.equal(t.font, 'A'); assert.equal(t.font_missing, true); assert.equal(t.text, '가\n나');
  const c = s.frames[1].layers.find(l => l.role === 'caption');
  assert.equal(c.y, 1430); assert.equal(c.enter, null);
  assert.ok(!s.frames[1].layers.some(l => l.role === 'label'), '고정 문구 모르면 그 층은 안 그림');
});

test('자막 나누기: 어절 단위, 칸 글자 수 안', () => {
  const ch = chunkLine('색깔 막대가 갑자기 움직이기 시작했어 그리고 소용돌이가 됐지', 12);
  assert.ok(ch.length >= 3);
  assert.equal(ch.join(' '), '색깔 막대가 갑자기 움직이기 시작했어 그리고 소용돌이가 됐지');
  for (const c of ch) assert.ok(c.length <= 12 || !c.includes(' '));
});
