/**
 * STOCK BRAIN 시그니처 인트로 v2
 * 240프레임 = 8초 @ 30fps
 *
 * 타임라인:
 *  f0~8    : 렌즈 플래시 (화이트 버스트)
 *  f8~80   : 스캔라인이 위→아래 쓸며 헥사 네트워크 빌드
 *  f60~110 : 웨이브폼 바 spring 활성화 (오버슈트)
 *  f90~160 : "STOCK BRAIN" 스크램블 리빌 (매트릭스 스타일)
 *  f155~165: 글리치 버스트
 *  f160~185: "스탁브레인" 슬라이드업
 *  f178~200: 구분선 드로잉
 *  f192~225: 태그라인 letterSpacing 수렴
 *  f215~240: ✦ sparkle + ambient hold
 */

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { C } from '../constants';

export const STOCK_BRAIN_INTRO_FRAMES = 240;

// ─── 글로우 (눈부심 줄임) ─────────────────────────────────────────
const GLOW_SOFT  = `0 0 8px rgba(0,255,208,0.45), 0 0 18px rgba(0,255,208,0.2)`;
const GLOW_MED   = `0 0 10px rgba(0,255,208,0.65), 0 0 28px rgba(0,255,208,0.25)`;

// ─── 헥사 네트워크 (SVG 400×400, center=200) ─────────────────────
const CX = 200, CY = 200;
const R_OUT = 148, R_MID = 86;

const outerNodes = Array.from({ length: 6 }, (_, i) => ({
  x: CX + R_OUT * Math.sin((i * Math.PI) / 3),
  y: CY - R_OUT * Math.cos((i * Math.PI) / 3),
}));
const midNodes = Array.from({ length: 6 }, (_, i) => ({
  x: CX + R_MID * Math.sin((i * Math.PI) / 3 + Math.PI / 6),
  y: CY - R_MID * Math.cos((i * Math.PI) / 3 + Math.PI / 6),
}));
const ALL_NODES = [{ x: CX, y: CY }, ...outerNodes, ...midNodes];

const EDGES: [number, number][] = [
  [1,2],[2,3],[3,4],[4,5],[5,6],[6,1],
  [7,1],[7,2],[8,2],[8,3],[9,3],[9,4],
  [10,4],[10,5],[11,5],[11,6],[12,6],[12,1],
  [0,7],[0,8],[0,9],[0,10],[0,11],[0,12],
];

// ─── 스크램블 문자 풀 ─────────────────────────────────────────────
const SCRAMBLE_POOL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&';

// ─── 유틸 ─────────────────────────────────────────────────────────
const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (frame: number, from: number, cfg = { damping: 14, stiffness: 160, mass: 0.85 }) =>
  spring({ frame: Math.max(0, frame - from), fps: 30, config: cfg });

