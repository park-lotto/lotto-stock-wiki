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

const Monitor: React.FC<{ s: S4Scene; k: string }> = ({ s, k }) => {
  const f = useCurrentFrame();
  const t = f / FPS;
  // 카메라는 0.5초 앞뒤를 평균해 덜컹이지 않게
  const cams = [-0.5, -0.25, 0, 0.25, 0.5].map((d) => camAt(s, Math.max(0, t + d)));
  const cam = { x: cams.reduce((a, c) => a + c.x, 0) / 5, y: cams.reduce((a, c) => a + c.y, 0) / 5, z: cams.reduce((a, c) => a + c.z, 0) / 5 };
  const lastCut = [...s.cuts].reverse().find((c) => c <= t) ?? 0;
  const pf = Math.round((t - lastCut) * FPS);
  const punch = lastCut > 0 ? 1 + 0.04 * Math.max(0, 1 - pf / 8) : 1;
  const enter = spring({ frame: f, fps: FPS, config: { damping: 16 } });
  const W = 1640, H = 922;
  const ox = (0.5 - cam.x) * W * (cam.z - 1), oy = (0.5 - cam.y) * H * (cam.z - 1);
  const clampX = (W * (cam.z - 1)) / 2, clampY = (H * (cam.z - 1)) / 2;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', paddingBottom: 40 }}>
      <div style={{ width: W, height: H, borderRadius: 22, overflow: 'hidden', position: 'relative',
        border: '2px solid rgba(250,204,21,0.45)', boxShadow: '0 30px 90px rgba(0,0,0,0.75), 0 0 60px rgba(250,204,21,0.12)',
        transform: `scale(${(0.9 + 0.1 * enter) * punch})`, opacity: enter }}>
        <div style={{ position: 'absolute', inset: 0, transform: `translate(${Math.max(-clampX, Math.min(clampX, ox))}px, ${Math.max(-clampY, Math.min(clampY, oy))}px) scale(${cam.z})` }}>
          <OffthreadVideo src={staticFile(`shottem2/v2s4/${k}/rec.mp4`)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        {lastCut > 0 && pf < 5 ? <AbsoluteFill style={{ background: 'white', opacity: 0.18 * (1 - pf / 5) }} /> : null}
      </div>
    </AbsoluteFill>
  );
};

const Chip: React.FC<{ text: string; n: number }> = ({ text, n }) => {
  const f = useCurrentFrame();
  const p = spring({ frame: f, fps: FPS, config: { damping: 14, mass: 0.6 } });
  const out = interpolate(f, [FPS * 3.2, FPS * 3.6], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ padding: '46px 70px', pointerEvents: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, transform: `translateX(${(1 - p) * -80}px)`, opacity: p * out }}>
        <div style={{ fontFamily: F.mono, fontSize: 30, fontWeight: 700, color: C.ink, background: C.gold, borderRadius: 10, padding: '4px 14px' }}>{String(n).padStart(2, '0')}</div>
        <div style={{ fontFamily: F.sans, fontSize: 44, fontWeight: 900, color: 'white', textShadow: '0 4px 18px rgba(0,0,0,0.9)', background: 'rgba(11,13,16,0.72)', borderRadius: 12, padding: '6px 22px', borderLeft: `6px solid ${C.gold}` }}>{text}</div>
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
      {s.punches.map(([at, text, accent], i) => (
        <Sequence key={'p' + i} from={Math.round(at * FPS)} durationInFrames={Math.round(2.4 * FPS)}>
          <Punch text={text} accent={accent} />
          <Audio src={staticFile('sfx/sting_hit.mp3')} volume={0.55} />
        </Sequence>
      ))}
      {s.cuts.slice(1).map((c, i) => (
        <Sequence key={'x' + i} from={Math.max(0, Math.round(c * FPS) - 3)} durationInFrames={20}>
          <Audio src={staticFile('sfx/sting_whoosh.mp3')} volume={0.22} />
        </Sequence>
      ))}
      <WordCaption k={'s4' + k} />
      <Audio src={staticFile(`shottem2/v2s4/${k}/voice.mp3`)} />
      {bgm ? <Audio src={staticFile(BGM)} loop volume={0.08} /> : null}
      <Grain opacity={0.08} />
    </AbsoluteFill>
  );
};
