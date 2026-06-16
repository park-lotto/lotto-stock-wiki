import { interpolate, spring } from 'remotion';

// ── 색상 ──
export const LIME   = '#AAFF00';
export const LIME50 = 'rgba(170,255,0,0.5)';
export const LIME20 = 'rgba(170,255,0,0.2)';
export const CARD   = 'rgba(0,0,0,0.84)';
export const BORDER = 'rgba(170,255,0,0.45)';
export const RED    = '#FF4455';
export const RED20  = 'rgba(255,68,85,0.2)';

// ── 애니메이션 헬퍼 ──
export const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

export const sp = (f: number, from: number, damping = 9, stiffness = 270, mass = 0.7) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping, stiffness, mass } });

export const panelOp = (f: number, start: number, end: number) =>
  ci(f, start, start + 20) * ci(f, end - 16, end, 1, 0);

export const slideX = (f: number, start: number, dir: 1 | -1) =>
  dir * (1 - sp(f, start)) * 40;

// ── 공통 스타일 ──
export const panelStyle = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'absolute',
  background: CARD,
  border: `1.5px solid ${BORDER}`,
  borderRadius: 6,
  overflow: 'hidden',
  ...extra,
});

export const kickerStyle: React.CSSProperties = {
  fontFamily: "'Courier New', monospace",
  fontSize: 10,
  color: LIME,
  letterSpacing: 3,
  textTransform: 'uppercase',
  padding: '12px 18px 10px',
  borderBottom: `1px solid ${LIME20}`,
};
