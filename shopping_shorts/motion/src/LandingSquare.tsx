// 랜딩 "4단계" 정사각 칸용 6초 루프 — 전체 화면 → 핵심 부분이 원위치에서 팝업 → 복귀.
// 캡처 PNG는 public/sq/*.png (gitignore). 좌표는 전부 원본 픽셀.
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type Rect = {x: number; y: number; w: number; h: number};
export type Pop = {
  src: Rect; // 원본 픽셀 영역
  target: Rect; // 출력(1080) 좌표의 목표 사각형
  delay?: number; // 팝 시작 지연(프레임)
  highlights?: {r: Rect; t0: number; t1: number}[]; // 원본 좌표 + 표시 구간(프레임)
};
export type SquareProps = {img: string; w: number; h: number; pops: Pop[]};

const SIZE = 1080;
const BG = '#070b0f';
const MINT = '#6FF0D6';
const DUR = 180;
const POP_START = 36; // 1.2s
const EXIT_START = 144; // 4.8s

// 팝 목표 사각형 계산 도우미: 안전영역(y 90~900, x 40~1040) 안에 맞춰 배율 ≤ maxScale
export const fit = (src: Rect, opt: {maxScale?: number; fitW?: number; fitH?: number; cx?: number; cy?: number} = {}): Rect => {
  const {maxScale = 1.6, fitW = 1000, fitH = 800, cx = SIZE / 2, cy = 495} = opt;
  const s = Math.min(maxScale, fitW / src.w, fitH / src.h);
  const w = src.w * s;
  const h = src.h * s;
  return {x: cx - w / 2, y: cy - h / 2, w, h};
};

