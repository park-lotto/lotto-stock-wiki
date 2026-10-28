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
