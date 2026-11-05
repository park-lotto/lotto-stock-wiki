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

test('점검도 401 을 일레븐 상태로 갈라 말한다(#4038 payment_issue · #3698 missing_permissions)', async () => {
  const { elevenStatusWhy } = await import('../server/selftest.js');
  assert.match(elevenStatusWhy('payment_issue'), /결제/);
  assert.match(elevenStatusWhy('missing_permissions'), /권한/);
  assert.match(elevenStatusWhy('detected_unusual_activity'), /유료/);
  assert.equal(elevenStatusWhy('invalid_api_key'), '일레븐랩스 키가 맞지 않습니다');
});

test('조회 권한(user_read)만 없는 키는 막지 않는다 — TTS 는 되는 키(11-05 이준연 #7048, 1.0.104 회귀)', async () => {
  const { elevenUsable } = await import('../server/selftest.js');
  const presets = [{ preset_id: 'kr-mina-stable', base_voice_id: 'AAAAAAAAAAAAAAAAAAAA' }];
  const denied = async () => { throw Object.assign(new Error('eleven_key'), { status: 'missing_permissions', why: '권한' }); };
  await elevenUsable('k', 'kr-mina-stable', { get: denied, presets });          // 통과(막지 않음)
  const pay = async () => { throw Object.assign(new Error('eleven_key'), { status: 'payment_issue', why: '결제' }); };
  await assert.rejects(elevenUsable('k', 'kr-mina-stable', { get: pay, presets }), e => /결제/.test(e.why));   // 결제 실패는 그대로 막음
});
