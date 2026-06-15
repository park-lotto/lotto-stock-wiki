/**
 * L30_RecBadge — REC 타임스탬프 뱃지
 *
 * 영상 레퍼런스: frame 0160
 *   위치: 좌상단 (HUD 아래)
 *   형식: ● REC  2022.11.30
 *   특징: 빨간 점 + 라임 텍스트, 다크 반투명 배경
 *
 * PiP "LIVE · 09:16" 레이블과 별개 컴포넌트
 */

import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { L30C, L30G } from './L30_constants';

interface L30_RecBadgeProps {
  showAt?: number;
  date?:   string;   // "2022.11.30"
  label?:  string;   // "REC" (default)
}

export const L30_RecBadge: React.FC<L30_RecBadgeProps> = ({
  showAt = 0,
  date   = '2022.11.30',
  label  = 'REC',
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const prog = spring({
    frame: Math.max(0, f - showAt),
    fps,
    config: { damping: 24, stiffness: 200, mass: 0.7 },
    durationInFrames: 20,
  });
  const op = prog;
  const tx = interpolate(prog, [0, 1], [-20, 0]);

  return (
    <div style={{
      position:   'absolute',
      top:        56,
      left:       44,
      display:    'flex',
      alignItems: 'center',
      gap:        10,
      opacity:    op,
      transform:  `translateX(${tx}px)`,
      background: 'rgba(0,0,0,0.55)',
      backdropFilter: 'blur(6px)',
      border:     '1px solid rgba(170,255,0,0.25)',
      borderRadius: 3,
      padding:    '6px 14px',
      pointerEvents: 'none',
    }}>
      {/* 빨간 점 */}
      <div style={{
        width:     7,
        height:    7,
        borderRadius: '50%',
        background: '#FF2D2D',
        boxShadow:  '0 0 6px #FF2D2D, 0 0 12px #FF000055',
        flexShrink: 0,
      }} />

      {/* REC 레이블 */}
      <span style={{
        fontFamily:    L30C.fontMono,
        fontSize:      10,
        fontWeight:    400,
        letterSpacing: '3px',
        color:         L30C.lime,
        textShadow:    L30G.lime.text,
      }}>
        {label}
      </span>

      {/* 날짜 */}
      <span style={{
        fontFamily:    L30C.fontMono,
        fontSize:      11,
        fontWeight:    700,
        letterSpacing: '2px',
        color:         L30C.lime,
        textShadow:    L30G.lime.text,
      }}>
        {date}
      </span>
    </div>
  );
};
