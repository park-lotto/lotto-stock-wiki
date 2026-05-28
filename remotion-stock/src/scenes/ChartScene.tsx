/**
 * ChartScene.tsx — 실제 차트 이미지 + 애니메이션 오버레이
 *
 * 차트 이미지: KODEX 친환경조선해운액티브 (1151×414px)
 * 오버레이 요소:
 *   ① 스캔 라인  — 왼→오 1회 스윕으로 "차트 분석 중" 연출
 *   ② 현재위치 서클 — 36,180 위치에 펄스 링 (3중 파동)
 *   ③ 추세 화살표 — SVG 드로잉 애니메이션으로 우상향 방향 그리기
 *   ④ 텍스트 — "우상향 상승 추세" 캡션
 *
 * 사용법:
 *   <Series.Sequence durationInFrames={360}>
 *     <FadeWrapper dur={360}><ChartScene /></FadeWrapper>
 *   </Series.Sequence>
 */
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

// ─────────────────────────────────────────────
// 레이아웃 상수 — 1920×1080 프레임 기준
// ─────────────────────────────────────────────
const DISPLAY_W = 1700;                                   // 차트 표시 너비
const DISPLAY_H = Math.round(DISPLAY_W * 414 / 1151);     // ≈ 611px (비율 유지)
const OFFSET_X  = Math.round((1920 - DISPLAY_W) / 2);    // ≈ 110px
const OFFSET_Y  = Math.round((1080 - DISPLAY_H) / 2);    // ≈ 234px

// 36,180 현재가 위치 (이미지 내 비율로 산출)
//  - X: 차트 오른쪽 끝 근처 (~90%)
//  - Y: 가격축 기준 — 표시범위 12,500~42,500 중 36,180 → 상단 28%
const DOT_PCT_X = 0.905;
const DOT_PCT_Y = 0.295;
const DOT_X = OFFSET_X + DOT_PCT_X * DISPLAY_W;  // ≈ 1649px
const DOT_Y = OFFSET_Y + DOT_PCT_Y * DISPLAY_H;  // ≈ 414px

// 추세 화살표 끝점 (우상향 방향, 현재가에서 +200px 오른쪽, -140px 위)
const ARROW_END_X = DOT_X + 200;
const ARROW_END_Y = DOT_Y - 140;

// 화살표 총 길이 (strokeDasharray 용)
const ARROW_LEN = Math.hypot(ARROW_END_X - DOT_X, ARROW_END_Y - DOT_Y);  // ≈ 243px

