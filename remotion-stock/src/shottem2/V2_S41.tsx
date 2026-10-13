import React from 'react';
import { AbsoluteFill, Audio, Loop, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { Scene, Para, sceneFrames } from './V2_Engine';
import { WordCaption } from './V2_Fx2';
import { Grain } from './fx';
import { C, F } from './theme2';

/* 숏템메이커 V2 광고 — S4-1 뭘 만들지(강의·프로그램이 시키는 수작업) · S4-7 머리(완성본 비교)
   데이터만 적는다. 연출은 V2_Engine 한 곳. 문단 길이·덩어리 시작 = 필재 TTS 정렬 파일 실측(초).
   bgm=false 는 배경음 파일이 없는 PC에서 렌더할 때만(--props). */

// ── S4-1 뭘 만들지 ──
const S41: Para[] = [
  { dur: 1.9, back: 'aurora', seed: 1, hits: [{ t: '유료 강의는\n이렇게 하라고 합니다', style: 'slam' }] },
  { dur: 11.5, back: 'aurora', seed: 4, hitAt: [0, 0.6], hits: [
    { t: '강의가 시키는 순서', style: 'flow', steps: ['채널\n팔로우', '떡상 영상\n저장', 'AI에게\n분석', '키워드\n번역', '해외 사이트\n하나씩 검색'] },
    { t: '영어 · 중국어로 번역해서\n사이트마다 하나씩', style: 'kinetic', accent: '하나씩' } ] },
  { dur: 4.45, back: 'aurora', seed: 7, hitAt: [0, 0.36], hits: [
    { t: '프로그램들도\n비슷하게 말합니다', style: 'tag' },
    { t: '"매일 올라오니까\n벤치마킹하면 된다"', style: 'quote' } ] },
  { dur: 5.3, back: 'aurora', seed: 10, hitAt: [0, 0.2, 0.7], hits: [
    { t: '막상 해 보면', style: 'slam' },
    { t: '단계는 복잡\n복사해서 붙여넣기', style: 'stack' },
    { t: '비슷한 영상 찾기는\n어렵습니다', style: 'kinetic', accent: '어렵습니다' } ] },
  { dur: 5.16, back: 'aurora', seed: 13, hitAt: [0, 0.36, 0.62], hits: [
    { t: '써 보신 분들은\n공감하실 겁니다', style: 'tag' },
    { t: '보여주기식\n자동화', style: 'mega', accent: '보여주기식' },
    { t: '실제로는\n잘 안 돌아갑니다', style: 'slam' } ] },
];
export const V2_S41_FRAMES = sceneFrames(S41);
export const V2_S41: React.FC<{ bgm?: boolean }> = ({ bgm = true }) => (
  <Scene voice="shottem2/v2s41/voice.mp3" paras={S41} cap="41" bgm={bgm} />
);

// ── S4-7 머리 — 터진 썰쇼핑 원본 vs 숏템메이커 완성본 나란히 ──
const SSUL = 'shottem2/v2s47h/ssul.mp4';
const MINE = 'shottem2/v2s47h/mine.mp4';
const Phone: React.FC<{ src: string; label: string; sub: string; gold?: boolean; delay: number; loop: number }> = ({ src, label, sub, gold, delay, loop }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - delay, fps, config: { damping: 13, mass: 0.7 } });
  const W = 420;
  const glow = gold ? 0.5 + Math.sin(f / 9) * 0.25 : 0;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, opacity: Math.min(1, p * 1.3), transform: 'translateY(' + (1 - p) * 140 + 'px) scale(' + (0.86 + p * 0.14) + ')' }}>
      <div style={{ padding: '8px 26px', borderRadius: 999, font: '900 34px ' + F.sans, color: gold ? '#111' : '#fff', background: gold ? C.gold : 'rgba(255,255,255,0.16)', border: gold ? 'none' : '2px solid rgba(255,255,255,0.5)' }}>{label}</div>
      <div style={{ width: W, height: (W * 16) / 9, borderRadius: 30, overflow: 'hidden', background: '#000', position: 'relative',
        boxShadow: gold ? '0 0 0 5px ' + C.gold + ', 0 0 ' + (60 + glow * 60) + 'px rgba(250,204,21,' + glow + '), 0 40px 100px rgba(0,0,0,0.9)' : '0 0 0 3px rgba(255,255,255,0.45), 0 40px 100px rgba(0,0,0,0.9)' }}>
        <Loop durationInFrames={loop}><OffthreadVideo src={staticFile(src)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} /></Loop>
      </div>
      <div style={{ font: '700 26px ' + F.sans, color: gold ? C.gold : 'rgba(255,255,255,0.75)' }}>{sub}</div>
    </div>
  );
};
export const V2_Compare: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const v = spring({ frame: f - 14, fps, config: { damping: 8, mass: 0.6 } });
  const drift = interpolate(f, [0, 400], [1.04, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse at 50% 40%, #1b1d2a 0%, #05060a 75%)', overflow: 'hidden' }}>
      <AbsoluteFill style={{ flexDirection: 'row', justifyContent: 'center', alignItems: 'flex-start', gap: 230, paddingTop: 22, transform: 'scale(' + drift + ')' }}>
        <Phone src={SSUL} label="지금 터지는 원본" sub="다른 썰쇼핑 채널의 터진 영상" delay={0} loop={720} />
        <Phone src={MINE} label="숏템메이커 완성본" sub="방금 눈앞에서 만든 영상" gold delay={8} loop={860} />
      </AbsoluteFill>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', paddingBottom: 90 }}>
        <div style={{ font: '900 110px ' + F.sans, color: C.gold, transform: 'scale(' + v + ') rotate(-6deg)', WebkitTextStroke: '4px #000', paintOrder: 'stroke fill', textShadow: '0 0 40px rgba(250,204,21,0.7), 0 12px 40px #000' }}>VS</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
const HEAD_SEC = 12.95;
export const V2_S47H_FRAMES = Math.round(HEAD_SEC * 30);
export const V2_S47H: React.FC<{ bgm?: boolean }> = ({ bgm = true }) => (
  <AbsoluteFill style={{ background: C.ink }}>
    <Audio src={staticFile('shottem2/v2s47h/voice.mp3')} />
    {bgm ? <Audio src={staticFile('shottem2/v2bgm/epic.mp3')} loop volume={0.11} /> : null}
    <V2_Compare />
    <WordCaption k="47h" />
    <Grain opacity={0.1} />
  </AbsoluteFill>
);
