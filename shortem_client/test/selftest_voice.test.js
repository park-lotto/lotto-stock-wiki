// 자가점검이 보는 목소리 = 엔진이 실제로 쓸 목소리 하나(CS #142 → 11-03 합침: selftest.voiceProvider 와 memberVoice 두 벌이던 것)
//   local_settings.engineVoice — 시작 점검의 키 검사·목소리 시험·일레븐 요금제 검사가 같이 부른다
import test from 'node:test';
import assert from 'node:assert/strict';
import { freshDirs } from './helpers.js';

freshDirs('selftest_voice');
const { engineVoice, useCatalog, providerOf } = await import('../server/local_settings.js');
useCatalog({ default_pack: { tts: { voice_id: 'tc_preset' } }, preset_defaults: {} });     // 프리셋 기본 목소리 = 타입캐스트
const has = (...ks) => s => ks.includes(s);
const st = ch => ({ current: 'p_aaaaaaaaaa', channels: { p_aaaaaaaaaa: { pack: ch } } });

test('고른 회사를 그대로 본다', async () => {
  assert.equal(providerOf(await engineVoice(has('fish'), st({ tts: { provider: 'fish', voice_id: 'fs-x' } }))), 'fish');
  assert.equal(providerOf(await engineVoice(has(), st({ tts: { voice_id: 'kr-abc' } }))), 'elevenlabs');
});

test('지금 채널에 없고 프리셋 회사 키도 없으면 고른 적 있는 채널 → 키 있는 회사 기본 성우', async () => {
  const two = { current: 'p_aaaaaaaaaa', channels: { p_aaaaaaaaaa: { pack: {} }, p_bbbbbbbbbb: { pack: { tts: { provider: 'elevenlabs', voice_id: 'kr-x' } } } } };
  assert.equal((await engineVoice(has('elevenlabs'), two)).voice_id, 'kr-x');
  assert.equal((await engineVoice(has('fish'), st({}))).voice_id, 'fs-ilban2-stable');
  assert.equal((await engineVoice(has('typecast', 'fish'), st({}))).voice_id, 'tc_preset', '프리셋 회사 키가 있으면 프리셋 목소리');
});

test('채널을 안 골랐으면 키 있는 회사 기본 성우, 키도 없으면 없음', async () => {
  assert.equal((await engineVoice(has('elevenlabs'), { current: null, channels: {} })).voice_id, 'kr-mina-expressive');
  assert.equal(await engineVoice(has(), { current: null, channels: {} }), null);
});
