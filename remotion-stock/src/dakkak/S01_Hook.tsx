// S01 — 씬1 코스피 8000 훅 (20초 = 600프레임)
// B4 수준 재작성: prog 페이즈 시스템 + 숨쉬는 글로우 + SVG draw-on 차트
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 600;

// KOSPI 상승 라인 (viewBox: 0 0 780 270)
// 2025.1(저점) → 2026.5(8500 신고가) 자연스러운 상승 곡선
const KOSPI_PATH = 'M 0,258 L 80,244 L 160,226 L 240,202 L 320,174 L 400,143 L 480,110 L 560,76 L 640,48 L 720,26 L 780,10';
const PATH_LEN = 900; // 추정 path length

const Y_LABELS = [
  { y: 10,  val: '8,500' },
  { y: 60,  val: '8,000' },
  { y: 110, val: '7,500' },
  { y: 160, val: '7,000' },
  { y: 210, val: '6,500' },
  { y: 258, val: '6,000' },
];

const X_LABELS = [
  { x: 0,   label: "'25.1" },
  { x: 195, label: "'25.6" },
  { x: 390, label: "'26.1" },
  { x: 585, label: "'26.4" },
  { x: 780, label: 'NOW'   },
];

export const S01_Hook = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  const prog   = interpolate(f, [15, DUR - 40], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // ── 숨쉬는 배경 글로우 ──
  const mintGlow = Math.sin(f * 0.04) * 0.025 + 0.04;
  const redGlow  = Math.sin(f * 0.04) * 0.020 + 0.03;

  // ── Phase 크로스페이드 ──
  const xfade = interpolate(prog, [0.44, 0.52], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  // ── Phase 1 타이밍 ──
  const p1_intro  = interpolate(prog, [0.02, 0.08], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const kospiNum  = Math.round(interpolate(prog, [0.02, 0.36], [0, 8476], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  }));
  const p1_시대    = interpolate(prog, [0.10, 0.16], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const p1_sub    = interpolate(prog, [0.29, 0.38], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 차트 draw-on (strokeDashoffset)
  const chartDraw  = interpolate(prog, [0.04, 0.42], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
  const dashOffset  = PATH_LEN * (1 - chartDraw);
  const chartPanelOp = interpolate(prog, [0.03, 0.10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const chartDataOp  = interpolate(prog, [0.38, 0.44], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 펄스 링 (현재가 포인트)
  const pulseR = 6 + Math.sin(f * 0.15) * 3;
  const pulseOp = 0.5 + Math.sin(f * 0.15) * 0.3;

  // 가이드 자막 패널
  const guideOp = interpolate(prog, [0.33, 0.42], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // ── Phase 2 타이밍 ──
  const p2_q   = interpolate(prog, [0.53, 0.61], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const lineP  = interpolate(prog, [0.60, 0.80], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.linear),
  });
  const p2_t1  = interpolate(prog, [0.73, 0.81], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const p2_t2  = interpolate(prog, [0.83, 0.89], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const p2_cta = interpolate(prog, [0.91, 0.97], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: '#000', opacity: fadeIn, fontFamily: FONT }}>

      {/* 숨쉬는 배경 글로우 — Phase 1 민트 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 32% 52%, rgba(0,255,208,1) 0%, transparent 52%)',
        opacity: mintGlow * (1 - xfade),
      }} />
      {/* 숨쉬는 배경 글로우 — Phase 2 레드 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(255,67,54,1) 0%, transparent 52%)',
        opacity: redGlow * xfade,
      }} />

      {/* 스캔라인 */}
      <AbsoluteFill style={{
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,255,208,0.009) 3px, rgba(0,255,208,0.009) 4px)',
        pointerEvents: 'none',
      }} />

      {/* 헤더 라벨 */}
      <div style={{
        position: 'absolute', top: 30, left: 60, zIndex: 50,
        color: C.textSub, fontSize: 15, fontWeight: 600, letterSpacing: 4,
        opacity: p1_intro,
      }}>STOCK BRAIN · MARKET OVERVIEW</div>
      <div style={{
        position: 'absolute', top: 30, right: 60, zIndex: 50,
        color: C.textSub, fontSize: 15, fontWeight: 600, letterSpacing: 3,
        opacity: p1_intro,
      }}>로또의 주식인사이트</div>

      {/* ════════ PHASE 1: 코스피 8000 ════════ */}
      <AbsoluteFill style={{ opacity: 1 - xfade, pointerEvents: 'none' }}>

        {/* 좌측 텍스트 (0 ~ 900) */}
        <div style={{
          position: 'absolute', left: 80, top: 0, width: 820, height: '100%',
          display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 22,
        }}>
          <div style={{
            opacity: p1_intro,
            transform: `translateY(${(1 - p1_intro) * 20}px)`,
            color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 8,
          }}>여러분, 이제</div>

          <div style={{ opacity: p1_intro, display: 'flex', alignItems: 'baseline', gap: 16 }}>
            <div style={{ color: C.textSub, fontSize: 44, fontWeight: 600 }}>코스피</div>
            <div style={{
              color: C.main, fontSize: 150, fontWeight: 900,
              fontFamily: '"Consolas", "Menlo", monospace',
              textShadow: GLOW.strong.text, lineHeight: 0.88,
            }}>{kospiNum.toLocaleString()}</div>
          </div>

          <div style={{
            opacity: p1_시대,
            transform: `translateY(${(1 - p1_시대) * 16}px)`,
            color: C.textPrimary, fontSize: 54, fontWeight: 700, letterSpacing: 7,
          }}>시대입니다</div>

          <div style={{
            opacity: p1_sub,
            transform: `translateY(${(1 - p1_sub) * 14}px)`,
            color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 2, marginTop: 6,
          }}>
            코스피&nbsp;
            <span style={{ color: C.mainLight, fontWeight: 800 }}>10,000</span>
            ,&nbsp;이제 꿈이 아니에요
          </div>
        </div>

        {/* 세로 구분선 */}
        <div style={{
          position: 'absolute', left: 945, top: '10%', height: '80%', width: 1,
          background: `linear-gradient(180deg, transparent, rgba(0,255,208,0.22) 25%, rgba(0,255,208,0.22) 75%, transparent)`,
          opacity: p1_intro,
        }} />

        {/* 우측 KOSPI 차트 패널 (960 ~ 1860) */}
        <div style={{
          position: 'absolute', left: 975, top: 90,
          width: 890, height: 580,
          background: '#080E0D',
          border: `1.5px solid rgba(0,255,208,0.22)`,
          borderRadius: 18,
          overflow: 'hidden',
          opacity: chartPanelOp,
          boxShadow: '0 0 50px rgba(0,255,208,0.07), 0 24px 70px rgba(0,0,0,0.65)',
        }}>

          {/* 패널 헤더 */}
          <div style={{
            padding: '15px 24px',
            borderBottom: '1px solid rgba(0,255,208,0.1)',
            background: 'linear-gradient(180deg, rgba(0,255,208,0.04) 0%, transparent 100%)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%', background: '#FF4336',
                boxShadow: '0 0 7px rgba(255,67,54,0.9)',
              }} />
              <div style={{ color: '#777', fontSize: 13, fontWeight: 600, letterSpacing: 3 }}>
                LIVE · KOSPI 실시간
              </div>
            </div>
            <div style={{ color: C.textSub, fontSize: 13, opacity: 0.7 }}>2025.01 — 2026.05</div>
          </div>

          {/* 차트 SVG */}
          <div style={{ padding: '20px 24px 10px 16px', flex: 1 }}>
            <svg width="846" height="370" viewBox="-60 -20 850 310" overflow="visible">
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#00FFD0" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="#00FFD0" stopOpacity="0" />
                </linearGradient>
                <clipPath id="chartClip">
                  <rect x="0" y="-20" width={780 * chartDraw} height="310" />
                </clipPath>
              </defs>

              {/* Y축 그리드 + 라벨 */}
              {Y_LABELS.map((yl, i) => (
                <g key={i}>
                  <line x1="0" y1={yl.y} x2="780" y2={yl.y}
                    stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                  <text x="-8" y={yl.y + 4}
                    fill="rgba(255,255,255,0.28)" fontSize="13" textAnchor="end"
                    fontFamily='"Consolas","Menlo",monospace'>{yl.val}</text>
                </g>
              ))}

              {/* X축 라벨 */}
              {X_LABELS.map((xl, i) => (
                <text key={i} x={xl.x} y="282"
                  fill={xl.label === 'NOW' ? C.main : 'rgba(255,255,255,0.28)'}
                  fontSize="13" textAnchor="middle"
                  fontFamily='"Consolas","Menlo",monospace'
                  fontWeight={xl.label === 'NOW' ? 800 : 400}>{xl.label}</text>
              ))}

              {/* Area fill (clip으로 draw-on) */}
              <path
                d={`${KOSPI_PATH} L 780,258 L 0,258 Z`}
                fill="url(#areaGrad)"
                clipPath="url(#chartClip)"
              />

              {/* 메인 라인 (strokeDashoffset draw-on) */}
              <path
                d={KOSPI_PATH}
                fill="none"
                stroke={C.main}
                strokeWidth="2.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={PATH_LEN}
                strokeDashoffset={dashOffset}
                style={{ filter: 'drop-shadow(0 0 7px rgba(0,255,208,0.9))' }}
              />

              {/* 현재가 포인트 (차트 다 그려졌을 때) */}
              {chartDraw > 0.96 && (
                <>
                  <circle cx="780" cy="10" r="6" fill={C.main}
                    style={{ filter: 'drop-shadow(0 0 8px rgba(0,255,208,1))' }} />
                  <circle cx="780" cy="10" r={pulseR}
                    fill="none" stroke={C.main} strokeWidth="1.5"
                    opacity={pulseOp} />
                </>
              )}
            </svg>
          </div>

          {/* 하단 현재가 카드 */}
          <div style={{
            position: 'absolute', bottom: 18, left: 24, right: 24,
            display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
            opacity: chartDataOp,
          }}>
            <div>
              <div style={{ color: C.textSub, fontSize: 12, fontWeight: 600, letterSpacing: 3, marginBottom: 4 }}>
                KOSPI 현재가
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
                <div style={{
                  color: C.main, fontSize: 44, fontWeight: 900,
                  fontFamily: '"Consolas","Menlo",monospace',
                  textShadow: GLOW.mid.text,
                }}>8,476</div>
                <div style={{ color: '#FF4336', fontSize: 20, fontWeight: 700 }}>▲ +3.50%</div>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ color: C.textSub, fontSize: 12, letterSpacing: 2, marginBottom: 4 }}>1년 수익률</div>
              <div style={{
                color: C.main, fontSize: 32, fontWeight: 900,
                fontFamily: '"Consolas","Menlo",monospace',
              }}>+38.2%</div>
            </div>
          </div>
        </div>

        {/* 가이드 자막 패널 (B4 스타일) */}
        <div style={{
          position: 'absolute', left: 80, bottom: 56,
          background: 'rgba(0,0,0,0.72)', borderRadius: 12, padding: '16px 22px',
          border: '1px solid rgba(0,255,208,0.1)',
          opacity: guideOp,
        }}>
          <div style={{
            color: C.main, fontSize: 15, fontWeight: 800, letterSpacing: 3, marginBottom: 8,
          }}>STAGE 1 · 시장 현황</div>
          <div style={{ color: C.textSub, fontSize: 14, fontWeight: 500, lineHeight: 1.7 }}>
            코스피 8,000 돌파 · 2026년 5월 기준<br />
            1년 수익률 +38.2% · 신고가 행진 중
          </div>
        </div>

      </AbsoluteFill>

      {/* ════════ PHASE 2: 내 계좌 ════════ */}
      <AbsoluteFill style={{
        opacity: xfade, pointerEvents: 'none',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 34,
      }}>

        <div style={{
          opacity: p2_q,
          transform: `translateY(${(1 - p2_q) * 22}px)`,
          color: C.textSub, fontSize: 36, fontWeight: 500, letterSpacing: 4,
        }}>그런데 여러분 계좌는 어떠십니까?</div>

        {/* 비교 차트 패널 */}
        <div style={{
          opacity: p2_q, width: 920,
          background: '#080E0D',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 16, padding: '28px 36px',
          boxShadow: '0 0 30px rgba(255,67,54,0.06)',
        }}>
          <svg width="848" height="150" style={{ display: 'block' }}>
            <defs>
              <linearGradient id="lg_kospi" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#00FFD0" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#00FFD0" stopOpacity="1" />
              </linearGradient>
              <linearGradient id="lg_acc" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#FF4336" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#FF4336" stopOpacity="1" />
              </linearGradient>
            </defs>

            {/* 그리드 */}
            {[25, 75, 125].map(y => (
              <line key={y} x1="0" y1={y} x2="848" y2={y}
                stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
            ))}

            {/* 레이블 */}
            <text x="10" y="20" fill="rgba(0,255,208,0.7)"
              fontSize="14" fontWeight="700" fontFamily={FONT}>코스피</text>
            <text x="10" y="108" fill="rgba(255,67,54,0.7)"
              fontSize="14" fontWeight="700" fontFamily={FONT}>내 계좌</text>

            {/* 코스피 상승선 */}
            <path
              d={`M 0,128 C 180,118 320,88 470,58 S 680,18 ${848 * lineP},12`}
              fill="none" stroke="url(#lg_kospi)" strokeWidth="3"
              strokeLinecap="round"
              style={{ filter: 'drop-shadow(0 0 5px rgba(0,255,208,0.6))' }}
            />

            {/* 내 계좌 flat */}
            <line x1="0" y1="102" x2={848 * lineP} y2="102"
              stroke="url(#lg_acc)" strokeWidth="3.5" strokeLinecap="round" />
            {lineP > 0.01 && (
              <circle cx={848 * lineP} cy="102" r="6" fill="#FF4336"
                style={{ filter: 'drop-shadow(0 0 5px rgba(255,67,54,0.8))' }} />
            )}

            {/* 끝점 퍼센트 라벨 */}
            {lineP > 0.95 && (
              <>
                <text x="854" y="16" fill={C.main}
                  fontSize="15" fontWeight="800" fontFamily={FONT}>▲ +38.2%</text>
                <text x="854" y="107" fill="#FF4336"
                  fontSize="15" fontWeight="800" fontFamily={FONT}>→ +0.3%</text>
              </>
            )}
          </svg>
        </div>

        <div style={{
          opacity: p2_t1, transform: `translateY(${(1 - p2_t1) * 16}px)`,
          color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center',
        }}>
          지수는 오르는데 내 계좌만&nbsp;
          <span style={{ color: '#FF4336' }}>제자리</span>
        </div>

        <div style={{
          opacity: p2_t2, transform: `translateY(${(1 - p2_t2) * 14}px)`,
          color: C.textSub, fontSize: 30, fontWeight: 500,
        }}>뒤로만 안 가면 잘한 건가요?</div>

        <div style={{
          opacity: p2_cta, transform: `translateY(${(1 - p2_cta) * 12}px)`,
          color: C.main, fontSize: 32, fontWeight: 800,
          textShadow: GLOW.mid.text, letterSpacing: 2,
        }}>뭔가 잘못되고 있다면 — 조금만 집중해 보세요</div>

      </AbsoluteFill>

      {/* 하단 STAGE 라벨 */}
      <div style={{
        position: 'absolute', bottom: 22, left: 0, right: 0, textAlign: 'center',
        color: C.textPrimary, fontSize: 22, fontWeight: 700, opacity: 0.4,
      }}>STAGE 1 · 시장 현황</div>

    </AbsoluteFill>
  );
};
