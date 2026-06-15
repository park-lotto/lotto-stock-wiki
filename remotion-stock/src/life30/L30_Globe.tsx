/**
 * L30_Globe — 도트매트릭스 지구본
 *
 * 영상 레퍼런스: frame 0360
 *   - 점으로 구성된 구체 (위경도 격자)
 *   - 라임 그린 색상, 깊이에 따른 opacity
 *   - 회전 애니메이션 (Y축)
 *   - 라임 글로우 후광 링
 *   - 중심 어두운 구체 fill
 */

import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { L30C } from './L30_constants';

interface GlobeDot {
  x: number;
  y: number;
  opacity: number;
  size: number;
}

function generateDots(
  rotY: number,
  cx: number,
  cy: number,
  r: number,
): GlobeDot[] {
  const dots: GlobeDot[] = [];
  const LAT_STEPS = 18;

  for (let latI = 0; latI <= LAT_STEPS; latI++) {
    // phi: -80° to +80°
    const phi = ((latI / LAT_STEPS) - 0.5) * Math.PI * 0.9;
    const cosP = Math.cos(phi);
    const sinP = Math.sin(phi);

    // 위도별 경도 점 개수 (원 둘레 비례)
    const lonCount = Math.max(2, Math.round(36 * cosP));

    for (let lonI = 0; lonI < lonCount; lonI++) {
      const theta = (lonI / lonCount) * Math.PI * 2 + rotY;
      // z: 앞면 +1, 뒷면 -1
      const z = cosP * Math.sin(theta);

      if (z < -0.08) continue;  // 뒷면 숨김 (약간 overlap)

      const screenX = cx + r * cosP * Math.cos(theta);
      const screenY = cy - r * sinP;

      const depth = (z + 0.08) / 1.08;          // 0~1
      const opacity = 0.12 + depth * 0.72;
      const size    = 1.8 + depth * 1.8;

      dots.push({ x: screenX, y: screenY, opacity, size });
    }
  }
  return dots;
}

interface L30_GlobeProps {
  /** 화면 내 중심 X (px, default 960) */
  cx?:       number;
  /** 화면 내 중심 Y (px, default 540) */
  cy?:       number;
  /** 반지름 px (default 310) */
  radius?:   number;
  /** 초당 회전 라디안 (default PI/10) */
  speed?:    number;
  startFrame?: number;
}

export const L30_Globe: React.FC<L30_GlobeProps> = ({
  cx         = 960,
  cy         = 540,
  radius     = 310,
  speed      = Math.PI / 10,
  startFrame = 0,
}) => {
  const f      = useCurrentFrame();
  const { fps } = useVideoConfig();

  const elapsed = Math.max(0, f - startFrame);
  const rotY    = (elapsed / fps) * speed;

  // 등장 fade-in
  const fadeIn = interpolate(elapsed, [0, 20], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const dots = generateDots(rotY, cx, cy, radius);

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <svg
        viewBox="0 0 1920 1080"
        width="1920" height="1080"
        style={{ position: 'absolute', inset: 0, opacity: fadeIn }}
      >
        <defs>
          {/* 중심 어두운 구체 fill */}
          <radialGradient id="globeFill" cx="45%" cy="40%" r="55%">
            <stop offset="0%"   stopColor="#0A1A0A" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#030803" stopOpacity="0.9" />
          </radialGradient>

          {/* 글로우 후광 필터 */}
          <filter id="glowFilter" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="12" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* 배경 구체 (어두운 fill) */}
        <circle cx={cx} cy={cy} r={radius} fill="url(#globeFill)" />

        {/* 외곽 글로우 링 */}
        <circle
          cx={cx} cy={cy} r={radius + 18}
          fill="none"
          stroke={L30C.lime}
          strokeWidth={1.5}
          opacity={0.25}
          filter="url(#glowFilter)"
        />
        {/* 두번째 얇은 링 */}
        <circle
          cx={cx} cy={cy} r={radius + 8}
          fill="none"
          stroke={L30C.lime}
          strokeWidth={0.8}
          opacity={0.15}
        />

        {/* 도트 */}
        {dots.map((dot, i) => (
          <circle
            key={i}
            cx={dot.x}
            cy={dot.y}
            r={dot.size}
            fill={L30C.lime}
            opacity={dot.opacity}
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};
