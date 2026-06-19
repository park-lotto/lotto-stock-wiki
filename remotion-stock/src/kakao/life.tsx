/**
 * kakao/life.tsx — LIFE 3.0 PICTURES 디자인 시스템 컴포넌트
 *
 * 레퍼런스(C:\Users\TheRose\Desktop\레퍼런스) 기반 공용 비주얼 부품.
 * DESIGN.md 의 규칙을 코드로 구현. 모든 KK_* 씬이 공유.
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile } from 'remotion';
import { cl, pop } from './fx';

// ── 색상 토큰 ──
export const ORANGE = '#D97757';
export const ORANGE_GLOW = 'rgba(217,119,87,0.55)';
export const LIME = '#AAFF00';
export const LIME_GLOW = 'rgba(170,255,0,0.55)';
export const GREEN = '#7CFF00';
export const RED = '#FF4455';
export const SUB = 'rgba(255,255,255,0.6)';

const KFONT = "'Noto Sans KR', sans-serif";
const MONO = "'Space Mono', 'Roboto Mono', monospace";
const NUM = "'Archivo', 'Noto Sans KR', sans-serif";
const SERIF = "'Fraunces', serif";

// ─────────────────────────────────────────────────────────────
//  무대 배경 (모드 C / 공용)
// ─────────────────────────────────────────────────────────────
export const Stage: React.FC<{ children?: React.ReactNode; baseline?: boolean }> = ({
  children,
  baseline = true,
}) => (
  <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 38%, #0d1410 0%, #000 72%)', fontFamily: KFONT }}>
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundImage:
          'linear-gradient(rgba(170,255,0,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(170,255,0,0.04) 1px, transparent 1px)',
        backgroundSize: '64px 64px',
      }}
    />
    {children}
    {baseline && (
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: RED, boxShadow: `0 0 12px ${RED}` }} />
    )}
  </AbsoluteFill>
);

// ─────────────────────────────────────────────────────────────
//  키커 레이블 (좌상단) — "CH 05 · THE SCALE"
// ─────────────────────────────────────────────────────────────
export const Kicker: React.FC<{ ch: string; title: string; color?: string; f?: number }> = ({
  ch,
  title,
  color = LIME,
  f = 99,
}) => (
  <div style={{ position: 'absolute', top: 44, left: 56, opacity: cl(f, 4, 20), fontFamily: MONO, fontSize: 17, letterSpacing: 5 }}>
    <span style={{ color: SUB }}>{ch} · </span>
    <span style={{ color, textShadow: `0 0 10px ${color}` }}>{title}</span>
  </div>
);

// ─────────────────────────────────────────────────────────────
//  채널 워터마크 (우하단)
// ─────────────────────────────────────────────────────────────
export const Watermark: React.FC<{ dark?: boolean }> = ({ dark = false }) => (
  <div
    style={{
      position: 'absolute',
      bottom: 28,
      right: 40,
      fontFamily: MONO,
      fontSize: 16,
      letterSpacing: 3,
      fontWeight: 700,
      color: dark ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.4)',
    }}
  >
    STOCK<span style={{ color: dark ? ORANGE : LIME }}>BRAIN</span>
  </div>
);

// ─────────────────────────────────────────────────────────────
//  Claude 아이콘 (오렌지 둥근사각 + 흰 별빛)
// ─────────────────────────────────────────────────────────────
export const ClaudeIcon: React.FC<{ size?: number; glow?: boolean }> = ({ size = 64, glow = true }) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: size * 0.22,
      background: ORANGE,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: glow ? `0 0 ${size * 0.6}px ${ORANGE_GLOW}` : 'none',
      flexShrink: 0,
    }}
  >
    <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 24 24" fill="none">
      {Array.from({ length: 12 }).map((_, i) => {
        const a = (i * 30 * Math.PI) / 180;
        return (
          <rect
            key={i}
            x={11.2}
            y={2.5}
            width={1.6}
            height={9}
            rx={0.8}
            fill="white"
            transform={`rotate(${i * 30} 12 12)`}
            opacity={0.55 + 0.45 * Math.abs(Math.cos(a))}
          />
        );
      })}
    </svg>
  </div>
);

// ─────────────────────────────────────────────────────────────
//  와이어 글로브 (배경 ambient)
// ─────────────────────────────────────────────────────────────
export const WireGlobe: React.FC<{ x?: string; y?: string; size?: number; f?: number; color?: string }> = ({
  x = '72%',
  y = '46%',
  size = 620,
  f = 0,
  color = LIME,
}) => {
  const rot = (f * 0.25) % 360;
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: size, height: size, transform: 'translate(-50%,-50%)', opacity: 0.28, pointerEvents: 'none' }}>
      <svg width={size} height={size} viewBox="0 0 200 200">
        <circle cx={100} cy={100} r={92} fill="none" stroke={color} strokeWidth={0.5} opacity={0.5} />
        {/* 위도 */}
        {[-60, -30, 0, 30, 60].map((lat) => {
          const ry = 92 * Math.cos((lat * Math.PI) / 180);
          return <ellipse key={lat} cx={100} cy={100 + lat * 0.9} rx={ry} ry={ry * 0.28} fill="none" stroke={color} strokeWidth={0.4} opacity={0.4} />;
        })}
        {/* 경도 (회전) */}
        <g transform={`rotate(${rot} 100 100)`}>
          {[0, 36, 72, 108, 144].map((lon) => (
            <ellipse key={lon} cx={100} cy={100} rx={92 * Math.abs(Math.cos((lon * Math.PI) / 180)) * 0.4 + 8} ry={92} fill="none" stroke={color} strokeWidth={0.4} opacity={0.35} />
          ))}
        </g>
        {/* 점 패턴 */}
        {Array.from({ length: 60 }).map((_, i) => {
          const a = (i * 47) % 360;
          const r = 88 * Math.sqrt(((i * 13) % 100) / 100);
          const cx = 100 + r * Math.cos((a * Math.PI) / 180);
          const cy = 100 + r * Math.sin((a * Math.PI) / 180) * 0.95;
          return <circle key={i} cx={cx} cy={cy} r={0.9} fill={color} opacity={0.5} />;
        })}
      </svg>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
