// 자가점검이 회원이 고른 목소리 회사를 본다(CS #142)
import test from 'node:test';
import assert from 'node:assert/strict';
import { voiceProvider } from '../server/selftest.js';

test('고른 회사를 그대로 본다', () => {
  assert.equal(voiceProvider({ current: 'p1', channels: { p1: { pack: { tts: { provider: 'fish' } } } } }), 'fish');
  assert.equal(voiceProvider({ current: 'p1', channels: { p1: { pack: { tts: { voice_id: 'kr-abc' } } } } }), 'elevenlabs');
});

test('지금 채널에 없으면 고른 적 있는 채널을 본다', () => {
  assert.equal(voiceProvider({ current: 'p1', channels: { p1: { pack: {} }, p2: { pack: { tts: { provider: 'elevenlabs' } } } } }), 'elevenlabs');
});

test('아무것도 안 골랐으면 타입캐스트', () => {
  assert.equal(voiceProvider({ current: null, channels: {} }), 'typecast');
  assert.equal(voiceProvider(undefined), 'typecast');
});
