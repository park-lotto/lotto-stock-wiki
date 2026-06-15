/**
 * L30_HUD — 항상 표시되는 챕터 레이블 + 타임코드
 *
 * 스타일: LIFE 3.0 Pictures
 *   좌상단: ● CH 01 · ORIGIN
 *   우상단: TIME 00:00 - 00:05
 *
 * 사용법:
 *   <L30_HUD chapter="01" title="HOOK" timeStart="00:00" timeEnd="00:08" />
 */

import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';
import { L30C, L30G, L30V } from './L30_constants';

interface HUDProps {
  chapter: string;    // "01"
  title: string;      // "HOOK"
  timeStart: string;  // "00:00"
  timeEnd: string;    // "00:08"
  showAt?: number;    // 등장 시작 프레임 (default 0)
}

const monoStyle: React.CSSProperties = {
  fontFamily:    L30C.fontMono,
  fontSize:      11,
  fontWeight:    400,
  letterSpacing: '3px',
  textTransform: 'uppercase',
  color:         L30C.lime,
  lineHeight:    1,
};

export const L30_HUD: React.FC<HUDProps> = ({
  chapter, title, timeStart, timeEnd, showAt = 0,
}) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [showAt, showAt + 12], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  return (
    <div style={{
      position: 'absolute', inset: 0,
      pointerEvents: 'none', zIndex: 100,
    }}>
      {/* ── 좌상단: ● CH 01 · TITLE ──────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 28, left: L30V.PAD,
        opacity: op,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: L30C.lime,
          boxShadow: L30G.lime.text,
          flexShrink: 0,
        }} />
        {/* CH XX · 접두사: 작고 dim */}
        <span style={{ ...monoStyle, opacity: 0.6, fontSize: 10 }}>
          CH {chapter} ·
        </span>
        {/* TITLE: 크고 선명 */}
        <span style={{
          ...monoStyle,
          fontSize:   13,
          fontWeight: 700,
          letterSpacing: '3px',
        }}>
          {title}
        </span>
      </div>

      {/* ── 우상단: TIME 00:00 - 00:05 ───────────────────────────── */}
      <div style={{
        position: 'absolute', top: 28, right: L30V.PAD,
        opacity: op,
      }}>
        <span style={monoStyle}>TIME {timeStart} - {timeEnd}</span>
      </div>
    </div>
  );
};
