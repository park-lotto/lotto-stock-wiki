/**
 * L30_GridBg — 서브그리드 배경
 *
 * 영상 레퍼런스: frame 0360, 0370
 *   - 아주 희미한 라임 격자 (opacity ~4%)
 *   - 회로기판과 다른 단순 그리드
 *   - 인포그래픽 씬 공통 배경
 */

import React from 'react';
import { AbsoluteFill } from 'remotion';
import { L30C } from './L30_constants';

interface L30_GridBgProps {
  spacing?:  number;   // 격자 간격 px (default 80)
  opacity?:  number;   // 전체 투명도 (default 0.04)
  color?:    string;   // 라인 색 (default lime)
  bgColor?:  string;   // 배경색 (default #050F05)
}

export const L30_GridBg: React.FC<L30_GridBgProps> = ({
  spacing  = 80,
  opacity  = 0.04,
  color    = L30C.lime,
  bgColor  = '#050F05',
}) => {
  const cols = Math.ceil(1920 / spacing) + 1;
  const rows = Math.ceil(1080 / spacing) + 1;

  return (
    <AbsoluteFill style={{ background: bgColor }}>
      <svg
        viewBox="0 0 1920 1080"
        width="1920" height="1080"
        style={{ position: 'absolute', inset: 0, opacity }}
      >
        {/* 수직 라인 */}
        {Array.from({ length: cols }, (_, i) => (
          <line
            key={`v${i}`}
            x1={i * spacing} y1={0}
            x2={i * spacing} y2={1080}
            stroke={color} strokeWidth={0.5}
          />
        ))}
        {/* 수평 라인 */}
        {Array.from({ length: rows }, (_, i) => (
          <line
            key={`h${i}`}
            x1={0}    y1={i * spacing}
            x2={1920} y2={i * spacing}
            stroke={color} strokeWidth={0.5}
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};
