import React from 'react';
import {
  AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import { Scene, Para } from './V2_Engine';
import { MemberGallery, WordCaption } from './V2_Fx2';
import { Talk } from './V2_S1_Open';
import { IconBadge } from './V2_Bg';
import { C, F } from './theme2';

/* S1 오프닝 2판 (2026-10-12 사장님: 엄마 쇼츠는 나레이션 멈추고 원음 몇 초 / 배경 다양 / 자막 다양 / 고급 아이콘)
   처음: 어머니 쇼츠를 끝까지 원음 그대로 → 그다음 필재 나레이션 시작(전체가 INTRO 만큼 뒤로 밀린다) */
const INTRO = 1063;   // 어머니 쇼츠 전체 35.43초를 원음으로 끝까지(사장님 10-12)
const A = (n: string) => 'shottem2/v2s1/' + n;
const PARA_S = [7.045, 6.955, 10.773, 11.455, 15.682, 12.227, 12.364, 4.091, 4.045, 10.137];
const VOICE_F = Math.round(PARA_S.reduce((a, b) => a + b, 0) * 30) + 15;
export const V2_S1B_FRAMES = INTRO + VOICE_F;

/** 오프닝 — 폰 화면 하나가 화면 가득에서 줄어들며 자리 잡고, 원음이 나레이션 밑으로 내려간다 */
const MomOpen: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const shrink = spring({ frame: f - INTRO + 10, fps, config: { damping: 18 } });
  const w = interpolate(shrink, [0, 1], [760, 560]);
  const x = interpolate(shrink, [0, 1], [0, -260]);

  const rec = Math.floor(f / 15) % 2 === 0;
  const tag = spring({ frame: f - INTRO - 20, fps, config: { damping: 12 } });
  const h = (w * 16) / 9;
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      <OffthreadVideo src={staticFile(A('mom1a.mp4'))} muted style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(40px) brightness(0.35)', transform: 'scale(1.3)' }} />
      <div style={{ position: 'absolute', left: 960 - w / 2 + x, top: 540 - Math.min(h, 1040) / 2, width: w, height: Math.min(h, 1040), borderRadius: 40, overflow: 'hidden', border: '7px solid #0b0b0d', boxShadow: '0 50px 150px rgba(0,0,0,0.9), 0 0 0 2px rgba(250,204,21,0.5)' }}>
        {f < INTRO
          ? <OffthreadVideo src={staticFile(A('mom1a.mp4'))} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          : <Sequence from={INTRO} layout="none"><OffthreadVideo src={staticFile(A('mom1a.mp4'))} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} /></Sequence>}
      </div>
      {f < INTRO ? (
        <div style={{ position: 'absolute', left: 60, top: 50, display: 'flex', alignItems: 'center', gap: 14, font: '800 34px ' + F.mono, color: '#fff' }}>
          <div style={{ width: 22, height: 22, borderRadius: 11, background: rec ? '#ef4444' : 'transparent', boxShadow: rec ? '0 0 16px #ef4444' : 'none' }} /> PLAY · 실제 영상
        </div>
      ) : null}
      <div style={{ position: 'absolute', left: 1080, top: 300, opacity: tag, transform: 'translateX(' + (1 - tag) * 80 + 'px)' }}>
        <IconBadge name="heart" size={130} delay={INTRO + 20} />
        <div style={{ font: '800 40px ' + F.sans, color: C.dim, marginTop: 24 }}>만든 사람</div>
        <div style={{ font: '900 110px/1.08 ' + F.sans, background: 'linear-gradient(180deg,#fff6c2,#facc15 55%,#f59e0b)', WebkitBackgroundClip: 'text', color: 'transparent', filter: 'drop-shadow(0 0 24px rgba(250,204,21,0.5))' }}>60대<br />우리 어머니</div>
        <div style={{ font: '800 40px ' + F.sans, color: C.paper, marginTop: 20 }}>타자 0번 · 마우스 클릭만</div>
      </div>
    </AbsoluteFill>
  );
};

// 나레이션 문단(필재 실측). 배경은 문단마다 다른 종류로 — 같은 배경 연속 금지
const P: Para[] = [
  { dur: 7.045, hits: [{ t: '', node: <AbsoluteFill /> }] },   // 오프닝 장면이 위에 깔려 있다(MomOpen)
  { dur: 6.955, back: 'ring', seed: 1, hits: [
    { t: '"60대 우리 엄마도\n직접 할 수 있게"', style: 'flip', accent: '직접' }, { t: '그 약속, 지켰습니다', style: 'neon' } ] },
  { dur: 10.773, back: 'aurora', seed: 2, hits: [
    { t: '가입 회원 중 가장 많은 연령대', style: 'bars', unit: '명', bars: [['20대', 23], ['30대', 80], ['40대', 162], ['50대', 175]] },
    { t: '50대', style: 'mega', sub: 'NO.1 AGE GROUP' } ], hitAt: [0, 0.62] },
  { dur: 11.455, hits: [{ t: '', node: <MemberGallery title="실제 회원님들이 만든 영상입니다" sub="숏템메이커 회원 완성 쇼츠" seed={2} /> }] },
  { dur: 15.682, back: 'split', seed: 4, hits: [
    { t: '책상 하나\n개발자 한 명', style: 'mega', accent: '한 명' },
    { t: '손으로 하던 매일', style: 'flow', steps: ['찾고', '쓰고', '자르고', '지우고', '입히고'] },
    { t: '이 노가다를\n대신 해 줄 프로그램', style: 'kinetic', accent: '대신' } ], hitAt: [0, 0.3, 0.68] },
  { dur: 12.227, back: 'mosaic', seed: 5, hits: [
    { t: '1편 이후 59일 동안', style: 'count', num: 2478, unit: '건', sub: 'UPDATE' },
    { t: '하루 평균', style: 'count', num: 42, unit: '번' },
    { t: '숏템메이커\nV2', style: 'mega', sub: 'COMPLETELY NEW' } ], hitAt: [0, 0.42, 0.7] },
  { dur: 12.364, back: 'hero', seed: 7, hits: [
    { t: '', style: 'vs', vs: ['보는 것', '직접 써 보는 것'] },
    { t: '지금 나와 있는 것 중\n숏템메이커가 제일 셉니다', style: 'mega', accent: '제일 셉니다' } ], hitAt: [0, 0.48] },
  { dur: 4.091, hits: [{ t: '', node: <Talk /> }] },
  { dur: 4.045, back: 'ring', seed: 9, hits: [{ t: '먼저 보신 분이,\n먼저 가져갑니다', style: 'neon' }] },
  { dur: 10.137, back: 'wall', seed: 3, hits: [
    { t: '"강의나 프로그램,\n이미 결제해 보셨습니까?"', style: 'quote' },
    { t: '끝까지 보고, 직접 비교해 보십시오', style: 'tag' } ], hitAt: [0, 0.55] },
];

export const V2_S1B: React.FC = () => (
  <AbsoluteFill style={{ background: '#000' }}>
    <Sequence from={INTRO} durationInFrames={VOICE_F}>
      <Scene voice={A('voice.mp3')} paras={P} />
    </Sequence>
    {/* 오프닝 장면 = 원음 4초 + 첫 문단 */}
    <Sequence from={0} durationInFrames={INTRO + Math.round(PARA_S[0] * 30)}>
      <MomOpen />
    </Sequence>
    <Sequence from={INTRO} durationInFrames={VOICE_F}>
      <WordCaption k="00" />
    </Sequence>
  </AbsoluteFill>
);
