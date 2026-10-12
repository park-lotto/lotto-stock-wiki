import React from 'react';
import {
  AbsoluteFill, OffthreadVideo, Sequence, Loop, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import { Scene, Para } from './V2_Engine';
import { MemberGallery, WordCaption } from './V2_Fx2';
import { Talk } from './V2_S1_Open';
import { IconBadge } from './V2_Bg';
import { C, F } from './theme2';

/* S1 오프닝 2판 (2026-10-12 사장님: 엄마 쇼츠는 나레이션 멈추고 원음 몇 초 / 배경 다양 / 자막 다양 / 고급 아이콘)
   처음: 어머니 쇼츠를 끝까지 원음 그대로 → 그다음 필재 나레이션 시작(전체가 INTRO 만큼 뒤로 밀린다) */
const INTRO = 1063;   // 메인(와플 쇼츠) 35.43초를 원음으로 끝까지(사장님 10-12: 와플이 위·메인, 카메라는 뒤)
const A = (n: string) => 'shottem2/v2s1/' + n;
const PARA_S = [7.045, 6.955, 10.773, 11.455, 15.682, 12.227, 12.364, 4.091, 4.045, 10.137];
const VOICE_F = Math.round(PARA_S.reduce((a, b) => a + b, 0) * 30) + 15;
export const V2_S1B_FRAMES = INTRO + VOICE_F;

/** 쇼츠 폰 — 맨 위 채널 띠(높이 8.9%)는 우리 금색 띠로 덮고, 아래 @워터마크(90~94.5%)는 흐린다 */
const ShortPhone: React.FC<{ src: string; w: number; muted?: boolean; label: string; glow?: number }> = ({ src, w, muted, label, glow = 0.5 }) => {
  const h = (w * 16) / 9;
  return (
    <div style={{ width: w, height: h, borderRadius: w * 0.07, overflow: 'hidden', position: 'relative', border: Math.round(w * 0.012) + 'px solid #0b0b0d',
      boxShadow: '0 60px 160px rgba(0,0,0,0.95), 0 0 0 2px rgba(250,204,21,' + glow + '), 0 0 80px rgba(250,204,21,' + glow * 0.5 + ')' }}>
      <OffthreadVideo src={staticFile(src)} muted={muted} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: '8.9%', background: 'linear-gradient(180deg,#141008,#0b0906)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: w * 0.025, borderBottom: '2px solid rgba(250,204,21,0.6)' }}>
        <div style={{ width: w * 0.022, height: w * 0.022, borderRadius: w, background: '#ef4444', boxShadow: '0 0 10px #ef4444' }} />
        <div style={{ font: '900 ' + Math.round(w * 0.06) + 'px ' + F.sans, color: C.gold, letterSpacing: 1 }}>{label}</div>
      </div>
      <div style={{ position: 'absolute', left: '28%', width: '44%', top: '90%', height: '4.6%', backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)', borderRadius: 12 }} />
    </div>
  );
};

/** 오프닝 — 두 작품을 겹쳐 띄운다. 뒤(왼쪽 위)는 소리 없이, 앞(오른쪽 아래)은 원래 TTS 그대로 끝까지 */
const MomOpen: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inA = spring({ frame: f - 6, fps, config: { damping: 15, mass: 0.9 } });
  const inB = spring({ frame: f, fps, config: { damping: 15, mass: 0.9 } });
  const head = spring({ frame: f - 30, fps, config: { damping: 12 } });
  const out = spring({ frame: f - INTRO + 6, fps, config: { damping: 16 } });   // 나레이션 들어갈 때 오른쪽으로 비켜 선다
  const floatA = Math.sin(f / 40) * 10;
  const floatB = Math.cos(f / 46) * 12;
  const push = interpolate(f, [0, INTRO], [1, 1.06], { extrapolateRight: 'clamp' });
  const sweep = interpolate(f % 150, [0, 50], [-30, 130], { extrapolateRight: 'clamp' });
  const tag = spring({ frame: f - INTRO - 20, fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ background: '#040304', overflow: 'hidden' }}>
      <OffthreadVideo src={staticFile(A('mom1a.mp4'))} muted style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(50px) brightness(0.28) saturate(1.4)', transform: 'scale(1.4)' }} />
      <AbsoluteFill style={{ background: 'radial-gradient(circle at ' + (30 + Math.sin(f / 50) * 10) + '% 25%, rgba(255,190,80,0.35), transparent 45%)', mixBlendMode: 'screen' }} />
      <div style={{ position: 'absolute', top: '-20%', left: sweep + '%', width: '12%', height: '140%', transform: 'rotate(18deg)', background: 'linear-gradient(90deg,transparent,rgba(255,230,150,0.18),transparent)', filter: 'blur(10px)' }} />
      <AbsoluteFill style={{ transform: 'scale(' + push + ') translateX(' + out * 330 + 'px)' }}>
        {/* 뒤 — 카메라 쇼츠(소리 없음, 22.9초 반복) */}
        <div style={{ position: 'absolute', left: 520, top: 40 + floatB, transform: 'rotate(' + (-9 * inB) + 'deg) translateY(' + (1 - inB) * 900 + 'px) scale(0.9)', filter: 'brightness(0.78)' }}>
          <Loop durationInFrames={687} layout="none"><ShortPhone src={A('mom4.mp4')} w={470} muted label="60대 어머니 작품 #2" glow={0.3} /></Loop>
        </div>
        {/* 앞(메인) — 와플 쇼츠(원래 TTS) */}
        <div style={{ position: 'absolute', left: 870, top: 110 + floatA, transform: 'rotate(' + (6 * inA) + 'deg) translateY(' + (1 - inA) * 1000 + 'px)' }}>
          {f < INTRO
            ? <ShortPhone src={A('mom1a.mp4')} w={500} label="60대 어머니 작품 #1" glow={0.7} />
            : <Sequence from={INTRO} layout="none"><ShortPhone src={A('mom1a.mp4')} w={500} muted label="60대 어머니 작품 #1" glow={0.7} /></Sequence>}
        </div>
      </AbsoluteFill>
      {f < INTRO ? (
        <div style={{ position: 'absolute', left: 70, top: 330, width: 620, opacity: head, transform: 'translateX(' + (1 - head) * -120 + 'px)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, font: '800 30px ' + F.mono, color: '#fff' }}>
            <div style={{ width: 18, height: 18, borderRadius: 9, background: Math.floor(f / 15) % 2 ? '#ef4444' : 'transparent', boxShadow: '0 0 14px #ef4444' }} /> REAL · 실제 영상
          </div>
          <div style={{ font: '900 92px/1.12 ' + F.sans, color: C.paper, marginTop: 18, textShadow: '0 10px 30px #000' }}>이 영상,<br /><span style={{ color: C.gold, textShadow: '0 0 30px rgba(250,204,21,0.6), 0 10px 30px #000' }}>누가</span><br />만들었을까요?</div>
        </div>
      ) : null}
      <div style={{ position: 'absolute', left: 90, top: 300, opacity: tag, transform: 'translateX(' + (1 - tag) * -80 + 'px)' }}>
        <IconBadge name="heart" size={130} delay={INTRO + 20} />
        <div style={{ font: '800 40px ' + F.sans, color: C.dim, marginTop: 24 }}>만든 사람</div>
        <div style={{ font: '900 110px/1.08 ' + F.sans, color: C.gold, textShadow: '0 0 30px rgba(250,204,21,0.55), 0 10px 30px #000' }}>60대<br />우리 어머니</div>
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
