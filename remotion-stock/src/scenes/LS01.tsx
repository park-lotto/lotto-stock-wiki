// LS01 — SVG 갈림길 차트형
// 같은 출발점에서 두 선이 분기. 아이콘·카드 전혀 없음.
// 자막: "주도주 한 종목이 모든 것을 바꿉니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

const SX = 240, SY = 490; // 시작점
const MINT_EX = 1680, MINT_EY = 160; // 주도주 끝점
const GRAY_EX = 1680, GRAY_EY = 845; // 비주도주 끝점
const CX = 960; // 화면 중앙 x

export const LS01 = () => {
  const f = useCurrentFrame();

  const fadeIn  = interpolate(f, [0, 10], [0, 1], { extrapolateRight: 'clamp' });

  // 상단 텍스트
  const titleOp = interpolate(f, [0, 22], [0, 1], { extrapolateRight: 'clamp' });
  const titleY  = interpolate(f, [0, 22], [-28, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 선 그리기 (f:28 → f:92)
  const drawProgress = interpolate(f, [28, 92], [1, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 시작점 마커
  const dotOp = interpolate(f, [22, 35], [0, 1], { extrapolateRight: 'clamp' });

  // 끝점 라벨
  const labelOp = interpolate(f, [94, 115], [0, 1], { extrapolateRight: 'clamp' });

  // 중간 설명 텍스트
  const subOp = interpolate(f, [118, 142], [0, 1], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [148, 168], [0, 1], { extrapolateRight: 'clamp' });

  // 민트 라인 글로우 펄스
  const pulse  = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gWidth = interpolate(pulse, [0, 1], [3, 5]);

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 상단 설명 */}
      <div style={{
        position: 'absolute', top: '7%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center',
        opacity: titleOp, transform: `translateY(${titleY}px)`,
      }}>
        <div style={{ color: C.textSub, fontSize: 32, fontWeight: 500, letterSpacing: 5 }}>
          같은 날, 같은 금액으로 매수했다면
        </div>
      </div>

      {/* SVG 차트 */}
      <svg
        viewBox="0 0 1920 1080"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <defs>
          <linearGradient id="mintLine" gradientUnits="userSpaceOnUse"
            x1={SX} y1={SY} x2={MINT_EX} y2={MINT_EY}>
            <stop offset="0%" stopColor={C.mainDark} />
            <stop offset="60%" stopColor={C.mainMid} />
            <stop offset="100%" stopColor={C.main} />
          </linearGradient>
          <linearGradient id="grayLine" gradientUnits="userSpaceOnUse"
            x1={SX} y1={SY} x2={GRAY_EX} y2={GRAY_EY}>
            <stop offset="0%" stopColor="#444444" />
            <stop offset="100%" stopColor="#2a2a2a" />
          </linearGradient>
          <filter id="mintGlow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* 수평 기준선 (희미) */}
        <line x1={SX} y1={SY} x2={CX + 400} y2={SY}
          stroke="#1a1a1a" strokeWidth="1" strokeDasharray="8 8" />

        {/* 주도주 선 (민트) */}
        <path
          d={`M ${SX},${SY} L ${MINT_EX},${MINT_EY}`}
          stroke="url(#mintLine)"
          strokeWidth={gWidth}
          fill="none"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={drawProgress}
          strokeLinecap="round"
          filter="url(#mintGlow)"
        />

        {/* 비주도주 선 (회색) */}
        <path
          d={`M ${SX},${SY} L ${GRAY_EX},${GRAY_EY}`}
          stroke="url(#grayLine)"
          strokeWidth="2.5"
          fill="none"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={drawProgress}
          strokeLinecap="round"
        />

        {/* 시작점 마커 */}
        <circle cx={SX} cy={SY} r="12" fill={C.main} opacity={dotOp}
          filter="url(#mintGlow)" />
        <circle cx={SX} cy={SY} r="6" fill={C.bg} opacity={dotOp} />

        {/* 주도주 끝점 라벨 */}
        <text x={MINT_EX + 24} y={MINT_EY + 10}
          fill={C.main} fontSize="72" fontWeight="900"
          fontFamily={FONT} opacity={labelOp}>
          +127%
        </text>
        <text x={MINT_EX + 24} y={MINT_EY + 52}
          fill={C.textSub} fontSize="30" fontFamily={FONT} opacity={labelOp}>
          주도주
        </text>

        {/* 비주도주 끝점 라벨 */}
        <text x={GRAY_EX + 24} y={GRAY_EY + 10}
          fill="#FF4444" fontSize="72" fontWeight="900"
          fontFamily={FONT} opacity={labelOp}>
          -15%
        </text>
        <text x={GRAY_EX + 24} y={GRAY_EY + 52}
          fill={C.textSub} fontSize="30" fontFamily={FONT} opacity={labelOp}>
          비주도주
        </text>
      </svg>

      {/* 중간 설명 */}
      <div style={{
        position: 'absolute', left: '13%', top: '46%',
        opacity: subOp,
      }}>
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 400,
          borderLeft: `3px solid ${C.borderSub}`, paddingLeft: 18, lineHeight: 1.8,
        }}>
          매수 시점 동일<br />
          보유 기간 동일
        </div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          주도주 한 종목이 모든 것을 바꿉니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
