// 서버 맞추기가 회원 PC 에서 방금 바꾼 칸을 덮었다 — #1958 이성택(caption_scale·brand.name_style 저장 직후 사라짐), #1041 최일환(필재로 바꿔도 restyle 때 박창수로).
//   서버 저장 관문(claude_studio.pc_sync)이 PC 칸을 거절하면(서버 엔진이 아직 모르는 칸·관문 차이) 서버 옛 칸이 돌아오고, PC 가 그걸 통째로 썼다.
//   PC 도 서버 sync_merge 와 같은 규칙(프리셋마다 더 최근에 바꾼 쪽)으로 받는다 — local_settings.mergeChannels.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('settings_sync_keep');
const { api } = await import('../server/api.js');
const { syncFromServer, readSettings } = await import('../server/local_settings.js');
const { homeDir } = await import('../server/paths.js');

const mine = { pack: { tts: { voice_id: 'tc_piljae' }, text: { caption_scale: 1.4 } }, updated: 2000 };
const old = { pack: { tts: { voice_id: 'tc_park', tempo: 1.1 } }, updated: 1000 };

function local(ch) {
  fs.mkdirSync(homeDir(), { recursive: true });
  fs.writeFileSync(path.join(homeDir(), 'settings.json'), JSON.stringify({ current: 'p_aaaaaaaaaa', current_at: 1, channels: ch }));
}

test('서버가 이 PC 칸을 거절해 옛 칸을 돌려줘도 더 최근에 바꾼 이 PC 칸을 지킨다', async () => {
  local({ p_aaaaaaaaaa: mine });
  api.studio = async () => ({ ok: true, settings: { current: 'p_aaaaaaaaaa', current_at: 1, channels: { p_aaaaaaaaaa: old } } });
  assert.equal((await syncFromServer({ force: true })).ok, true);
  assert.deepEqual(readSettings().channels.p_aaaaaaaaaa, mine);
});

test('웹에서 더 최근에 바꾼 칸·이 PC 에 없던 프리셋은 받아 온다', async () => {
  const web = { pack: { tts: { voice_id: 'tc_web' } }, updated: 3000 };
  local({ p_aaaaaaaaaa: mine });
  api.studio = async () => ({ ok: true, settings: { current: 'p_aaaaaaaaaa', current_at: 1, channels: { p_aaaaaaaaaa: web, p_bbbbbbbbbb: old } } });
  await syncFromServer({ force: true });
  assert.deepEqual(readSettings().channels, { p_aaaaaaaaaa: web, p_bbbbbbbbbb: old });
});
