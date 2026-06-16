/**
 * ClaudeLiveShared — Claude Live 시리즈 공유 컴포넌트
 * Opus가 설계한 S5 디자인 시스템 추출 → 모든 씬에서 재사용
 *
 * 사용법:
 *   import { Background, PresenterWindow, TopBar, SubtitleBar,
 *            CL, SERIF, SANS, ci, sp, hexToRgb, blend } from './ClaudeLiveShared';
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, interpolate, spring, staticFile } from 'remotion';

// ── Claude CI/BI 팔레트 (고정)
export const CL = {
  coral:     '#D97757',
  coralDeep: '#BE5D3A',
  coralSoft: '#E89B7D',
  cream:     '#F0EEE6',
  bone:      '#FAF9F5',
  warmDark:  '#1F1E1D',
  warmDark2: '#141413',
  ink:       '#1F1E1D',
  onDark:    '#F0EEE6',
  muted:     '#9A938A',
  cardDark:  'rgba(20,19,19,0.88)',
  cardCream: 'rgba(244,242,236,0.97)',
};

export const SERIF = "Fraunces, 'Noto Serif KR', Georgia, serif";
export const SANS  = "Pretendard, 'Noto Sans KR', sans-serif";

// ── 헬퍼
export const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

export const sp = (f: number, from: number, damp = 11, stiff = 260, mass = 0.7) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping: damp, stiffness: stiff, mass } });

export const hexToRgb = (h: string) => {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

export const blend = (h1: string, h2: string, t: number) => {
  const a = hexToRgb(h1), b = hexToRgb(h2);
  return `rgb(${Math.round(a[0]+(b[0]-a[0])*t)},${Math.round(a[1]+(b[1]-a[1])*t)},${Math.round(a[2]+(b[2]-a[2])*t)})`;
};

// ── Claude 로고
export const ClaudeLogo: React.FC<{ size?: number }> = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 46 46">
    <rect width="46" height="46" rx="11" fill={CL.coral} />
    <rect x="10" y="10" width="6.5" height="26" rx="3.25" fill={CL.bone} />
    <rect x="19.75" y="10" width="6.5" height="26" rx="3.25" fill={CL.bone} />
    <rect x="29.5" y="10" width="6.5" height="26" rx="3.25" fill={CL.bone} />
  </svg>
);

// ════════════════════════════════
//  Background — 부유 blob 배경
// ════════════════════════════════
interface BgProps { f: number; accent: string }
export const Background: React.FC<BgProps> = ({ f, accent }) => {
  const blob = (cx: number, cy: number, col: string, r: number, ax: number, ay: number, ph: number, op: number) => {
    const x = cx + Math.sin(f * 0.012 + ph) * ax;
    const y = cy + Math.cos(f * 0.010 + ph) * ay;
    return (
      <div style={{
        position: 'absolute', left: x - r, top: y - r, width: r * 2, height: r * 2,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${col} 0%, transparent 65%)`,
        filter: 'blur(70px)', opacity: op,
      }} />
    );
  };
  return (
    <AbsoluteFill style={{ background: `linear-gradient(155deg, ${CL.warmDark} 0%, ${CL.warmDark2} 100%)` }}>
      {blob(420,  320, CL.coral,    560, 90, 70, 0.0, 0.34)}
      {blob(1540, 760, accent,      520, 110,80, 2.1, 0.28)}
      {blob(1180, 220, CL.coralSoft,420, 70, 60, 4.0, 0.16)}
      {blob(300,  900, accent,      440, 80, 60, 1.2, 0.14)}
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.34) 100%)' }} />
    </AbsoluteFill>
  );
};

// ════════════════════════════════
//  PresenterWindow — 발표자 윈도우 (좌측 1120×630)
// ════════════════════════════════
interface WinProps { f: number; accent: string; videoSrc: string }
export const PresenterWindow: React.FC<WinProps> = ({ f, accent, videoSrc }) => {
  const X = 70, Y = 170, W = 1120, H = 630;
  const intro = sp(f, 4, 12, 200, 0.8);
  const float = Math.sin(f * 0.045) * 4;
  const scale = 0.96 + intro * 0.04;

  const dot = (corner: 0|1|2|3) => {
    const ang = f * 0.03 + (corner * Math.PI) / 2;
    const cx = (corner === 0 || corner === 3) ? -4 : W + 4;
    const cy = corner < 2 ? -4 : H + 4;
    const ox = Math.cos(ang) * 10, oy = Math.sin(ang) * 10;
    return (
      <div key={corner} style={{
        position: 'absolute', left: cx + ox - 5, top: cy + oy - 5,
        width: 10, height: 10, borderRadius: '50%',
        background: accent, boxShadow: `0 0 12px ${accent}`, opacity: 0.9,
      }} />
    );
  };

  return (
    <div style={{
      position: 'absolute', left: X, top: Y + float, width: W, height: H,
      transform: `scale(${scale})`, transformOrigin: 'center center',
      opacity: ci(f, 2, 18), zIndex: 30,
    }}>
      <div style={{ position: 'absolute', inset: -40, borderRadius: 28,
        background: `radial-gradient(circle, ${accent}44 0%, transparent 62%)`,
        filter: 'blur(24px)' }} />
      <div style={{ position: 'absolute', inset: 0, borderRadius: 20, overflow: 'hidden',
        border: `3px solid ${accent}`,
        boxShadow: `0 24px 60px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(255,255,255,0.06)`,
        background: CL.warmDark2 }}>
        <OffthreadVideo
          src={staticFile(videoSrc)}
          volume={0}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
        <div style={{ position: 'absolute', left: 18, bottom: 16,
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'rgba(20,19,19,0.72)', borderRadius: 8, padding: '7px 13px',
          backdropFilter: 'blur(6px)' }}>
          <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#E5484D',
            opacity: 0.6 + Math.sin(f * 0.2) * 0.4 }} />
          <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700,
            color: CL.onDark, letterSpacing: '0.08em' }}>CLAUDE</span>
        </div>
      </div>
      {([0,1,2,3] as const).map(c => dot(c))}
    </div>
  );
};

// ════════════════════════════════
//  TopBar — 진행 리본 + 챕터칩 + 로고
// ════════════════════════════════
interface Section { id: string; from: number; to: number; accent: string; chapter: string }
interface TopBarProps { f: number; accent: string; sections: Section[]; totalFrames: number }
export const TopBar: React.FC<TopBarProps> = ({ f, accent, sections, totalFrames }) => {
  const sec = sections.find(s => f >= s.from && f < s.to) ?? sections[sections.length - 1];
  const pct = ci(f, 0, totalFrames, 0, 100);
  const chipIn = sp(f, sec.from, 12, 240);
  const chipX  = (1 - chipIn) * -26;

  return (
    <>
      {/* 진행 리본 */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 5,
        background: 'rgba(240,238,230,0.08)', zIndex: 90 }}>
        <div style={{ height: '100%', width: `${pct}%`,
          background: `linear-gradient(90deg, ${CL.coral} 0%, ${accent} 100%)`,
          boxShadow: `0 0 8px ${accent}` }} />
      </div>
      {/* 챕터 칩 */}
      <div key={sec.id} style={{ position: 'absolute', top: 56, left: 70, zIndex: 90,
        opacity: ci(f, sec.from, sec.from + 10), transform: `translateX(${chipX}px)` }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12,
          background: 'rgba(20,19,19,0.58)', backdropFilter: 'blur(6px)',
          borderRadius: 30, padding: '11px 22px', border: `1.5px solid ${accent}66` }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%',
            background: accent, boxShadow: `0 0 10px ${accent}` }} />
          <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700,
            color: CL.onDark, letterSpacing: '0.08em' }}>{sec.chapter}</span>
        </div>
      </div>
      {/* 로고 */}
      <div style={{ position: 'absolute', top: 50, right: 44, zIndex: 90,
        display: 'flex', alignItems: 'center', gap: 12, opacity: ci(f, 6, 24) }}>
        <span style={{ fontFamily: SERIF, fontSize: 26, fontWeight: 600, color: CL.onDark }}>Claude</span>
        <ClaudeLogo size={40} />
      </div>
    </>
  );
};

