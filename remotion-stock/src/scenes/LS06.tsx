// LS06 — SVG 레이더 탐지형
// 회전 스캔 라인이 조건 포인트를 하나씩 점등
// 자막: "네 가지 조건이 겹칠 때 주도주가 탄생합니다"
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

const CX = 960, CY = 450;
const R = 280;

const SIGNALS = [
  { angle: -80, label: '수급 빈집', sublabel: '외인·기관 비어있음', dx: 2, dy: -1 },
  { angle: 10,  label: '이평선 정배열', sublabel: '5>20>60>120', dx: 1, dy: 0 },
  { angle: 105, label: '섹터 모멘텀', sublabel: '섹터 주도 확인', dx: 0, dy: 1 },
  { angle: 195, label: '촉매 D-30', sublabel: '일정 재료 존재', dx: -1, dy: 0 },
];

export const LS06 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 레이더 원 그리기
  const circleProgress = interpolate(f, [8, 35], [0, 1], { extrapolateRight: 'clamp' });

  // 스캔 시작 (f:38~)
  const scanStart = 38;
  const sweepAngle = f >= scanStart ? ((f - scanStart) * 2.8) % 360 : 0;
  const sweepRad = (sweepAngle - 90) * Math.PI / 180;
  const sweepX = CX + R * Math.cos(sweepRad);
  const sweepY = CY + R * Math.sin(sweepRad);

  // 신호 점 가시성 (첫 회전 시 순차 등장)
  const totalSweep = f >= scanStart ? (f - scanStart) * 2.8 : 0;
  const signalVisible = SIGNALS.map(sig => {
    const normalizedAngle = ((sig.angle % 360) + 360 + 90) % 360;
    return totalSweep > normalizedAngle + 15;
  });

  // 신호점 근접 글로우
  const signalGlow = SIGNALS.map(sig => {
    const normalizedAngle = ((sig.angle % 360) + 360 + 90) % 360;
    const currentNorm = sweepAngle % 360;
    const dist = Math.abs(currentNorm - normalizedAngle);
    const minDist = Math.min(dist, 360 - dist);
    return Math.max(0, 1 - minDist / 25);
  });

  // 제목
  const titleOp = interpolate(f, [0, 20], [0, 1], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [148, 168], [0, 1], { extrapolateRight: 'clamp' });

  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 제목 */}
      <div style={{
        position: 'absolute', top: '6%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: titleOp,
      }}>
        <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 6 }}>
          주도주 탐지 레이더
        </div>
      </div>

      <svg
        viewBox="0 0 1920 1080"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <defs>
          <radialGradient id="sweepGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={C.main} stopOpacity="0.15" />
            <stop offset="100%" stopColor={C.main} stopOpacity="0" />
          </radialGradient>
          <filter id="signalGlow">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="sweepGlowFilter">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* 동심원 보조선 */}
        {[0.33, 0.67, 1].map((ratio, i) => (
          <circle key={i} cx={CX} cy={CY} r={R * ratio}
            stroke={C.borderSub} strokeWidth="1" fill="none"
            strokeDasharray="4 6"
            opacity={circleProgress * (0.3 + i * 0.15)} />
        ))}

        {/* 십자 보조선 */}
        <line x1={CX - R} y1={CY} x2={CX + R} y2={CY}
          stroke={C.borderSub} strokeWidth="1" opacity={circleProgress * 0.3} strokeDasharray="4 6" />
        <line x1={CX} y1={CY - R} x2={CX} y2={CY + R}
          stroke={C.borderSub} strokeWidth="1" opacity={circleProgress * 0.3} strokeDasharray="4 6" />

        {/* 스캔 부채꼴 (이전 60° 범위 흐릿하게) */}
        {f >= scanStart && (
          <path
            d={`M ${CX},${CY} L ${sweepX},${sweepY} A ${R},${R} 0 0,0 ${
              CX + R * Math.cos(sweepRad - 1.0)
            },${CY + R * Math.sin(sweepRad - 1.0)} Z`}
            fill={C.main} opacity="0.07"
          />
        )}

        {/* 스캔 라인 */}
        {f >= scanStart && (
          <line
            x1={CX} y1={CY} x2={sweepX} y2={sweepY}
            stroke={C.main} strokeWidth="2.5"
            opacity="0.9"
            filter="url(#sweepGlowFilter)"
          />
        )}

        {/* 신호 포인트 */}
        {SIGNALS.map((sig, i) => {
          if (!signalVisible[i]) return null;
          const rad = (sig.angle - 90) * Math.PI / 180;
          const px = CX + R * 0.75 * Math.cos(rad);
          const py = CY + R * 0.75 * Math.sin(rad);
          const glow = signalGlow[i];
          const r = 14 + glow * 8;
          const glowIntensity = 0.6 + pulse * 0.4 * (glow > 0.3 ? 1 : 0.3);

          // 레이블 위치
          const lx = CX + (R + 48) * Math.cos(rad) + sig.dx * 20;
          const ly = CY + (R + 48) * Math.sin(rad) + sig.dy * 20;

          return (
            <g key={i}>
              {/* 외부 글로우 */}
              {glow > 0.1 && (
                <circle cx={px} cy={py} r={r + 12} fill={C.main}
                  opacity={glow * 0.25} filter="url(#signalGlow)" />
              )}
              {/* 점 */}
              <circle cx={px} cy={py} r={r} fill={C.main} opacity={glowIntensity}
                filter={glow > 0.3 ? 'url(#signalGlow)' : undefined} />
              <circle cx={px} cy={py} r={r - 6} fill={C.bg} opacity="0.7" />

              {/* 레이블 */}
              <text x={lx} y={ly - 18} textAnchor="middle"
                fill={glow > 0.3 ? C.main : C.textPrimary}
                fontSize="30" fontWeight="700" fontFamily={FONT}
                opacity={0.9}>{sig.label}</text>
              <text x={lx} y={ly + 14} textAnchor="middle"
                fill={C.textSub} fontSize="22" fontFamily={FONT}
                opacity={0.7}>{sig.sublabel}</text>
            </g>
          );
        })}

        {/* 중앙 점 */}
        <circle cx={CX} cy={CY} r="6" fill={C.main} opacity={circleProgress} />
      </svg>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          네 가지 조건이 겹칠 때 주도주가 탄생합니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
