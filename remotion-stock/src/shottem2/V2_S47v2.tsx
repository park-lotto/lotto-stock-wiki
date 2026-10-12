import React from 'react';
import { AbsoluteFill, Audio, Sequence, staticFile } from 'remotion';
import { Scene, Para } from './V2_Engine';
import { KakaoChat, Challenge30, MemberGallery, WordCaption } from './V2_Fx2';
import { V2_S47_Proof } from './V2_S47_Proof';

/* S4-7 완성·증거 2판 (2026-10-12 사장님: 카톡 후기 각색 / 30일 챌린지 극적으로 / 판매 수량 강조)
   나레이션은 "회원분들 반응도 보시죠"(23.0초)에서 멈추고 카톡 장면(CH)을 넣은 뒤 이어진다.
   화면 전환 시각 = 필재 TTS 단어 시각(V2_Captions '14') — 80건 27.3초 · 4만 29.0초 · 그래프 36.7초 */
const F = (s: number) => Math.round(s * 30);
const VOICE = 'shottem2/v2s47/voice.mp3';
const CUT = F(23.0);          // 나레이션 멈추는 자리
const CH = 450;               // 카톡 장면 15초
const VEND = F(50.27);        // 음성 끝
const P2 = CUT + CH;          // 나레이션 다시 시작하는 프레임
const at = (voiceSec: number) => P2 + F(voiceSec) - CUT;   // 뒤쪽 음성 시각 → 전체 프레임
export const V2_S47V2_FRAMES = P2 + (VEND - CUT) + 20;

const HEAD: Para[] = [
  { dur: 16.9, back: 'hero', seed: 21, hits: [
    { t: '완성본 vs 원본', style: 'mega', sub: '녹화 들어올 자리' }, { t: '어떻습니까?', style: 'neon' },
    { t: '머리 쥐어짠 순간\n0번', style: 'mega', accent: '0번' }, { t: '눈앞에서\n직접 만들어 보였습니다', style: 'flip', accent: '직접' } ], hitAt: [0, 0.35, 0.5, 0.78] },
  { dur: 4.4, img: 'shottem2/s47/list.png', hits: [{ t: '실제로 받은 조회수', style: 'tag' }] },
  { dur: 1.7, hits: [{ t: '', node: <MemberGallery title="회원님들 반응도 보시죠" sub="1기 회원 실제 후기" seed={6} /> }] },
];
const TAIL: Para[] = [
  { dur: 10.2, back: 'ring', seed: 12, hits: [
    { t: '매일 올리는 게\n제일 힘들었다', style: 'slam' }, { t: '이제 매일은\n문제가 아니다', style: 'mega', accent: '문제가 아니다' },
    { t: '', style: 'vs', vs: ['양산형\n같은 틀 반복', '숏템메이커\n매일, 다르게'] } ], hitAt: [0, 0.45, 0.78] },
];

export const V2_S47V2: React.FC = () => (
  <AbsoluteFill style={{ background: '#000' }}>
    <Audio src={staticFile('shottem2/v2bgm/epic.mp3')} loop volume={0.11} />
    {/* 앞 나레이션 0~23초 */}
    <Sequence from={0} durationInFrames={CUT}>
      <Audio src={staticFile(VOICE)} endAt={CUT} />
      <Scene paras={HEAD} />
      <WordCaption k="14" />
    </Sequence>
    {/* 카톡 후기 — 나레이션 없이 */}
    <Sequence from={CUT} durationInFrames={CH}><KakaoChat every={66} /></Sequence>
    {/* 뒤 나레이션 */}
    <Sequence from={P2}><Audio src={staticFile(VOICE)} startFrom={CUT} /></Sequence>
    {/* 한 달 기록 — "한 회원분의 실제 한 달 · 매일 올렸습니다" */}
    <Sequence from={P2} durationInFrames={at(27.2) - P2}><Challenge30 per={5} /></Sequence>
    {/* 80건 — 증거 장면의 판매 수량 확대 구간 */}
    <Sequence from={at(27.2)} durationInFrames={at(28.95) - at(27.2)}>
      <Sequence from={-400}><V2_S47_Proof /></Sequence>
    </Sequence>
    {/* 한 달 수익 4만 7,820원 → "크지 않습니다" */}
    <Sequence from={at(28.95)} durationInFrames={at(33.2) - at(28.95)}>
      <Sequence from={-760}><V2_S47_Proof /></Sequence>
    </Sequence>
    {/* "이분, 한 달 내내 쉬지 않고" — 달력 완성 화면 다시 */}
    <Sequence from={at(33.2)} durationInFrames={at(36.0) - at(33.2)}>
      <Sequence from={-130}><Challenge30 per={5} /></Sequence>
    </Sequence>
    {/* 그래프 끝 급등 */}
    <Sequence from={at(36.0)} durationInFrames={at(40.1) - at(36.0)}>
      <Sequence from={-900}><V2_S47_Proof /></Sequence>
    </Sequence>
    {/* 마무리 */}
    <Sequence from={at(40.1)}><Scene paras={TAIL} /></Sequence>
    <Sequence from={P2}><WordCaption k="14" offset={23.0} /></Sequence>
  </AbsoluteFill>
);
