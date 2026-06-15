/**
 * L30_SloganText — 슬로건 대형 텍스트 레이아웃
 *
 * 영상 레퍼런스: frame 0370 "AI가 바꾼 것은 / 기술만이 아닙니다"
 *   - 1줄: 흰색, ultra-bold, 대형
 *   - 2줄: 라임, 동일 크기, bold
 *   - 3줄: 흰색 소형, em-dash 구분자 ("숫자 — 시장 — 현실")
 *   - 좌상단 섹션 라벨 (선택)
 *   - 각 줄 순차 등장
 */

import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { clamp, L30C, L30G, L30V } from './L30_constants';

interface L30_SloganTextProps {
  showAt?:      number;
  line1?:       string;   // "AI가 바꾼 것은" — 흰색
  line2?:       string;   // "기술만이 아닙니다" — 라임
  line3?:       string;   // "숫자 — 시장 — 현실" — 흰색 소형
  sectionLabel?: string;  // "THE VERDICT" — 좌상 소형 라임
  fontSize?:    number;   // 대형 폰트 크기 (default 96)
}

export const L30_SloganText: React.FC<L30_SloganTextProps> = ({
  showAt       = 0,
  line1        = 'AI가 바꾼 것은',
  line2        = '기술만이 아닙니다',
  line3,
  sectionLabel,
  fontSize     = 96,
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const makeProg = (delay: number) => spring({
    frame: Math.max(0, f - showAt - delay),
    fps,
    config: { damping: 28, stiffness: 160, mass: 1.0 },
    durationInFrames: 24,
  });

  const prog0 = makeProg(0);
  const prog1 = makeProg(8);
  const prog2 = makeProg(18);
  const labelOp = clamp(f, showAt, showAt + 14);

  const slideIn = (prog: number, dist = 28) =>
    interpolate(prog, [0, 1], [dist, 0], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });

  return (
    <div style={{
      position: 'absolute',
      top:      '50%',
      left:     L30V.PAD + 8,
      transform: 'translateY(-50%)',
      pointerEvents: 'none',
    }}>
      {/* 섹션 라벨 */}
      {sectionLabel && (
        <div style={{
          fontFamily:    L30C.fontMono,
          fontSize:      10,
          letterSpacing: '3px',
          textTransform: 'uppercase',
          color:         L30C.lime,
          opacity:       labelOp,
          marginBottom:  20,
        }}>
          {sectionLabel}
        </div>
      )}

      {/* 1줄: 흰색 */}
      {line1 && (
        <div style={{
          fontFamily:    L30C.fontMain,
          fontSize,
          fontWeight:    900,
          color:         L30C.white,
          lineHeight:    1.15,
          opacity:       prog0,
          transform:     `translateY(${slideIn(prog0)}px)`,
          marginBottom:  4,
        }}>
          {line1}
        </div>
      )}

      {/* 2줄: 라임 */}
      {line2 && (
        <div style={{
          fontFamily:    L30C.fontMain,
          fontSize,
          fontWeight:    900,
          color:         L30C.lime,
          lineHeight:    1.15,
          textShadow:    L30G.lime.text,
          opacity:       prog1,
          transform:     `translateY(${slideIn(prog1)}px)`,
          marginBottom:  32,
        }}>
          {line2}
        </div>
      )}

      {/* 3줄: 흰색 소형 */}
      {line3 && (
        <div style={{
          fontFamily:    L30C.fontMain,
          fontSize:      fontSize * 0.35,
          fontWeight:    400,
          color:         L30C.white,
          letterSpacing: '1px',
          opacity:       prog2 * 0.75,
          transform:     `translateY(${slideIn(prog2, 16)}px)`,
        }}>
          {line3}
        </div>
      )}
    </div>
  );
};
