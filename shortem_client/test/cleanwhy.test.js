// 고객에게 나가는 실패 글·만들기 응답에 숏템 내부(경로·파일 이름·벤치 프리셋 경로)가 안 새는가(관제 234 5판)
import test from 'node:test';
import assert from 'node:assert/strict';
import { freshDirs } from './helpers.js';

freshDirs('cleanwhy');
const { cleanWhy, shapeSession } = await import('../server/make_flow.js');
const { SERVER_INSTRUCTIONS } = await import('../server/index.js');

test('실패 글에서 경로·파일 이름·프리셋 경로·트레이스백을 지운다', () => {
  const s = 'RuntimeError: 재료 없음 C:\\Users\\x\\engine\\remake.py channel/sseolpulda/preset/A/frame.json /home/u/a.py 3\nTraceback (most recent call last): boom';
  const w = cleanWhy(s);
  for (const bad of ['Users', 'remake.py', 'sseolpulda', 'frame.json', '/home', 'Traceback']) assert.ok(!w.includes(bad), `${bad} 가 남았다: ${w}`);
  assert.ok(w.includes('재료 없음'));
});

test('만들기 응답에 내부 프리셋 경로가 없다', () => {
  const o = shapeSession({ sid: 'abcdefabcdef', state: 'candidates', preset: 'channel/sseolpulda/preset/A_흰바탕창/창아래_검정', candidates: [{ n: 1, title: 't', total: 7 }] });
  assert.ok(!JSON.stringify(o).includes('sseolpulda'));
  const f = shapeSession({ sid: 'abcdefabcdef', state: 'failed', error: 'X C:\\a\\b.py channel/x/preset/y' });
  assert.ok(!JSON.stringify(f).match(/b\.py|channel\//));
});

test('서버 안내에 내부 설명 금지가 들어 있다', () => {
  assert.match(SERVER_INSTRUCTIONS, /설명드릴 수 없어요/);
  assert.match(SERVER_INSTRUCTIONS, /열어 읽거나 보여 주지 않는다/);
});

test('멈춤 전달 안내는 한국어 칸 이름으로 — why·fix 영어 칸 이름을 고객에게 쓰지 말라고(98 #160)', async () => {
  const { FAIL_SAY, TOOL_TEXT } = await import('../server/index.js');
  for (const t of [SERVER_INSTRUCTIONS, TOOL_TEXT.shortem_make]) {
    assert.ok(t.includes(FAIL_SAY), '멈춤 안내가 FAIL_SAY 한 곳을 안 씀');
    assert.ok(!/why·fix 두 줄만/.test(t), '옛 안내(why·fix 두 줄만)가 남았다');
  }
  assert.match(FAIL_SAY, /이유: …/);
  assert.match(FAIL_SAY, /할 일: …/);
});

test('회원 Claude 역할(제작자) 한 곳 — 서버 안내 첫 줄 · make 스킬이 가리킨다(사장님 10-26)', async () => {
  const { MAKER_ROLE } = await import('../server/index.js');
  assert.ok(SERVER_INSTRUCTIONS.startsWith(MAKER_ROLE), '안내 첫 줄이 제작자 역할이 아님');
  for (const w of ['제작자', '가이드를 지킨다', '금지선', '스스로 헤쳐 나간다', '꼭 필요한 결정']) assert.ok(MAKER_ROLE.includes(w), w);
  const fs = await import('node:fs');
  const skill = fs.readFileSync(new URL('../../installer/plugin/shortem/skills/make/SKILL.md', import.meta.url), 'utf8');
  assert.match(skill, /역할: 너는 이 편의 제작자다/);
});
