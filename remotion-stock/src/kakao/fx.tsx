/**
 * kakao/fx.tsx — 카카오EP1 공통 효과 모듈
 *
 * 모션 헬퍼 + 오디오(SFX) + 재사용 컴포넌트.
 * 모든 KK_* 씬이 이 어휘를 공유해 톤을 통일한다.
 */

import React from 'react';
import { Audio, Sequence, interpolate, spring, staticFile, Easing } from 'remotion';
import { LIME, LIME50 } from './theme';

const FPS = 30;

// ─────────────────────────────────────────────────────────────
//  모션 헬퍼
// ─────────────────────────────────────────────────────────────

/** clamp interpolate */
export const cl = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

/** 카드·아이콘 등장 스프링 (0→1) */
export const pop = (
  f: number,
  start: number,
  cfg: { damping?: number; stiffness?: number; mass?: number } = {},
) =>
  spring({
    frame: Math.max(0, f - start),
    fps: FPS,
    config: { damping: cfg.damping ?? 9, stiffness: cfg.stiffness ?? 260, mass: cfg.mass ?? 0.7 },
  });

/** 텍스트 줄 등장: { opacity, y } */
export const riseFade = (f: number, start: number, dur = 14, dist = 18) => {
  const p = cl(f, start, start + dur);
  return { opacity: p, y: (1 - p) * dist };
};

/** 핵심 단어 줌 펀치: scale 1 → peak → 1 */
export const zoomPunch = (f: number, start: number, peak = 1.08, dur = 10) => {
  if (f < start || f > start + dur) return 1;
  const half = dur / 2;
  const up = cl(f, start, start + half, 1, peak);
  const down = cl(f, start + half, start + dur, peak, 1);
  return f < start + half ? up : down;
};

/** 경고·임팩트 쉐이크: { x, y } (감쇠) */
export const shake = (f: number, start: number, dur = 12, amp = 6) => {
  if (f < start || f > start + dur) return { x: 0, y: 0 };
  const decay = 1 - (f - start) / dur;
  return {
    x: Math.sin((f - start) * 4.2) * amp * decay,
    y: Math.cos((f - start) * 3.1) * amp * 0.5 * decay,
  };
};

/** 컷 전환 흰 플래시 (0→peak→0) */
export const flashAt = (f: number, start: number, dur = 6, peak = 0.6) =>
  interpolate(f, [start, start + dur * 0.3, start + dur], [0, peak, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });

/** 글리치 x 오프셋 (구간 내에서만) */
export const glitchX = (f: number, a: number, b: number, amp = 6) =>
  f >= a && f <= b ? Math.sin(f * 47) * amp : 0;

/** 타이핑: cps(초당 글자수) 기준 노출 substring */
export const typeReveal = (text: string, f: number, start: number, cps = 22) => {
  const n = Math.max(0, Math.floor(((f - start) / FPS) * cps));
  return text.slice(0, n);
};

/** 부드러운 ambient 펄스 (0.7~1.0) */
export const pulse = (f: number, speed = 0.08, base = 0.85, amp = 0.15) =>
  base + Math.sin(f * speed) * amp;

// ─────────────────────────────────────────────────────────────
//  오디오 (SFX)
// ─────────────────────────────────────────────────────────────

/** 특정 프레임에 효과음 1회 재생 */
export const Sfx: React.FC<{ at: number; file: string; vol?: number }> = ({ at, file, vol = 0.4 }) => (
  <Sequence from={at} durationInFrames={90} layout="none">
    <Audio src={staticFile(`sfx/${file}`)} volume={vol} />
  </Sequence>
);

// ─────────────────────────────────────────────────────────────
//  재사용 컴포넌트
// ─────────────────────────────────────────────────────────────

/** 클릭 위치 빨간 ripple — 화면녹화 클릭 포인트 강조 */
export const ClickPulse: React.FC<{ f: number; at: number; x: number; y: number; color?: string }> = ({
  f,
  at,
  x,
  y,
  color = '#FF4455',
}) => {
  if (f < at || f > at + 36) return null;
  const local = f - at;
  return (
    <>
      {[0, 12].map((d, i) => {
        const p = cl(f, at + d, at + d + 22);
        if (p <= 0 || p >= 1) return null;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: 12 + p * 70,
              height: 12 + p * 70,
              marginLeft: -(6 + p * 35),
              marginTop: -(6 + p * 35),
              borderRadius: '50%',
              border: `3px solid ${color}`,
              opacity: (1 - p) * 0.9,
              boxShadow: `0 0 18px ${color}`,
              pointerEvents: 'none',
            }}
          />
        );
      })}
      <div
        style={{
          position: 'absolute',
          left: x,
          top: y,
          width: 14,
          height: 14,
          marginLeft: -7,
          marginTop: -7,
          borderRadius: '50%',
          background: color,
          opacity: cl(local, 0, 6) * cl(local, 28, 36, 1, 0),
          boxShadow: `0 0 14px ${color}`,
          pointerEvents: 'none',
        }}
      />
    </>
  );
};