// ─── 헥사 네트워크 (스캔라인 빌드업) ─────────────────────────────
const HexNetwork: React.FC<{ f: number }> = ({ f }) => {
  // 스캔라인 Y: f8~80 동안 0→400 (easeInOut)
  const scanY = interpolate(f, [8, 80], [0, 400], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.quad),
  });

  const ambientPulse = 0.75 + Math.sin(f * 0.055) * 0.25;

  return (
    <svg width={400} height={400} viewBox="0 0 400 400" style={{ overflow: 'visible' }}>
      {/* 스캔라인 */}
      {f >= 8 && f <= 82 && (
        <line
          x1={0} y1={scanY} x2={400} y2={scanY}
          stroke={C.main}
          strokeWidth={1.5}
          strokeOpacity={0.7}
          style={{ filter: `drop-shadow(0 0 6px ${C.main})` }}
        />
      )}

      {/* 엣지 — 스캔라인이 지나간 영역만 표시 */}
      {EDGES.map(([a, b], i) => {
        const na = ALL_NODES[a], nb = ALL_NODES[b];
        const revealY = Math.max(na.y, nb.y);
        const progress = clamp(scanY, revealY - 10, revealY + 10);
        if (progress <= 0) return null;
        return (
          <line
            key={i}
            x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
            stroke={C.main}
            strokeWidth={1.4}
            strokeOpacity={0.38 * progress * ambientPulse}
          />
        );
      })}

      {/* 노드 */}
      {ALL_NODES.map((n, i) => {
        const revealProgress = clamp(scanY, n.y - 8, n.y + 14);
        if (revealProgress <= 0) return null;
        const r = i === 0 ? 6 : i <= 6 ? 6 : 4.5;
        const centerPulse = i === 0 ? 1 + Math.sin(f * 0.09) * 0.3 : 1;
        const nodeScale = sp(f, Math.max(8, 8 + (n.y / 400) * 72));
        return (
          <g key={i} transform={`translate(${n.x},${n.y})`} opacity={revealProgress}>
            <circle r={r * 3.5 * centerPulse} fill="none" stroke={C.main}
              strokeWidth={0.7} strokeOpacity={0.18 * revealProgress} />
            <circle r={r * nodeScale * centerPulse} fill={C.main} opacity={0.88}
              style={{ filter: `drop-shadow(0 0 ${i === 0 ? 7 : 3}px rgba(0,255,208,0.5))` }} />
          </g>
        );
      })}
    </svg>
  );
};

// ─── 웨이브폼 (spring 오버슈트 활성화) ───────────────────────────
const BAR_BASES = [0.28, 0.52, 0.78, 0.55, 1.0, 0.55, 0.78, 0.52, 0.28];
const BAR_W = 7, BAR_GAP = 6, BAR_MAX_H = 68;

const Waveform: React.FC<{ f: number }> = ({ f }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: BAR_GAP }}>
      {BAR_BASES.map((base, i) => {
        const barStart = 60 + i * 4;
        const activation = sp(f, barStart, { damping: 9, stiffness: 220, mass: 0.6 });
        const pulse = 0.7 + Math.sin(f * 0.11 + i * 0.75) * 0.3;
        const h = base * BAR_MAX_H * activation * pulse;
        const op = clamp(f, barStart, barStart + 15);
        return (
          <div key={i} style={{
            width: BAR_W,
            height: Math.max(2, h),
            background: `linear-gradient(180deg, rgba(128,255,232,0.9) 0%, ${C.main} 55%, rgba(0,191,154,0.6) 100%)`,
            borderRadius: 4,
            opacity: op,
            boxShadow: `0 0 5px rgba(0,255,208,0.35)`,
          }} />
        );
      })}
    </div>
  );
};

// ─── 스크램블 텍스트 ──────────────────────────────────────────────
const ScrambleText: React.FC<{
  text: string;
  f: number;
  startFrame: number;
  totalDuration: number;
  fontSize: number;
  letterSpacing: number;
}> = ({ text, f, startFrame, totalDuration, fontSize, letterSpacing }) => {
  const chars = text.split('');
  const perChar = totalDuration / chars.length;

  return (
    <div style={{ display: 'flex', letterSpacing, fontSize, fontWeight: 900,
      fontFamily: '"Arial Black", Arial, sans-serif' }}>
      {chars.map((ch, i) => {
        if (ch === ' ') return <span key={i} style={{ width: fontSize * 0.4 }} />;
        const cStart = startFrame + i * (perChar * 0.55);
        const cEnd   = cStart + perChar * 1.2;
        const prog   = clamp(f, cStart, cEnd);
        const settled = prog >= 0.88;

        // 프레임 기반 의사난수 (deterministic)
        const randIdx = Math.floor((f * 11 + i * 17 + 3) % SCRAMBLE_POOL.length);
        const display = prog <= 0 ? ch : settled ? ch : SCRAMBLE_POOL[randIdx];
        const color   = settled ? C.main : `rgba(0,255,208,${0.3 + prog * 0.55})`;
        const glow    = settled ? GLOW_MED : `0 0 4px rgba(0,255,208,${prog * 0.4})`;

        return (
          <span key={i} style={{ color, textShadow: glow, opacity: Math.max(0, prog * 1.3) }}>
            {display}
          </span>
        );
      })}
    </div>
  );
};