//  플로팅 인포 카드 (모드 A — AI 호스트 위 모서리)
// ─────────────────────────────────────────────────────────────
export const FloatCard: React.FC<{
  kicker: string;
  accent?: string;
  style?: React.CSSProperties;
  f: number;
  at: number;
  children: React.ReactNode;
}> = ({ kicker, accent = LIME, style, f, at, children }) => {
  const p = pop(f, at, { damping: 9 });
  const op = cl(f, at, at + 14);
  return (
    <div
      style={{
        position: 'absolute',
        background: 'rgba(0,0,0,0.66)',
        border: `1px solid ${accent}`,
        borderRadius: 10,
        backdropFilter: 'blur(8px)',
        padding: '16px 20px',
        opacity: op,
        transform: `translateY(${(1 - p) * 24}px)`,
        boxShadow: `0 0 24px rgba(0,0,0,0.5)`,
        ...style,
      }}
    >
      <div style={{ fontFamily: MONO, fontSize: 13, letterSpacing: 3, color: accent, marginBottom: 10, textShadow: `0 0 8px ${accent}` }}>
        {kicker}
      </div>
      {children}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
//  거대 수치 (모드 C)
// ─────────────────────────────────────────────────────────────
export const BigStat: React.FC<{
  value: string;
  unit?: string;
  numColor?: string;
  unitColor?: string;
  size?: number;
  f: number;
  at: number;
}> = ({ value, unit, numColor = '#fff', unitColor = ORANGE, size = 180, f, at }) => {
  const p = pop(f, at, { damping: 8, stiffness: 200 });
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, transform: `scale(${0.6 + p * 0.4})`, opacity: cl(f, at, at + 12) }}>
      <span style={{ fontFamily: NUM, fontWeight: 900, fontSize: size, color: numColor, letterSpacing: -4, lineHeight: 1, textShadow: `0 0 50px rgba(255,255,255,0.2)` }}>
        {value}
      </span>
      {unit && (
        <span style={{ fontFamily: NUM, fontWeight: 800, fontSize: size * 0.34, color: unitColor, textShadow: `0 0 30px ${unitColor}` }}>{unit}</span>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
//  로어서드 (모드 A — 채널명 + 이탤릭 태그)
// ─────────────────────────────────────────────────────────────
export const LowerThird: React.FC<{ tagline?: string; accent?: string; f: number; at: number }> = ({
  tagline,
  accent = LIME,
  f,
  at,
}) => {
  const p = pop(f, at, { damping: 10 });
  return (
    <div style={{ position: 'absolute', left: 64, bottom: 220, opacity: cl(f, at, at + 16), transform: `translateY(${(1 - p) * 26}px)` }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 14, padding: '14px 24px', background: 'rgba(0,0,0,0.62)', borderLeft: `4px solid ${accent}`, borderRadius: '0 10px 10px 0', backdropFilter: 'blur(6px)' }}>
        <div style={{ fontSize: 34, fontWeight: 900, color: '#fff', letterSpacing: -1 }}>
          STOCK<span style={{ color: accent, textShadow: `0 0 20px ${accent}` }}>BRAIN</span>
        </div>
      </div>
      {tagline && (
        <div style={{ marginTop: 12, fontFamily: SERIF, fontStyle: 'italic', fontSize: 30, color: 'rgba(255,255,255,0.78)', paddingLeft: 6 }}>
          {tagline}
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
//  브라우저 프레임 (모드 B — 화면녹화를 밝게 담는 창)
// ─────────────────────────────────────────────────────────────
export const BrowserFrame: React.FC<{
  src: string;
  scale?: number;
  top?: number;
  accent?: string;
}> = ({ src, scale = 0.78, top = 132, accent = LIME }) => {
  const w = 1920 * scale;
  const h = 1080 * scale;
  return (
    <div
      style={{
        position: 'absolute',
        top,
        left: '50%',
        transform: 'translateX(-50%)',
        width: w,
        borderRadius: 16,
        overflow: 'hidden',
        border: `2px solid ${accent}`,
        boxShadow: `0 24px 70px rgba(0,0,0,0.7), 0 0 40px ${accent}33`,
        background: '#111',
      }}
    >
      {/* 창 상단바 */}
      <div style={{ height: 38, background: 'linear-gradient(#2a2a2e,#1d1d20)', display: 'flex', alignItems: 'center', paddingLeft: 16, gap: 8 }}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#ff5f57' }} />
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#febc2e' }} />
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#28c840' }} />
        <div style={{ marginLeft: 16, fontFamily: MONO, fontSize: 13, color: 'rgba(255,255,255,0.4)' }}>claude.ai · STOCKBRAIN tutorial</div>
      </div>
      {/* 화면녹화 (밝게, dim 없음) */}
      <OffthreadVideo src={staticFile(src)} style={{ width: w, height: h, display: 'block' }} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
//  STEP 상단 바 (모드 B — 큰 단계 표시)
// ─────────────────────────────────────────────────────────────
export const StepBar: React.FC<{
  step: number;
  total: number;
  label: string;
  f: number;
  accent?: string;
}> = ({ step, total, label, f, accent = LIME }) => (
  <div style={{ position: 'absolute', top: 40, left: 56, right: 56, display: 'flex', alignItems: 'center', gap: 24, opacity: cl(f, 0, 16) }}>
    <div style={{ fontFamily: NUM, fontSize: 52, fontWeight: 900, color: accent, textShadow: `0 0 24px ${accent}`, lineHeight: 1 }}>
      {String(step).padStart(2, '0')}
      <span style={{ fontSize: 24, color: SUB }}>/{String(total).padStart(2, '0')}</span>
    </div>
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 38, fontWeight: 800, color: '#fff', letterSpacing: -1 }}>{label}</div>
      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 2,
              background: i < step ? accent : 'rgba(255,255,255,0.14)',
              boxShadow: i < step ? `0 0 8px ${accent}` : 'none',
            }}
          />
        ))}
      </div>
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
//  여백 콜아웃 (모드 B — 화면 밖에서 가리킴)
// ─────────────────────────────────────────────────────────────
export const MarginCallout: React.FC<{
  text: string;
  side: 'left' | 'right' | 'bottom';
  top?: number;
  f: number;
  at: number;
  accent?: string;
}> = ({ text, side, top = 400, f, at, accent = RED }) => {
  const p = pop(f, at, { damping: 8 });
  const arrow = side === 'left' ? '→' : side === 'right' ? '←' : '↑';
  const pos: React.CSSProperties =
    side === 'left'
      ? { left: 40, top }
      : side === 'right'
      ? { right: 40, top }
      : { left: '50%', bottom: 200, transform: `translateX(-50%) scale(${0.8 + p * 0.2})` };
  return (
    <div
      style={{
        position: 'absolute',
        ...pos,
        transform: side === 'bottom' ? pos.transform : `scale(${0.8 + p * 0.2})`,
        opacity: cl(f, at, at + 12),
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '14px 24px',
        background: 'rgba(0,0,0,0.85)',
        border: `2px solid ${accent}`,
        borderRadius: 12,
        boxShadow: `0 0 24px ${accent}66`,
        fontSize: 30,
        fontWeight: 800,
        color: '#fff',
        whiteSpace: 'nowrap',
      }}
    >
      {side !== 'left' && <span style={{ color: accent, fontSize: 34 }}>{arrow}</span>}
      {text}
      {side === 'left' && <span style={{ color: accent, fontSize: 34 }}>{arrow}</span>}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
//  자막 바 (공용 — 라임 강조)
// ─────────────────────────────────────────────────────────────
export const LifeSubBar: React.FC<{ f: number; subs: { from: number; to: number; text: string; accent: string }[] }> = ({ f, subs }) => {
  const active = subs.find((s) => f >= s.from && f < s.to);
  if (!active) return null;
  const local = f - active.from;
  const op = cl(local, 0, 6);
  const y = (1 - cl(local, 0, 7)) * 14;
  return (
    <div style={{ position: 'absolute', bottom: 26, left: 0, right: 0, display: 'flex', justifyContent: 'center' }}>
      <div
        style={{
          fontFamily: KFONT,
          fontSize: 48,
          fontWeight: 700,
          color: '#fff',
          textAlign: 'center',
          padding: '14px 40px',
          maxWidth: '84%',
          lineHeight: 1.35,
          textShadow: '0 2px 20px rgba(0,0,0,1)',
          opacity: op,
          transform: `translateY(${y}px)`,
        }}
      >
        {active.text.split(active.accent).map((part, i, arr) => (
          <React.Fragment key={i}>
            {part}
            {i < arr.length - 1 && active.accent && (
              <span style={{ color: LIME, textShadow: `0 0 16px ${LIME_GLOW}` }}>{active.accent}</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