/** 상단 단계 진행바 — S7 같은 멀티스텝 씬용 */
export const StepProgress: React.FC<{
  steps: string[];
  current: number; // 0-based, 진행 중 인덱스
  f: number;
}> = ({ steps, current, f }) => (
  <div
    style={{
      position: 'absolute',
      top: 40,
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 22px',
      background: 'rgba(0,0,0,0.7)',
      border: `1px solid ${LIME50}`,
      borderRadius: 999,
      opacity: cl(f, 0, 20),
    }}
  >
    {steps.map((s, i) => {
      const done = i < current;
      const active = i === current;
      return (
        <React.Fragment key={i}>
          {i > 0 && (
            <div style={{ width: 26, height: 2, background: i <= current ? LIME : 'rgba(255,255,255,0.2)' }} />
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 11,
                fontWeight: 800,
                background: done || active ? LIME : 'rgba(255,255,255,0.08)',
                color: done || active ? '#000' : 'rgba(255,255,255,0.5)',
                boxShadow: active ? `0 0 14px ${LIME50}` : 'none',
              }}
            >
              {done ? '✓' : i + 1}
            </div>
            {active && (
              <span style={{ fontSize: 13, fontWeight: 700, color: '#fff', whiteSpace: 'nowrap' }}>{s}</span>
            )}
          </div>
        </React.Fragment>
      );
    })}
  </div>
);

/** 채널 로고 + 채널명 묶음 (스팅·아웃트로 공용) */
export const LogoLockup: React.FC<{ scale?: number; glow?: number }> = ({ scale = 1, glow = 0.6 }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 18 * scale, transform: `scale(${scale})` }}>
    <svg width={64} height={64} viewBox="0 0 46 46">
      <rect width="46" height="46" rx="12" fill="#D97757" />
      <rect x="10" y="10" width="7" height="26" rx="3.5" fill="white" />
      <rect x="19.5" y="10" width="7" height="26" rx="3.5" fill="white" />
      <rect x="29" y="10" width="7" height="26" rx="3.5" fill="white" />
    </svg>
    <div style={{ fontFamily: "'Noto Sans KR', sans-serif", fontWeight: 900, lineHeight: 1.05 }}>
      <div style={{ fontSize: 44, color: '#fff', letterSpacing: -1 }}>
        로또의 <span style={{ color: LIME, textShadow: `0 0 ${24 * glow}px rgba(170,255,0,${glow})` }}>주식</span>
      </div>
      <div style={{ fontSize: 20, color: 'rgba(255,255,255,0.55)', fontWeight: 500, letterSpacing: 6 }}>
        STOCK INSIGHT
      </div>
    </div>
  </div>
);

export type Sub = { from: number; to: number; text: string; accent: string };

/** 순수 Remotion 씬용 자막바 (SceneBase 미사용 씬) */
export const SubBar: React.FC<{ f: number; subs: Sub[] }> = ({ f, subs }) => {
  const active = subs.find((s) => f >= s.from && f < s.to);
  if (!active) return null;
  const local = f - active.from;
  const opacity = cl(local, 0, 6);
  const y = interpolate(local, [0, 7], [14, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '19%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.4) 55%, transparent 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: 40,
          fontWeight: 700,
          color: '#fff',
          textAlign: 'center',
          paddingInline: 90,
          maxWidth: '88%',
          lineHeight: 1.4,
          textShadow: '0 2px 18px rgba(0,0,0,0.98)',
          opacity,
          transform: `translateY(${y}px)`,
        }}
      >
        {active.text.split(active.accent).map((part, i, arr) => (
          <React.Fragment key={i}>
            {part}
            {i < arr.length - 1 && active.accent && (
              <span style={{ color: LIME, textShadow: `0 0 16px rgba(170,255,0,0.9)` }}>{active.accent}</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

/** 스캔라인 오버레이 (스팅 분위기) */
export const Scanlines: React.FC<{ opacity?: number }> = ({ opacity = 0.12 }) => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      pointerEvents: 'none',
      backgroundImage: 'repeating-linear-gradient(0deg, rgba(170,255,0,0.5) 0px, rgba(170,255,0,0.5) 1px, transparent 2px, transparent 4px)',
      opacity,
      mixBlendMode: 'screen',
    }}
  />
);

/** 중앙 방사 글로우 */
export const GlowOrb: React.FC<{ f: number; color?: string; size?: number }> = ({
  f,
  color = '170,255,0',
  size = 520,
}) => {
  const r = size + Math.sin(f * 0.05) * 40;
  const op = 0.06 + Math.sin(f * 0.06) * 0.03;
  return (
    <div
      style={{
        position: 'absolute',
        width: r,
        height: r,
        borderRadius: '50%',
        background: `radial-gradient(circle, rgba(${color},${op}) 0%, transparent 65%)`,
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
      }}
    />
  );
};