// ════════════════════════════════
//  SubtitleBar — 키네틱 세리프 자막 (하단 16%)
// ════════════════════════════════
interface Sub { from: number; to: number; text: string; accent: string }
interface SubProps { f: number; accent: string; subs: Sub[] }
export const SubtitleBar: React.FC<SubProps> = ({ f, accent, subs }) => {
  const sub = subs.find(s => f >= s.from && f < s.to);
  if (!sub) return null;
  const barOp = Math.min(ci(f, sub.from, sub.from + 7), ci(f, sub.to - 6, sub.to, 1, 0));
  const accentWords = new Set((sub.accent ?? '').split(' '));
  const strip = (w: string) => w.replace(/[.,?!"""]/g, '');

  const lines = sub.text.split('\n');
  let wi = 0;
  return (
    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
      background: 'linear-gradient(0deg, rgba(20,19,19,0.95) 0%, rgba(20,19,19,0.82) 55%, transparent 100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '0 140px', opacity: barOp, zIndex: 80, gap: 4 }}>
      {lines.map((line, li) => (
        <div key={li} style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 14px' }}>
          {line.split(' ').map((word) => {
            const delay = sub.from + wi * 2; wi++;
            const o = ci(f, delay, delay + 8);
            const y = (1 - sp(f, delay, 12, 260)) * 14;
            const isAcc = accentWords.has(strip(word));
            return (
              <span key={`${li}-${wi}`} style={{
                fontFamily: SERIF, fontSize: 44, fontWeight: 700,
                color: isAcc ? accent : CL.onDark,
                opacity: o, transform: `translateY(${y}px)`, display: 'inline-block',
                textShadow: '0 2px 10px rgba(0,0,0,0.8)',
                borderBottom: isAcc ? `3px solid ${accent}` : 'none',
                lineHeight: 1.35, paddingBottom: 2,
              }}>{word}</span>
            );
          })}
        </div>
      ))}
    </div>
  );
};
