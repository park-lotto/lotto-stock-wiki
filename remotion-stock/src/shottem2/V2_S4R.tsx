import React from 'react';
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { Backdrop } from './V2_Bg';
import { WordCaption } from './V2_Fx2';
import { CAP } from './V2_Captions';
import { Grain } from './fx';
import { C, F } from './theme2';
import { S4R, S4Scene } from './V2_S4Data';

/* 숏템메이커 V2 광고 — S4 시연 녹화 씬(사장님 화면 녹화 + 필재 음성).
   녹화본은 tools/v2s4/cut.py 가 음성 길이에 맞춰 컷 편집한 rec.mp4 하나.
   화면: 금빛 오로라 위 모니터 → 활동 지점으로 천천히 당겨 보기(작은 글자 읽히게) · 컷마다 살짝 펀치
   글자: 문단 머리 제목(왼쪽 위) · 강조 문구(가운데 크게) · 단어자막(아래) · 효과음 */

Object.assign(CAP, Object.fromEntries(Object.entries(S4R).map(([k, s]) => ['s4' + k, s.words])));

const FPS = 30;
const BGM = 'shottem2/v2bgm/epic.mp3';
export const s4Frames = (k: string) => Math.round(S4R[k].dur * FPS) + 15;

// 활동 지점 따라 당기기 — 1.5초 창으로 부드럽게, 움직임 클 때만 확대
const camAt = (s: S4Scene, t: number) => {
  let wx = 0, cx = 0, cy = 0, act = 0;
  for (const [ft, x, y, a] of s.focus) {
    const d = Math.abs(ft - t);
    if (d > 1.6) continue;
    const w = (1 - d / 1.6) * (0.2 + Math.min(a, 0.05) * 20);
    wx += w; cx += x * w; cy += y * w; act += a * (1 - d / 1.6);
  }
  if (wx === 0) return { x: 0.5, y: 0.5, z: 1 };
  cx /= wx; cy /= wx;
  const z = 1 + Math.min(0.45, act * 1.6) * (s.zoom ?? 1);
  return { x: cx, y: cy, z };
};

// 차분한 설명 녹화 — 확대·펀치 없이 녹화 화면 전체를 원래 비율(16:9) 그대로 보여 준다
const Monitor: React.FC<{ s: S4Scene; k: string }> = ({ k }) => {
  const f = useCurrentFrame();
  const enter = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const W = 1552, H = 873;
  return (
    <AbsoluteFill style={{ alignItems: 'center', paddingTop: 72 }}>
      <div style={{ width: W, height: H, borderRadius: 14, overflow: 'hidden', background: '#000',
        border: '2px solid rgba(250,204,21,0.45)', boxShadow: '0 20px 60px rgba(0,0,0,0.7)', opacity: enter }}>
        <OffthreadVideo src={staticFile(`shottem2/v2s4/${k}/rec.mp4`)} muted style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
      </div>
    </AbsoluteFill>
  );
};

const Chip: React.FC<{ text: string; n: number }> = ({ text, n }) => {
  const f = useCurrentFrame();
  const p = spring({ frame: f, fps: FPS, config: { damping: 14, mass: 0.6 } });
  const out = interpolate(f, [FPS * 3.2, FPS * 3.6], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ padding: '14px 184px', pointerEvents: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, transform: `translateX(${(1 - p) * -80}px)`, opacity: p * out }}>
        <div style={{ fontFamily: F.mono, fontSize: 24, fontWeight: 700, color: C.ink, background: C.gold, borderRadius: 10, padding: '4px 14px' }}>{String(n).padStart(2, '0')}</div>
        <div style={{ fontFamily: F.sans, fontSize: 32, fontWeight: 800, color: 'white', textShadow: '0 4px 18px rgba(0,0,0,0.9)', background: 'rgba(11,13,16,0.72)', borderRadius: 12, padding: '6px 22px', borderLeft: `6px solid ${C.gold}` }}>{text}</div>
      </div>
    </AbsoluteFill>
  );
};

const Punch: React.FC<{ text: string; accent?: string }> = ({ text, accent }) => {
  const f = useCurrentFrame();
  const p = spring({ frame: f, fps: FPS, config: { damping: 11, mass: 0.7 } });
  const out = interpolate(f, [FPS * 1.9, FPS * 2.3], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const parts = accent ? text.split(accent) : [text];
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, rgba(0,0,0,0.55), transparent 62%)', opacity: out }} />
      <div style={{ fontFamily: F.sans, fontWeight: 900, fontSize: 104, color: 'white', textAlign: 'center', lineHeight: 1.15, whiteSpace: 'pre-line',
        transform: `scale(${1.6 - 0.6 * p}) rotate(${(1 - p) * -4}deg)`, opacity: Math.min(1, p * 1.5) * out,
        textShadow: '0 8px 30px rgba(0,0,0,0.95), 0 0 2px black' }}>
        {parts.map((x, i) => (
          <React.Fragment key={i}>{x}{i < parts.length - 1 ? <span style={{ color: C.gold }}>{accent}</span> : null}</React.Fragment>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const V2_S4R: React.FC<{ k: string; bgm?: boolean }> = ({ k, bgm = true }) => {
  const s = S4R[k];
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      <Backdrop kind="aurora" seed={s.seed ?? 3} dim={0.55} />
      <Monitor s={s} k={k} />
      {s.chips.map(([at, text], i) => (
        <Sequence key={'c' + i} from={Math.round(at * FPS)} durationInFrames={Math.round(3.7 * FPS)}>
          <Chip text={text} n={i + 1} />
          <Audio src={staticFile('sfx/transition_swipe.mp3')} volume={0.45} />
        </Sequence>
      ))}
      <WordCaption k={'s4' + k} />
      <Audio src={staticFile(`shottem2/v2s4/${k}/voice.mp3`)} />
      {bgm ? <Audio src={staticFile(BGM)} loop volume={0.08} /> : null}
      <Grain opacity={0.08} />
    </AbsoluteFill>
  );
};
