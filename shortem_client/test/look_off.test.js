// 11-06 문인석 #9438: 꾸민 모양을 끄는 길이 없었다 — 지우면 서버 맞추기 때 웹 꾸민 모양이 다시 받아진다.
//   끄기 = 빈 표식(snapshot null + 지금 시각) · 서버 맞추기(syncFromServer) 뒤에도 꺼진 채.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('look_off');
const { api } = await import('../server/api.js');
const { syncFromServer, readSettings, clearLook } = await import('../server/local_settings.js');
const { homeDir } = await import('../server/paths.js');

const PID = 'p_3b6f601651';
const WEB = { snapshot: { presetId: 'fixed_s0093' }, updated: 5 };

test('꾸민 모양 끄기 — 빈 표식으로 남고 서버 맞추기 뒤에도 꺼진 채', async () => {
  fs.mkdirSync(homeDir(), { recursive: true });
  fs.writeFileSync(path.join(homeDir(), 'settings.json'), JSON.stringify({ current: PID, channels: {}, looks: { [PID]: WEB } }));
  const r = clearLook(PID);
  assert.equal(r.ok, true);
  assert.equal(readSettings().looks[PID].snapshot, null);
  api.studio = async () => ({ settings: { current: PID, current_at: 0, channels: {}, looks: { [PID]: WEB } } });   // 서버엔 웹 꾸민 모양이 그대로
  const s = await syncFromServer({ force: true });
  assert.equal(s.ok, true);
  assert.equal(readSettings().looks[PID].snapshot, null, '서버 맞추기가 웹 꾸민 모양을 되살리면 안 된다');
});
