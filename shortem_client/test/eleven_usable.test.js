import test from 'node:test';
import assert from 'node:assert/strict';

test('일레븐 무료 요금제 + 공유 목록 목소리는 점검에서 막고, 내 목소리·유료는 통과(11-03 윤상길)', async () => {
  const { elevenUsable, elevenBaseId } = await import('../server/selftest.js');
  const presets = [{ preset_id: 'kr-mina-stable', base_voice_id: 'AAAAAAAAAAAAAAAAAAAA' }];
  assert.equal(elevenBaseId('kr-mina-stable', presets), 'AAAAAAAAAAAAAAAAAAAA');
  const mk = (tier, cat) => async p => (p.includes('subscription') ? { tier } : { category: cat });
  await assert.rejects(elevenUsable('k', 'kr-mina-stable', { get: mk('free', 'professional'), presets }), e => /무료 요금제/.test(e.why));
  await elevenUsable('k', 'kr-mina-stable', { get: mk('creator', 'professional'), presets });
  await elevenUsable('k', 'BBBBBBBBBBBBBBBBBBBB', { get: mk('free', 'cloned'), presets });
  await elevenUsable('k', '', { get: mk('free', 'professional'), presets });
});