export const LandingSquare: React.FC<SquareProps> = ({img, w, h, pops}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  // 전체 화면: contain
  const c = Math.min(SIZE / w, SIZE / h);
  const ox = (SIZE - w * c) / 2;
  const oy = (SIZE - h * c) / 2;
  // 켄번스: 0/180프레임에서 1 → 루프 이음매 없음
  const kb = 1 + 0.045 * Math.sin((Math.PI * frame) / DUR);
  const toScreen = (px: number, py: number) => {
    const sx = ox + px * c;
    const sy = oy + py * c;
    return {x: SIZE / 2 + (sx - SIZE / 2) * kb, y: SIZE / 2 + (sy - SIZE / 2) * kb};
  };

  // 전체 진행도(어둡게 등) = 첫 팝 기준
  const exitT = interpolate(frame, [EXIT_START, DUR - 2], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const enterMain = spring({frame: frame - POP_START, fps, config: {damping: 13, stiffness: 110, mass: 0.9}});
  const dim = 0.55 * Math.min(enterMain, 1) * (1 - exitT);

  return (
    <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>
      <Img
        src={staticFile(img)}
        style={{
          position: 'absolute',
          left: ox,
          top: oy,
          width: w * c,
          height: h * c,
          transform: `scale(${kb})`,
          transformOrigin: `${SIZE / 2 - ox}px ${SIZE / 2 - oy}px`,
        }}
      />
      <div style={{position: 'absolute', inset: 0, background: `rgba(3,6,9,${dim})`}} />
      {pops.map((pop, i) => {
        const delay = pop.delay ?? 0;
        const enter = spring({frame: frame - POP_START - delay, fps, config: {damping: 13, stiffness: 110, mass: 0.9}});
        const p = Math.min(enter, 1.08) * (1 - exitT);
        // 원위치(화면 좌표)
        const a = toScreen(pop.src.x, pop.src.y);
        const b = toScreen(pop.src.x + pop.src.w, pop.src.y + pop.src.h);
        const from: Rect = {x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y};
        // 유지 구간 아주 느린 줌
        const hold = interpolate(frame, [POP_START + 20, EXIT_START], [1, 1.03], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const tw = pop.target.w * hold;
        const th = pop.target.h * hold;
        const to: Rect = {x: pop.target.x + (pop.target.w - tw) / 2, y: pop.target.y + (pop.target.h - th) / 2, w: tw, h: th};
        const r: Rect = {
          x: from.x + (to.x - from.x) * p,
          y: from.y + (to.y - from.y) * p,
          w: from.w + (to.w - from.w) * p,
          h: from.h + (to.h - from.h) * p,
        };
        const s = r.w / pop.src.w; // 원본 px → 출력 px
        const ui = Math.max(0, Math.min(1, (p - 0.15) / 0.5)); // 테두리·그림자·둥근모서리
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: r.x,
              top: r.y,
              width: r.w,
              height: r.h,
              overflow: 'hidden',
              borderRadius: 18 * ui,
              boxShadow: `0 0 0 ${3 * ui}px ${MINT}, 0 ${30 * ui}px ${80 * ui}px rgba(0,0,0,${0.7 * ui}), 0 0 ${40 * ui}px rgba(111,240,214,${0.35 * ui})`,
              opacity: p <= 0.001 ? 0 : 1,
            }}
          >
            <Img
              src={staticFile(img)}
              style={{position: 'absolute', left: -pop.src.x * s, top: -pop.src.y * s, width: w * s, height: h * s}}
            />
            {(pop.highlights ?? []).map((hl, j) => {
              if (frame < hl.t0 || frame > hl.t1) return null;
              const pulse = 0.55 + 0.45 * Math.sin(((frame - hl.t0) / 9) * Math.PI); // 깜빡
              const inT = interpolate(frame, [hl.t0, hl.t0 + 6], [0.8, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
              return (
                <div
                  key={j}
                  style={{
                    position: 'absolute',
                    left: (hl.r.x - pop.src.x) * s,
                    top: (hl.r.y - pop.src.y) * s,
                    width: hl.r.w * s,
                    height: hl.r.h * s,
                    border: `3px solid ${MINT}`,
                    borderRadius: 8,
                    boxShadow: `0 0 18px rgba(111,240,214,.55), inset 0 0 0 999px rgba(111,240,214,.10)`,
                    opacity: Math.abs(pulse) * ui,
                    transform: `scale(${inT})`,
                  }}
                />
              );
            })}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export const SQUARE = {width: SIZE, height: SIZE, fps: 30, durationInFrames: DUR};

// ── 4개 칸 설정 (원본 픽셀 좌표) ─────────────────────
const A = {img: 'sq/A.png', w: 1638, h: 802};
const B = {img: 'sq/B.png', w: 1627, h: 796};
const C = {img: 'sq/C.png', w: 1608, h: 832};

const sq1Src: Rect = {x: 20, y: 490, w: 310, h: 310};
const sq2Bar: Rect = {x: 15, y: 340, w: 1582, h: 105};
const sq2Cards: Rect[] = [
  {x: 15, y: 488, w: 187, h: 197},
  {x: 215, y: 488, w: 187, h: 197},
  {x: 414, y: 488, w: 187, h: 197},
];
const sq3Src: Rect = {x: 385, y: 275, w: 675, h: 330}; // 오른쪽 빈 영역 제외(배율 확보)
const sq4Src: Rect = {x: 22, y: 238, w: 348, h: 562};

// 카드 3장 가로 배치(각 1.6배, 간격 24)
const cardS = 1.6;
const cardW = 187 * cardS;
const cardH = 197 * cardS;
const cardsTotal = cardW * 3 + 24 * 2;
const cardY = 390;

export const SQUARES: Record<string, SquareProps> = {
  sq_1: {
    ...A,
    pops: [
      {
        src: sq1Src,
        target: fit(sq1Src, {maxScale: 1.6}),
        highlights: [
          {r: {x: 30, y: 594, w: 292, h: 22}, t0: 66, t1: 100}, // Key 줄
          {r: {x: 30, y: 618, w: 292, h: 36}, t0: 104, t1: 140}, // 상세 줄
        ],
      },
    ],
  },
  sq_2b: {
    ...B,
    pops: [
      {
        src: sq2Bar,
        target: fit(sq2Bar, {maxScale: 1.6, fitW: 1000, cy: 300}),
        highlights: [
          {r: {x: 28, y: 384, w: 312, h: 22}, t0: 70, t1: 92},
          {r: {x: 342, y: 384, w: 412, h: 22}, t0: 88, t1: 110},
          {r: {x: 756, y: 384, w: 516, h: 22}, t0: 106, t1: 128},
          {r: {x: 1274, y: 384, w: 310, h: 22}, t0: 124, t1: 144},
        ],
      },
      ...sq2Cards.map((r, i) => ({
        src: r,
        delay: 8 + i * 6,
        target: {x: (SIZE - cardsTotal) / 2 + i * (cardW + 24), y: cardY, w: cardW, h: cardH},
      })),
    ],
  },
  sq_3b: {
    ...C,
    pops: [
      {
        src: sq3Src,
        target: fit(sq3Src, {maxScale: 1.6, fitW: 1000}),
        highlights: [
          {r: {x: 430, y: 360, w: 292, h: 24}, t0: 66, t1: 104}, // 자막 줄
          {r: {x: 393, y: 411, w: 372, h: 165}, t0: 108, t1: 144}, // 컷 카드 4개
        ],
      },
    ],
  },
  sq_4: {
    ...C,
    pops: [
      {
        src: sq4Src,
        target: fit(sq4Src, {maxScale: 1.6, fitH: 770}),
        highlights: [{r: {x: 138, y: 672, w: 122, h: 28}, t0: 70, t1: 140}], // "This camera is"
      },
    ],
  },
};
