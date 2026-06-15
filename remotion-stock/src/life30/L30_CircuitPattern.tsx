/**
 * L30_CircuitPattern — PCB 회로기판 배경
 *
 * 영상 레퍼런스: https://youtu.be/kI1soqlxwl8 (frame ~320)
 *   - 배경: #060E06 (다크 그린 블랙)
 *   - 트레이스: 라임 그린 (#AAFF00), 직각 경로만
 *   - 패드: 교차점에 작은 사각형 노드
 *   - 코너 브래킷 4개
 *   - 헤더: "SYSTEM · 007 / SIGNAL"
 *   - 트레이스 순차적 등장 애니메이션
 */

import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { clamp, L30C, L30G } from './L30_constants';

// 1920×1080 공간의 PCB 트레이스 정의 (직각 경로만)
const TRACES: [number, number][][] = [
  // ── 상단 구역 ────────────────────────────────────────
  [[80, 100], [320, 100], [320, 200], [580, 200]],
  [[580, 100], [860, 100], [860, 200], [1080, 200], [1080, 80]],
  [[200, 100], [200, 40]],
  [[460, 200], [460, 320], [680, 320]],
  // ── 좌측 중단 ─────────────────────────────────────────
  [[80, 320], [200, 320], [200, 440], [80, 440]],
  [[200, 380], [360, 380], [360, 320]],
  // ── 중앙 ──────────────────────────────────────────────
  [[680, 320], [860, 320], [860, 200]],
  [[860, 440], [1080, 440], [1080, 340], [1260, 340]],
  [[680, 440], [680, 560], [460, 560]],
  [[460, 560], [460, 680], [660, 680]],
  [[80, 560], [300, 560], [300, 680]],
  [[300, 680], [460, 680]],
  // ── 우측 중단 ─────────────────────────────────────────
  [[1080, 560], [1300, 560], [1300, 440]],
  [[1080, 680], [1300, 680], [1300, 560]],
  [[1260, 240], [1400, 240], [1400, 140]],
  // ── 하단 구역 ─────────────────────────────────────────
  [[80, 780], [360, 780], [360, 680], [520, 680]],
  [[360, 780], [360, 900], [620, 900]],
  [[620, 780], [880, 780], [880, 900], [1100, 900]],
  [[880, 680], [1100, 680], [1100, 780]],
  [[520, 960], [760, 960], [760, 900]],
  [[1100, 960], [1320, 960], [1320, 900]],
  [[1320, 780], [1500, 780], [1500, 680]],
  // ── 추가 수직 연결 ─────────────────────────────────────
  [[1400, 440], [1400, 340]],
  [[1500, 560], [1500, 440]],
];

// 패드 노드 위치 (트레이스 교차점)
const PADS: [number, number][] = [
  [320, 100], [580, 100], [580, 200], [860, 100], [1080, 80],
  [460, 200], [460, 320], [680, 320], [860, 320], [200, 320],
  [200, 440], [860, 440], [1080, 440], [1300, 440],
  [680, 560], [460, 560], [460, 680], [300, 680], [660, 680],
  [1080, 560], [1300, 560], [1080, 680], [1300, 680],
  [360, 780], [620, 780], [880, 780], [1100, 780], [1320, 780],
  [620, 900], [880, 900], [1100, 900], [760, 960], [1320, 960],
  [1260, 340], [1400, 240], [1400, 340], [1500, 560], [1500, 680],
];

// polyline points 문자열로 변환
const toPoints = (pts: [number, number][]): string =>
  pts.map(p => `${p[0]},${p[1]}`).join(' ');

export const L30_CircuitPattern: React.FC<{
  startFrame?: number;
  systemId?:   string;   // "007"
  signalLabel?: string;  // "SIGNAL"
}> = ({
  startFrame  = 0,
  systemId    = '007',
  signalLabel = 'SIGNAL',
}) => {
  const f = useCurrentFrame();

  const headerOp = clamp(f, startFrame, startFrame + 20);

  return (
    <AbsoluteFill style={{ background: '#060E06' }}>

      {/* SVG 회로 트레이스 */}
      <svg
        viewBox="0 0 1920 1080"
        width="1920"
        height="1080"
        style={{ position: 'absolute', inset: 0 }}
      >
        {/* 트레이스 라인 */}
        {TRACES.map((pts, i) => {
          const delay = startFrame + i * 4;
          const op = clamp(f, delay, delay + 28);
          return (
            <polyline
              key={`t${i}`}
              points={toPoints(pts)}
              fill="none"
              stroke={L30C.lime}
              strokeWidth={1.5}
              strokeLinecap="square"
              opacity={op * 0.85}
            />
          );
        })}

        {/* 패드 노드 */}
        {PADS.map((pad, i) => {
          const traceIdx = Math.min(i, TRACES.length - 1);
          const delay = startFrame + traceIdx * 4 + 14;
          const op = clamp(f, delay, delay + 16);
          return (
            <rect
              key={`p${i}`}
              x={pad[0] - 5}
              y={pad[1] - 5}
              width={10}
              height={10}
              fill={L30C.lime}
              opacity={op}
            />
          );
        })}

        {/* 코너 브래킷 — 좌상 */}
        <path
          d="M28,28 L28,72 M28,28 L72,28"
          stroke={L30C.lime} strokeWidth={2} fill="none"
          opacity={headerOp}
        />
        {/* 코너 브래킷 — 우상 */}
        <path
          d="M1892,28 L1892,72 M1892,28 L1848,28"
          stroke={L30C.lime} strokeWidth={2} fill="none"
          opacity={headerOp}
        />
        {/* 코너 브래킷 — 좌하 */}
        <path
          d="M28,1052 L28,1008 M28,1052 L72,1052"
          stroke={L30C.lime} strokeWidth={2} fill="none"
          opacity={headerOp}
        />
        {/* 코너 브래킷 — 우하 */}
        <path
          d="M1892,1052 L1892,1008 M1892,1052 L1848,1052"
          stroke={L30C.lime} strokeWidth={2} fill="none"
          opacity={headerOp}
        />
      </svg>

      {/* 헤더 레이블 */}
      <div style={{
        position:      'absolute',
        top:           36,
        left:          44,
        fontFamily:    L30C.fontMono,
        fontSize:      11,
        fontWeight:    400,
        letterSpacing: '3px',
        textTransform: 'uppercase',
        color:         L30C.lime,
        opacity:       headerOp,
        textShadow:    L30G.lime.text,
      }}>
        SYSTEM · {systemId} / {signalLabel}
      </div>

    </AbsoluteFill>
  );
};