// ─────────────────────────────────────────────
export const ChartScene: React.FC = () => {
  const f = useCurrentFrame();

  // 씬 페이드인
  const fadeIn = interpolate(f, [0, 18], [0, 1], { extrapolateRight: 'clamp' });

  // 차트 이미지 — 아래에서 위로 슬라이드인
  const chartY   = interpolate(f, [0, 30], [40, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const chartOp  = interpolate(f, [0, 30], [0, 1],   { extrapolateRight: 'clamp' });

  // ① 스캔 라인 (f10 ~ f80): 왼→오 스윕
  const scanX    = interpolate(f, [10, 80], [OFFSET_X, OFFSET_X + DISPLAY_W], { extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad) });
  const scanOp   = interpolate(f, [10, 15, 72, 80], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // ② 서클 — f80 이후 등장
  const circleOp = interpolate(f, [80, 100], [0, 1], { extrapolateRight: 'clamp' });

  // 펄스 링 3개 — 80프레임 간격, 순차 확산 (40프레임씩 딜레이)
  const pulse = (delay: number) => {
    const pf = Math.max(0, f - 100 - delay);
    const period = 70;
    const t = (pf % period) / period;
    return {
      scale:   interpolate(t, [0, 1], [1, 3.2], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
      opacity: interpolate(t, [0, 0.3, 1], [0.7, 0.5, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    };
  };
  const r1 = pulse(0);
  const r2 = pulse(22);
  const r3 = pulse(44);

  // ③ 화살표 드로잉 (f120 ~ f180): strokeDashoffset 0 → ARROW_LEN
  const arrowDraw   = interpolate(f, [120, 180], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const dashOffset  = ARROW_LEN * (1 - arrowDraw);
  const arrowHeadOp = interpolate(f, [175, 195], [0, 1], { extrapolateRight: 'clamp' });

  // ④ 텍스트 레이블
  const labelOp = interpolate(f, [190, 215], [0, 1], { extrapolateRight: 'clamp' });
  const labelX  = interpolate(f, [190, 215], [30, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 자막
  const capOp = interpolate(f, [230, 250], [0, 1], { extrapolateRight: 'clamp' });

  // 배경 글로우 (차트에 민트 느낌 오버레이)
  const bgGlow = Math.sin(f * 0.04) * 0.02 + 0.03;

  return (
    <AbsoluteFill style={{ background: '#060810', opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 민트 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* ── 차트 이미지 ── */}
      <div style={{
        position: 'absolute',
        left: OFFSET_X, top: OFFSET_Y,
        width: DISPLAY_W, height: DISPLAY_H,
        opacity: chartOp,
        transform: `translateY(${chartY}px)`,
        borderRadius: 8,
        overflow: 'hidden',
        boxShadow: '0 8px 60px rgba(0,0,0,0.8)',
      }}>
        <Img
          src={staticFile('images/chart_조선etf.png')}
          style={{ width: '100%', height: '100%', objectFit: 'fill', display: 'block' }}
        />
        {/* 차트 테두리 민트 글로우 */}
        <div style={{
          position: 'absolute', inset: 0,
          boxShadow: 'inset 0 0 0 1px rgba(0,255,208,0.35)',
          borderRadius: 8, pointerEvents: 'none',
        }} />
      </div>

      {/* ① 스캔 라인 */}
      <div style={{
        position: 'absolute',
        left: scanX, top: OFFSET_Y,
        width: 2, height: DISPLAY_H,
        background: `linear-gradient(180deg,
          transparent 0%,
          ${C.main} 20%,
          rgba(128,255,232,0.9) 50%,
          ${C.main} 80%,
          transparent 100%)`,
        boxShadow: `0 0 12px ${C.main}, 0 0 24px rgba(0,255,208,0.4)`,
        opacity: scanOp,
        pointerEvents: 'none',
      }} />
      {/* 스캔 트레일 (뒤에 흐릿한 빛) */}
      <div style={{
        position: 'absolute',
        left: OFFSET_X, top: OFFSET_Y,
        width: Math.max(0, scanX - OFFSET_X),
        height: DISPLAY_H,
        background: 'linear-gradient(90deg, transparent 0%, rgba(0,255,208,0.06) 100%)',
        opacity: scanOp,
        pointerEvents: 'none',
      }} />

      {/* SVG 오버레이 — 서클 + 화살표 */}
      <svg
        style={{ position: 'absolute', inset: 0, overflow: 'visible', pointerEvents: 'none' }}
        width={1920} height={1080}
      >
        {/* ② 서클 — 펄스 링 3겹 */}
        <g opacity={circleOp}>
          {/* 링 1 */}
          <circle cx={DOT_X} cy={DOT_Y} r={22}
            fill="none" stroke={C.main} strokeWidth={2}
            transform={`scale(${r1.scale})`}
            style={{ transformOrigin: `${DOT_X}px ${DOT_Y}px` }}
            opacity={r1.opacity}
          />
          {/* 링 2 */}
          <circle cx={DOT_X} cy={DOT_Y} r={22}
            fill="none" stroke={C.main} strokeWidth={1.5}
            transform={`scale(${r2.scale})`}
            style={{ transformOrigin: `${DOT_X}px ${DOT_Y}px` }}
            opacity={r2.opacity}
          />
          {/* 링 3 */}
          <circle cx={DOT_X} cy={DOT_Y} r={22}
            fill="none" stroke={C.mainLight} strokeWidth={1}
            transform={`scale(${r3.scale})`}
            style={{ transformOrigin: `${DOT_X}px ${DOT_Y}px` }}
            opacity={r3.opacity}
          />
          {/* 중앙 도트 */}
          <circle cx={DOT_X} cy={DOT_Y} r={8}
            fill={C.main}
            style={{ filter: 'drop-shadow(0 0 8px #00FFD0) drop-shadow(0 0 16px rgba(0,255,208,0.6))' }}
          />
          {/* 내부 하이라이트 */}
          <circle cx={DOT_X - 2} cy={DOT_Y - 2} r={3}
            fill="white" opacity={0.7}
          />
        </g>

        {/* ③ 추세 화살표 — 드로잉 애니메이션 */}
        {/* 화살표 본체 (점선 드로잉) */}
        <line
          x1={DOT_X} y1={DOT_Y}
          x2={ARROW_END_X} y2={ARROW_END_Y}
          stroke={C.main}
          strokeWidth={3.5}
          strokeDasharray={ARROW_LEN}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${C.main})` }}
        />
        {/* 화살표 헤드 */}
        <g opacity={arrowHeadOp} style={{ filter: `drop-shadow(0 0 8px ${C.main})` }}>
          <polygon
            points={`
              ${ARROW_END_X},${ARROW_END_Y}
              ${ARROW_END_X - 24},${ARROW_END_Y + 10}
              ${ARROW_END_X - 16},${ARROW_END_Y + 24}
            `}
            fill={C.main}
          />
        </g>

        {/* 텍스트 레이블 — "현재 위치" */}
        <g opacity={circleOp} transform={`translate(${DOT_X + 18}, ${DOT_Y - 30})`}>
          <rect x={0} y={-22} width={130} height={28}
            rx={5} fill="rgba(0,255,208,0.18)"
            stroke={C.main} strokeWidth={1}
          />
          <text x={8} y={-3}
            fill={C.main} fontSize={18} fontWeight={700}
            fontFamily={FONT}
          >
            현재 36,180
          </text>
        </g>

        {/* 화살표 끝 "추세" 레이블 */}
        <g opacity={arrowHeadOp} transform={`translate(${ARROW_END_X + 16}, ${ARROW_END_Y - 8})`}>
          <rect x={0} y={-22} width={170} height={30}
            rx={5} fill="rgba(0,255,208,0.15)"
            stroke={C.main} strokeWidth={1}
          />
          <text x={10} y={-2}
            fill={C.main} fontSize={20} fontWeight={700}
            fontFamily={FONT}
          >
            🔴 상승 추세
          </text>
        </g>
      </svg>

      {/* ④ 좌하단 인사이트 레이블 */}
      <div style={{
        position: 'absolute',
        left: OFFSET_X + 40,
        bottom: OFFSET_Y - 10,
        opacity: labelOp,
        transform: `translateX(${labelX}px)`,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{
          background: 'rgba(0,255,208,0.15)',
          border: `1px solid ${C.main}`,
          borderRadius: 6,
          padding: '7px 18px',
          fontSize: 26, fontWeight: 700, color: C.main,
          letterSpacing: 2,
          textShadow: GLOW.weak.text,
        }}>
          📈 우상향 상승 추세
        </div>
        <div style={{
          fontSize: 24, fontWeight: 500,
          color: 'rgba(240,248,255,0.7)',
        }}>
          +186.77% (2025.01 → 현재)
        </div>
      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '12%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: capOp,
      }}>
        <div style={{
          color: C.textPrimary, fontSize: 38, fontWeight: 700,
          textAlign: 'center', paddingInline: 100,
          textShadow: '0 2px 12px rgba(0,0,0,0.9)',
        }}>
          지금 보시는 것처럼 우상향으로 잘 가고 있고, 상승 추세입니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
