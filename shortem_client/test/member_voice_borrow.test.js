// 프리셋 기본 목소리 회사 키가 없으면 회원이 다른 프리셋에서 고른 목소리(키 있는 회사)를 쓴다 — #1186·#878 정민혜, #953·#1040 김미화, #1846 이성택.
//   프리셋 tts 가 타입캐스트로 남아 제작에서 '타입캐스트 키'를 요구했고, 회원이 목소리를 손으로 옮겨 우회했다.
//   판단 주인 local_settings.memberVoice — 엔진 팩 member.tts 를 정하면 엔진(styles.member_frame → need_list·합성)이 그대로 따른다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { memberVoice, providerOf } from '../server/local_settings.js';

const TC = { voice_id: 'tc_preset', name: '프리셋' };
const FISH = { voice_id: 'fs-abc', name: '내 피쉬', provider: 'fishaudio', tempo: 1.2 };
const has = (...ks) => s => ks.includes(s);

test('이 프리셋 목소리를 안 정했고 타입캐스트 키가 없으면 다른 프리셋의 피쉬 목소리를 쓴다(빠르기는 안 옮긴다)', () => {
  const st = { current: 'p_b', channels: { p_a: { pack: {} }, p_b: { pack: { tts: FISH } } } };
  assert.deepEqual(memberVoice(st, 'p_a', TC, has('fish')), { voice_id: 'fs-abc', name: '내 피쉬', provider: 'fishaudio' });
});

test('프리셋 회사 키가 있으면 프리셋 목소리 그대로', () => {
  const st = { current: 'p_b', channels: { p_a: { pack: {} }, p_b: { pack: { tts: FISH } } } };
  assert.deepEqual(memberVoice(st, 'p_a', TC, has('typecast', 'fish')), {});
});

test('회원이 이 프리셋 목소리를 정했으면 그대로 — 빌리지 않는다', () => {
  const own = { voice_id: 'tc_mine' };
  const st = { current: 'p_a', channels: { p_a: { pack: { tts: own } }, p_b: { pack: { tts: FISH } } } };
  assert.equal(memberVoice(st, 'p_a', TC, has('fish')), own);
});

test('빌릴 목소리도 키가 없으면 프리셋 그대로(점검이 프리셋 회사 키를 요구)', () => {
  const st = { current: 'p_a', channels: { p_a: { pack: { tts: { tempo: 1.1 } } }, p_b: { pack: { tts: FISH } } } };
  assert.deepEqual(memberVoice(st, 'p_a', TC, has()), { tempo: 1.1 });
});

test('회원 빠르기만 정한 채널도 목소리는 빌리고 빠르기는 남긴다', () => {
  const st = { current: 'p_a', channels: { p_a: { pack: { tts: { tempo: 1.1 } } }, p_b: { pack: { tts: FISH } } } };
  assert.deepEqual(memberVoice(st, 'p_a', TC, has('fish')), { voice_id: 'fs-abc', name: '내 피쉬', provider: 'fishaudio', tempo: 1.1 });
  assert.equal(providerOf({ provider: 'fishaudio' }), 'fish');
});