// ─── 메인 ────────────────────────────────────────────────────────
export const StockBrainIntro: React.FC = () => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();

  // 렌즈 플래시 (f0~8)
  const flashOp = interpolate(f, [0, 3, 8], [0, 0.55, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });

  // 글리치 (f155~165)
  const glitching = f >= 155 && f <= 165;
  const glitchX   = glitching ? Math.sin(f * 47) * 5 : 0;
  const glitchOp  = glitching && f % 3 === 0 ? 0.65 : 1;

  // 서브텍스트 슬라이드업
  const subSlide = sp(f, 160, { damping: 16, stiffness: 200, mass: 0.8 });
  const subOp    = clamp(f, 160, 185);

  // 구분선
  const lineW = interpolate(f, [178, 205], [0, 380], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // 태그라인
  const tagOp      = clamp(f, 192, 218);
  const tagSpacing = interpolate(f, [192, 225], [18, 1.5], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // ✦ sparkle
  const sparkOp = clamp(f, 218, 238);

  // ambient glow
  const ambientR = 480 + Math.sin(f * 0.045) * 40;
  const ambientOp = 0.055 + Math.sin(f * 0.055) * 0.025;

  return (
    <AbsoluteFill style={{ background: '#000', display: 'flex',
      flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>

      {/* 렌즈 플래시 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: '#fff',
        opacity: flashOp,
        pointerEvents: 'none',
        zIndex: 99,
      }} />

      {/* 배경 방사 글로우 */}
      <div style={{
        position: 'absolute',
        width: ambientR, height: ambientR,
        borderRadius: '50%',
        background: `radial-gradient(circle, rgba(0,255,208,${ambientOp}) 0%, transparent 65%)`,
        top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
      }} />

      {/* 헥사 네트워크 + 웨이브폼 */}
      <div style={{ position: 'relative', width: 400, height: 400, marginBottom: 20 }}>
        <HexNetwork f={f} />
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Waveform f={f} />
        </div>
      </div>

      {/* STOCK BRAIN 스크램블 + 글리치 */}
      <div style={{
        opacity: glitchOp,
        transform: `translateX(${glitchX}px)`,
        marginBottom: 14,
      }}>
        <ScrambleText
          text="STOCK BRAIN"
          f={f}
          startFrame={90}
          totalDuration={65}
          fontSize={96}
          letterSpacing={12}
        />
      </div>

      {/* 스탁브레인 (슬라이드업) */}
      <div style={{
        opacity: subOp,
        transform: `translateY(${interpolate(subSlide, [0, 1], [28, 0])}px)`,
        fontFamily: '"Noto Sans KR", sans-serif',
        fontSize: 38,
        fontWeight: 500,
        letterSpacing: 8,
        color: 'rgba(255,255,255,0.88)',
        textShadow: GLOW_SOFT,
        marginBottom: 24,
      }}>
        스탁브레인
      </div>

      {/* 구분선 */}
      <div style={{
        width: lineW,
        height: 1,
        background: `linear-gradient(90deg, transparent 0%, ${C.main} 50%, transparent 100%)`,
        opacity: 0.5,
        marginBottom: 20,
      }} />

      {/* 태그라인 */}
      <div style={{
        opacity: tagOp,
        fontFamily: '"Noto Sans KR", sans-serif',
        fontSize: 28,
        fontWeight: 300,
        letterSpacing: tagSpacing,
        color: 'rgba(255,255,255,0.65)',
        textAlign: 'center',
        whiteSpace: 'nowrap',
      }}>
        AI를 쉽게 활용하는 주식투자 분석
      </div>

      {/* ✦ sparkle */}
      <div style={{
        position: 'absolute',
        bottom: height * 0.075,
        right: width * 0.055,
        opacity: sparkOp,
        color: C.main,
        fontSize: 24,
        textShadow: GLOW_SOFT,
      }}>
        ✦
      </div>
    </AbsoluteFill>
  );
};
