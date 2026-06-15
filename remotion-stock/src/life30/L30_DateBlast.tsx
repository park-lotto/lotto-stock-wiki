/**
 * L30_DateBlast — 날짜 임팩트 타이포 오버레이
 *
 * 영상 레퍼런스: frame 0160
 *   2022           ← 초대형 흰색, 화면 좌반 중앙
 *   11.30          ← 라임, medium-large
 *   THE DAY THE WORLD CHANGED  ← 라임 소형 caps
 *
 * 아바타 영상 위에 오버레이로 사용
 */

import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { L30C, L30G, L30V } from './L30_constants';

interface L30_DateBlastProps {
  showAt?:   number;
  year?:     string;   // "2022"
  day?:      string;   // "11.30"
  tagline?:  string;   // "THE DAY THE WORLD CHANGED"
  /** 숫자 크기 px (default 220) */
  yearSize?: number;
}

export const L30_DateBlast: React.FC<L30_DateBlastProps> = ({
  showAt   = 0,
  year     = '2022',
  day      = '11.30',
  tagline  = 'THE DAY THE WORLD CHANGED',
  yearSize = 220,
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progYear = spring({
    frame: Math.max(0, f - showAt),
    fps,
    config: { damping: 22, stiffness: 120, mass: 1.4 },
    durationInFrames: 30,
  });
  const progDay = spring({
    frame: Math.max(0, f - showAt - 8),
    fps,
    config: { damping: 26, stiffness: 160, mass: 1.0 },
    durationInFrames: 24,
  });
  const progTag = spring({
    frame: Math.max(0, f - showAt - 18),
    fps,
    config: { damping: 30, stiffness: 200, mass: 0.8 },
    durationInFrames: 20,
  });

  const tx = (prog: number, dist = 30) =>
    interpolate(prog, [0, 1], [-dist, 0], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });

  return (
    <div style={{
      position:  'absolute',
      left:      L30V.PAD + 16,
      top:       '50%',
      transform: 'translateY(-54%)',
      pointerEvents: 'none',
    }}>
      {/* 연도 — 초대형 흰색 */}
      <div style={{
        fontFamily:    L30C.fontMain,
        fontSize:      yearSize,
        fontWeight:    900,
        color:         L30C.white,
        lineHeight:    0.9,
        opacity:       progYear,
        transform:     `translateX(${tx(progYear, 40)}px)`,
        letterSpacing: '-6px',
      }}>
        {year}
      </div>

      {/* 날짜 — 라임 대형 */}
      <div style={{
        fontFamily:    L30C.fontMain,
        fontSize:      yearSize * 0.38,
        fontWeight:    900,
        color:         L30C.lime,
        textShadow:    L30G.lime.text,
        lineHeight:    1.1,
        letterSpacing: '-1px',
        opacity:       progDay,
        transform:     `translateX(${tx(progDay)}px)`,
        marginTop:     8,
      }}>
        {day}
      </div>

      {/* 태그라인 — 라임 소형 caps */}
      <div style={{
        fontFamily:    L30C.fontMono,
        fontSize:      12,
        fontWeight:    400,
        color:         L30C.lime,
        letterSpacing: '3px',
        textTransform: 'uppercase',
        opacity:       progTag * 0.8,
        transform:     `translateX(${tx(progTag, 16)}px)`,
        marginTop:     14,
      }}>
        {tagline}
      </div>
    </div>
  );
};
