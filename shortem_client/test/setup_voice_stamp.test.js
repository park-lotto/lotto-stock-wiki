// #3698·#3701(11-03 박준영): 준비 점검을 통과한 뒤 일레븐 키·목소리를 바꿨는데 점검 통과 표식(setup_ok.json)이 그대로라
//   권한 제한 키(voices_read 만)가 제작 8/11 장면 맞추기에서야 missing_permissions 로 멈췄다.
//   표식에 점검 때의 목소리·키 지문을 묶고, 제작 시작(flow_driver.startFlow)이 recheckVoice 로 바뀐 것만 다시 본다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('setup_voice_stamp');
const { homeDir } = await import('../server/paths.js');
const { useCatalog } = await import('../server/local_settings.js');
const { recheckVoice, voiceStamp } = await import('../server/selftest.js');
useCatalog({ default_pack: { tts: { voice_id: 'tc_preset' } }, preset_defaults: {} });

const PID = 'p_aaaaaaaaaa';
const settings = vid => ({ current: PID, channels: { [PID]: { pack: { tts: { provider: 'elevenlabs', voice_id: vid } } } } });
const stamp = d => fs.writeFileSync(path.join(homeDir(), 'setup_ok.json'), JSON.stringify(d));
const read = () => JSON.parse(fs.readFileSync(path.join(homeDir(), 'setup_ok.json'), 'utf8'));
const keys = k => svc => (svc === 'elevenlabs' ? k : '');
const bad = async () => { throw Object.assign(new Error('eleven_key'), { why: '일레븐랩스 키가 맞지 않습니다', fix: '키를 다시' }); };

test('점검 뒤 키가 바뀌면 제작 시작 때 목소리를 다시 보고, 못 쓰는 키면 막는다', async () => {
  const s1 = settings('AAAAAAAAAAAAAAAAAAAA');
  const v = await voiceStamp(s1, { key: keys('sk_old') });
  stamp({ ok: true, at: 1, fails: [], voice: v });
  await assert.rejects(recheckVoice(PID, { settings: s1, key: keys('sk_new_restricted'), usable: bad }), e => /키가 맞지 않습니다/.test(e.why));
});

test('점검 뒤 목소리가 바뀌어도 다시 본다', async () => {
  const s1 = settings('AAAAAAAAAAAAAAAAAAAA');
  stamp({ ok: true, at: 1, fails: [], voice: await voiceStamp(s1, { key: keys('sk_same') }) });
  let called = 0;
  await recheckVoice(PID, { settings: settings('BBBBBBBBBBBBBBBBBBBB'), key: keys('sk_same'), usable: async () => { called++; } });
  assert.equal(called, 1);
  assert.equal(read().voice.voice, 'BBBBBBBBBBBBBBBBBBBB', '통과하면 표식을 지금 목소리로 고친다');
});

test('같은 키·같은 목소리면 아무것도 부르지 않는다(돈·시간 0)', async () => {
  const s1 = settings('AAAAAAAAAAAAAAAAAAAA');
  stamp({ ok: true, at: 1, fails: [], voice: await voiceStamp(s1, { key: keys('sk_same') }) });
  await recheckVoice(PID, { settings: s1, key: keys('sk_same'), usable: async () => { throw new Error('부르면 안 됨'); } });
});

test('옛 표식(목소리 기록 없음)도 한 번 다시 본다', async () => {
  stamp({ ok: true, at: 1, fails: [] });
  await assert.rejects(recheckVoice(PID, { settings: settings('AAAAAAAAAAAAAAAAAAAA'), key: keys('sk_x'), usable: bad }), e => !!e.why);
});

test('표식에 키 값 자체는 남기지 않는다', async () => {
  const v = await voiceStamp(settings('AAAAAAAAAAAAAAAAAAAA'), { key: keys('sk_secret_value') });
  assert.ok(!JSON.stringify(v).includes('sk_secret_value'));
});
