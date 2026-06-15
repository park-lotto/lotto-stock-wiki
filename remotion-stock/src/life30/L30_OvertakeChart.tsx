/**
 * L30_OvertakeChart — 주가 추월 라인 차트
 *
 * 영상 레퍼런스: frame 0355
 *   - NVIDIA(라임) vs 경쟁사(파랑) 두 선
 *   - 교차점: "OVERTAKE ·" 원형 레이블
 *   - 경쟁사 로고카드 "▲ OVERTAKEN · 2024.06"
 *   - SVG 베지어 곡선으로 구현
 *   - 선이 왼쪽에서 오른쪽으로 그려지는 애니메이션
 */

import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { clamp, L30C, cardBase } from './L30_constants';

interface L30_OvertakeChartProps {
  showAt?:        number;
  /** NVIDIA 라인 색 (default lime) */
  lineAColor?:    string;
  /** 경쟁사 라인 색 (default #4A9EFF) */
  lineBColor?:    string;
  /** 경쟁사 이름 (default "MICROSOFT") */
  competitorName?: string;
  /** 경쟁사 이모지/기호 */
  competitorEmoji?: string;
  /** 추월 날짜 (default "2024.06") */
  overtakeDate?:  string;
  width?:         number;
  height?:        number;
}

// SVG 차트 내부 좌표 (0,0 = 좌상, w,h = 우하)
const W = 420;
const H = 280;

// NVIDIA 라인: 아래→교차→위 (지수적 상승)
const NV_POINTS = '20,240 80,230 140,210 200,175 240,140 280,90 340,40 400,20';
// 경쟁사 라인: 높음→완만 상승→역전
const MS_POINTS = '20,200 80,195 140,192 200,190 240,188 280,200 340,220 400,245';
// 교차점 위치
const CROSS_X = 245;
const CROSS_Y = 142;

function pointsToPath(pts: string): string {
  const arr = pts.split(' ').map(p => p.split(',').map(Number));
  let d = `M ${arr[0][0]} ${arr[0][1]}`;
  for (let i = 1; i < arr.length; i++) {
    const prev = arr[i - 1];
    const curr = arr[i];
    const cpx = (prev[0] + curr[0]) / 2;
    d += ` C ${cpx},${prev[1]} ${cpx},${curr[1]} ${curr[0]},${curr[1]}`;
  }
  return d;
}

export const L30_OvertakeChart: React.FC<L30_OvertakeChartProps> = ({
  showAt          = 0,
  lineAColor      = L30C.lime,
  lineBColor      = '#4A9EFF',
  competitorName  = 'MICROSOFT',
  competitorEmoji = '🪟',
  overtakeDate    = '2024.06',
  width           = W,
  height          = H,
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const drawProg = interpolate(
    Math.max(0, f - showAt),
    [0, 50],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );

  const crossProg = spring({
    frame: Math.max(0, f - showAt - 40),
    fps,
    config: { damping: 22, stiffness: 200, mass: 0.7 },
    durationInFrames: 18,
  });

  const badgeProg = spring({
    frame: Math.max(0, f - showAt - 48),
    fps,
    config: { damping: 26, stiffness: 180, mass: 0.8 },
    durationInFrames: 20,
  });

  const containerOp = clamp(f, showAt, showAt + 14);
  const pathLen     = W * 2;  // approx total path length

  const nvPath = pointsToPath(NV_POINTS);
  const msPath = pointsToPath(MS_POINTS);

  // strokeDashoffset으로 그리기 애니메이션
  const dashOffset = interpolate(drawProg, [0, 1], [pathLen, 0]);

  return (
    <div style={{
      position: 'relative',
      width,
      height,
      opacity: containerOp,
    }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={width}
        height={height}
        style={{ overflow: 'visible' }}
      >
        <defs>
          <filter id="nvGlow">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* 경쟁사 라인 (파랑) */}
        <path
          d={msPath}
          fill="none"
          stroke={lineBColor}
          strokeWidth={2.5}
          strokeDasharray={pathLen}
          strokeDashoffset={dashOffset}
          opacity={0.75}
        />

        {/* NVIDIA 라인 (라임) */}
        <path
          d={nvPath}
          fill="none"
          stroke={lineAColor}
          strokeWidth={3}
          strokeDasharray={pathLen}
          strokeDashoffset={dashOffset}
          filter="url(#nvGlow)"
          opacity={0.95}
        />

        {/* NVIDIA 라벨 (우하단) */}
        <text
          x={380} y={30}
          fontFamily={L30C.fontMono}
          fontSize={9}
          letterSpacing={2}
          fill={lineAColor}
          textAnchor="end"
          opacity={drawProg}
        >
          NVIDIA
        </text>
        {/* 경쟁사 라벨 */}
        <text
          x={380} y={252}
          fontFamily={L30C.fontMono}
          fontSize={9}
          letterSpacing={2}
          fill={lineBColor}
          textAnchor="end"
          opacity={drawProg * 0.75}
        >
          {competitorName}
        </text>

        {/* 교차점 원 + 레이블 */}
        <circle
          cx={CROSS_X} cy={CROSS_Y} r={10}
          fill="none"
          stroke={L30C.white}
          strokeWidth={1.5}
          opacity={crossProg * 0.85}
        />
        <circle cx={CROSS_X} cy={CROSS_Y} r={3} fill={L30C.white} opacity={crossProg} />
        <text
          x={CROSS_X + 16} y={CROSS_Y - 8}
          fontFamily={L30C.fontMono}
          fontSize={9}
          letterSpacing={2}
          fill={L30C.white}
          opacity={crossProg * 0.8}
        >
          OVERTAKE ·
        </text>
      </svg>

      {/* 경쟁사 로고 카드 */}
      <div style={{
        position:  'absolute',
        bottom:    0,
        left:      12,
        opacity:   badgeProg,
        transform: `translateY(${interpolate(badgeProg, [0, 1], [10, 0])}px)`,
        ...cardBase,
        padding:   '10px 16px',
        display:   'flex',
        alignItems: 'center',
        gap:       10,
      }}>
        <span style={{ fontSize: 22, lineHeight: 1 }}>{competitorEmoji}</span>
        <div>
          <div style={{
            fontFamily:    L30C.fontMain,
            fontSize:      14,
            fontWeight:    700,
            color:         L30C.white,
            letterSpacing: '0.5px',
          }}>
            {competitorName}
          </div>
          <div style={{
            fontFamily:    L30C.fontMono,
            fontSize:      9,
            letterSpacing: '2px',
            color:         L30C.lime,
            marginTop:     3,
          }}>
            ▲ OVERTAKEN · {overtakeDate}
          </div>
        </div>
      </div>
    </div>
  );
};
