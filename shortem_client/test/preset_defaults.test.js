// 기본값 = 그 프리셋의 원본 영상(사장님 10-20, 모든 프리셋) — 엔진 기본 팩 ← 프리셋 기본값 ← 회원이 바꾼 칸 (local_settings.packFor)
//   10-20 실측: 프리셋 5개가 모두 팩 하나(잘난고딕·외곽선 0·남자 필재)로 덮여 얜샷템이 원본(Cafe24·외곽선 5·여자 문정)과 달랐다
import test from 'node:test';
import assert from 'node:assert/strict';
import { freshDirs } from './helpers.js';

freshDirs('preset_defaults');
const { useCatalog, packFor } = await import('../server/local_settings.js');
const PID = 'p_a06ac463ee', OTHER = 'p_1111111111';
useCatalog({
  default_pack: { text: { title_font: 'JalnanGothic', caption_font: 'CcPretendard-Bold', caption: { mode: 'accumulate', outline_px: 0 } },
    tts: { voice_id: 'tc_68257f68bc6e3c161ab5078d', name: '필재', tempo: 1.36 }, bgm: { candidates: ['qiuqiu'], gain: 0.12 } },
  preset_defaults: { [PID]: { text: { title_font: 'Cafe24Ohsquare', caption_font: 'Cafe24Ohsquare', caption: { outline_px: 5, outline_rgb: [0, 0, 0] } },
    tts: { voice_id: 'tc_68f9c6a72f0f04a417bb136f', name: '문정', tempo: 1.36 }, bgm: { candidates: ['sweets'] } } },
});

test('회원이 안 바꾼 칸 = 프리셋 기본값, 프리셋에 없는 칸 = 엔진 기본', async () => {
  const p = await packFor(PID);
  assert.equal(p.text.title_font, 'Cafe24Ohsquare');
  assert.equal(p.text.caption.outline_px, 5);
  assert.equal(p.text.caption.mode, 'accumulate');          // 프리셋에 없는 칸
  assert.equal(p.tts.name, '문정');
  assert.deepEqual(p.bgm.candidates, ['sweets']);
  assert.equal(p.bgm.gain, 0.12);
  assert.equal((await packFor(OTHER)).tts.name, '필재');    // 표에 없는 프리셋 = 엔진 기본
});

test('회원이 바꾼 칸만 회원 값', async () => {
  // savePack 은 엔진 check 를 부른다 — 여기서는 저장 파일(회원이 바꾼 칸만 남는 꼴)로 바로 넣는다
  const fs = await import('node:fs'); const path = await import('node:path');
  fs.writeFileSync(path.join(process.env.SHORTEM_HOME, 'settings.json'), JSON.stringify({ current: PID, channels: { [PID]: { pack: { tts: { voice_id: 'tc_x', name: '김건' } } } } }));
  const p = await packFor(PID);
  assert.equal(p.tts.name, '김건');
  assert.equal(p.text.title_font, 'Cafe24Ohsquare');        // 나머지는 프리셋 그대로
});
