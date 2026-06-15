/**
 * L30 Design System — LIFE 3.0 Pictures 스타일 벤치마크
 *
 * 기준 영상: https://youtu.be/kI1soqlxwl8
 * 특징: 순수 블랙 + 라임 그린 액센트 + 골드 PiP + HUD 챕터 레이블
 */

// ── 컬러 팔레트 ────────────────────────────────────────────────────────────────
export const L30C = {
  // Backgrounds
  bg:           '#000000',
  bgCard:       'rgba(0,0,0,0.88)',

  // Accent — Lime Green (핵심 액센트)
  lime:         '#AAFF00',
  limeDim:      'rgba(170,255,0,0.45)',
  limeFaint:    'rgba(170,255,0,0.10)',
  limeBorder:   'rgba(170,255,0,0.65)',

  // Text
  white:        '#FFFFFF',
  textDim:      'rgba(255,255,255,0.55)',

  // PiP border — Gold/Amber (아바타 PiP 테두리)
  pipGold:      '#C8921A',

  // Chart bars
  barFill:      '#1C1C1C',
  barBorder:    '#303030',

  // Typography
  fontMain: '"Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif',
  fontMono: '"Courier New","Consolas","Lucida Console",monospace',
} as const;

// ── 글로우 프리셋 ───────────────────────────────────────────────────────────────
export const L30G = {
  lime: {
    text:   '0 0 8px rgba(170,255,0,0.85)',
    boxWk:  '0 0 8px rgba(170,255,0,0.30)',
    box:    '0 0 14px rgba(170,255,0,0.50), 0 0 32px rgba(170,255,0,0.15)',
    filter: 'drop-shadow(0 0 5px rgba(170,255,0,0.65))',
  },
  gold: {
    box:    '0 0 12px rgba(200,146,26,0.55), 0 0 28px rgba(200,146,26,0.20)',
  },
} as const;

// ── 캔버스 ─────────────────────────────────────────────────────────────────────
export const L30V = {
  W:   1920,
  H:   1080,
  PAD: 44,   // 좌우 패딩
} as const;

// ── 공통 헬퍼 ──────────────────────────────────────────────────────────────────
export const clamp = (
  f: number, a: number, b: number, va = 0, vb = 1,
) => {
  if (f <= a) return va;
  if (f >= b) return vb;
  return va + (vb - va) * (f - a) / (b - a);
};

// ── 공통 스타일 ────────────────────────────────────────────────────────────────
export const hudLabel: React.CSSProperties = {
  fontFamily:    L30C.fontMono,
  fontSize:      11,
  fontWeight:    400,
  letterSpacing: '3px',
  textTransform: 'uppercase',
  color:         L30C.lime,
} as const;

export const cardBase: React.CSSProperties = {
  background:    L30C.bgCard,
  border:        `1.5px solid ${L30C.limeBorder}`,
  borderRadius:  4,
  backdropFilter:'blur(8px)',
} as const;

import React from 'react';
