import React from 'react';
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { Grain } from './fx';
import { C, F } from './theme2';
import { WordCaption } from './V2_Fx2';
import { CAP } from './V2_Captions';
import { V3W } from './V2_V3Words';

Object.assign(CAP, V3W);

/* 숏템메이커 V2 광고 맨 끝 — V3 예고(커밍순).
   영상 찾기부터 완성까지 AI 혼자 만든 쇼츠(Paragon 3편 밍밍)를 보여 주고 V3 로 기대감을 남긴다. 내레이션 없음. */

const SRC = 'shottem2/v3t/clean.mp4';  // 원본 쇼츠에서 제목띠·자막띠·워터마크를 잘라내고 글자 없는 구간만 이은 것
const A_SEC = 12.3;
export const V3T_FRAMES = Math.round((A_SEC + 13.0 + 1.2) * 30);
const LINES: [number, string, boolean?][] = [
  [2.6, '이 쇼츠,'],
  [4.6, '영상 찾기부터'],
  [5.8, '대본 · 장면 · 성우 · 편집까지'],
  [9.3, '처음부터 끝까지'],
  [10.6, '혼자 만든 영상', true],
];

const Line: React.FC<{ at: number; text: string; gold?: boolean }> = ({ at, text, gold }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f - at * fps, fps, config: { damping: 14, mass: 0.6 } });
  return (
    <div style={{ font: (gold ? '900 64px ' : '800 52px ') + F.sans, color: gold ? C.gold : '#fff', opacity: p, transform: 'translateX(' + (1 - p) * -60 + 'px)',
      textShadow: '0 6px 24px rgba(0,0,0,0.9)', lineHeight: 1.25 }}>{text}</div>
  );
};

const Shorts: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 16 } });
  const out = interpolate(f, [(A_SEC - 0.6) * fps, A_SEC * fps], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const W = 700;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <OffthreadVideo src={staticFile(SRC)} muted style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(30px) brightness(0.3)', transform: 'scale(1.15)' }} />
      <AbsoluteFill style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 90 }}>
        <div style={{ width: 760, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 14, textAlign: 'right' }}>
          {LINES.map(([at, t, g], i) => <Line key={i} at={at} text={t} gold={g} />)}
        </div>
        <div style={{ width: W, height: W, borderRadius: 30, overflow: 'hidden', background: '#000', transform: 'scale(' + (0.88 + p * 0.12) + ')', opacity: p,
          boxShadow: '0 0 0 5px ' + C.gold + ', 0 0 90px rgba(250,204,21,0.45), 0 40px 100px rgba(0,0,0,0.9)' }}>
          <OffthreadVideo src={staticFile(SRC)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        <div style={{ width: 160 }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Coming: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = spring({ frame: f, fps, config: { damping: 10, mass: 0.8 } });
  const b = spring({ frame: f - 1.2 * fps, fps, config: { damping: 14 } });
  const glow = 0.5 + Math.sin(f / 8) * 0.25;
  return (
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse at 50% 45%, #2a2208 0%, #05060a 70%)', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
      <div style={{ font: '700 40px ' + F.sans, color: 'rgba(255,255,255,0.8)', opacity: a }}>다음 진화</div>
      <div style={{ font: '900 190px ' + F.sans, color: C.gold, transform: 'scale(' + (1.4 - 0.4 * a) + ')', opacity: Math.min(1, a * 1.5), letterSpacing: -4,
        textShadow: '0 0 ' + (50 + glow * 50) + 'px rgba(250,204,21,' + glow + '), 0 12px 40px #000' }}>숏템메이커 V3</div>
      <div style={{ font: '900 64px ' + F.mono, color: '#fff', letterSpacing: 18, opacity: b, transform: 'translateY(' + (1 - b) * 30 + 'px)' }}>COMING SOON</div>
    </AbsoluteFill>
  );
};

export const V2_V3Teaser: React.FC<{ bgm?: boolean }> = ({ bgm = true }) => (
  <AbsoluteFill style={{ background: '#05060a' }}>
    <Sequence durationInFrames={Math.round(A_SEC * 30)}>
      <Shorts />
      <Audio src={staticFile('shottem2/v3t/v3t_a.mp3')} />
      <WordCaption k="v3a" />
    </Sequence>
    <Sequence from={Math.round(A_SEC * 30)}>
      <Coming />
      <Audio src={staticFile('sfx/impact.mp3')} volume={0.5} />
      <Audio src={staticFile('shottem2/v3t/v3t_b.mp3')} />
      <WordCaption k="v3b" />
    </Sequence>
    {bgm ? <Audio src={staticFile('shottem2/v2bgm/epic.mp3')} loop volume={(f) => (f < A_SEC * 30 ? 0.06 : 0.1)} /> : null}
    <Grain opacity={0.08} />
  </AbsoluteFill>
);
