// GB03 — 씬3 수익률 비교 Whisper 싱크 (55.82s + 30f = 1616프레임)
// Whisper(국씬3.m4a): f0~185 직접계산/f185~448 6%→3900/f448~694 소득공제→4200
//                    f694~946 ETF10%비과세/f946~1170 4800·차이600/f1170~1385 확정수익아님/f1385~1586 타이밍질문
// Phase1 f0~380 / Phase2+3 f380~1200 / Phase4 f1200~1616
//
// ── 수치 (2026-05-30 검증) ──
// 국민성장펀드: 4,231만원 (세후+소득공제환급) / ETF: 4,831만원 / 차이: 600만원
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO = 'audio/국씬3.m4a';
const HAS_AUDIO = true;

const lerp = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

export const GB03_Compare = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });

  // ── 배경 글로우 ──
  const bgGlow = Math.sin(f * 0.03) * 0.025 + 0.04;

  // ── 수평 스캔라인 ──
  const scanY  = interpolate(f, [0, 38], [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // ═══════════════════════════════════════
  // PHASE 1 (f0-600): 3,000만원 → 두 갈래 분기
  // (카운트업 제거 — 3,000은 출발점, 결과가 아님)
  // ═══════════════════════════════════════
  const ph1 = {
    labelOp: lerp(0, 1, 10, 40)(f),
    titleOp: lerp(0, 1, 30, 70)(f),
    titleY:  lerp(40, 0, 30, 70)(f),
    // 원금 이모지 + 수치 (정적 등장, 카운트업 없음)
    numOp:   lerp(0, 1, 80, 120)(f),
    numScale: interpolate(f, [80, 130], [0.7, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) }),
    subOp:   lerp(0, 1, 200, 260)(f),
    subY:    lerp(20, 0, 200, 260)(f),
    // 두 갈래 화살표 (f380-460)
    splitOp: lerp(0, 1, 380, 460)(f),
    splitY:  lerp(16, 0, 380, 460)(f),
    // 페이드아웃 (f520-600)
    fadeOut: lerp(1, 0, 520, 600)(f),
  };

  // ── 동적 글로우 (원금 숫자) ──
  const pulse1   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz1     = interpolate(pulse1, [0, 1], [14, 40]);
  const strongGlow = `0 0 ${gSz1}px #00FFD0, 0 0 ${gSz1 * 2}px rgba(0,255,208,0.6), 0 0 ${gSz1 * 4}px rgba(0,191,154,0.35)`;

  // ═══════════════════════════════════════
  // PHASE 2 (f600-1200): 두 갈래 → 각각 카운트업
  // ═══════════════════════════════════════
  const ph2 = {
    cardOp:   lerp(0, 1, 390, 450)(f),
    cardY:    lerp(30, 0, 390, 450)(f),
    // 펀드 카운트업: f420~694 (Whisper f448 "4,200만원" 끝나는 시점)
    fundNum: Math.round(interpolate(f, [420, 694], [3000, 4231], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    })),
    // ETF 카운트업: f560~946 (Whisper f946 "4,800" 끝나는 시점)
    etfNum:  Math.round(interpolate(f, [560, 946], [3000, 4831], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    })),
    // f694 "소득공제" / f730 "비과세"
    taxOp:   lerp(0, 1, 694, 760)(f),
    riskOp:  lerp(0, 1, 760, 830)(f),
  };

  // ── 바 높이 (비율) ──
  // 바 높이: 4231/4831 = 87.6%
  const fundBarH = interpolate(ph2.fundNum, [3000, 4231], [0, 87.6], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const etfBarH  = interpolate(ph2.etfNum,  [3000, 4831], [0, 100],  { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // ═══════════════════════════════════════
  // PHASE 3 (f1200-2000): 비교 dimming + 차이 강조
  // ═══════════════════════════════════════
  const ph3 = {
    // f946 "차이 600만원" → ETF 글로우 강해짐
    fundDim:   interpolate(f, [946, 1060], [1, 0.35], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    etfReveal: interpolate(f, [946, 1060], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    // 차이 카운트업 f960~1160 (Whisper f946~f1170 "차이 600만원")
    diffNum: Math.round(interpolate(f, [960, 1160], [0, 600], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    })),
    diffOp:  lerp(0, 1, 950, 1010)(f),
    diffY:   lerp(20, 0, 950, 1010)(f),
    // VS 라인 f400~
    vsOp:    lerp(0, 1, 400, 455)(f),
  };

  // ── ETF 동적 글로우 (Phase 3에서 강해짐) ──
  const pulse3   = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz3     = interpolate(pulse3, [0, 1], [14, 40]);
  const etfGlow3 = `0 0 ${gSz3 * ph3.etfReveal}px #00FFD0, 0 0 ${gSz3 * 2 * ph3.etfReveal}px rgba(0,255,208,0.55)`;

  // ═══════════════════════════════════════
  // PHASE 4 (f2000-2700): 반전 "타이밍이 관건"
  // ═══════════════════════════════════════
  const ph4 = {
    // 크로스 스캔 (f1200~1238, Whisper f1170 "확정수익 아님")
    scan4X:  interpolate(f, [1200, 1238], [-2, 104], { extrapolateRight: 'clamp' }),
    scan4Y:  interpolate(f, [1200, 1238], [-2, 104], { extrapolateRight: 'clamp' }),
    scan4Op: interpolate(f, [1200, 1205, 1232, 1238], [0, 1, 1, 0], { extrapolateRight: 'clamp' }),
    but:     lerp(0, 1, 1240, 1282)(f),
    butY:    lerp(24, 0, 1240, 1282)(f),
    // f1385 "타이밍이 맞았을 때 이야기"
    t1Op:    lerp(0, 1, 1290, 1330)(f),
    t1Y:     lerp(-60, 0, 1290, 1330)(f),
    t1Ls:    lerp(20, 0, 1290, 1330)(f),
    t2Op:    lerp(0, 1, 1345, 1385)(f),
    t2Y:     lerp(60, 0, 1345, 1385)(f),
    zoom:    interpolate(f, [1200, 1616], [1, 1.04], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    // 버스트 f1420
    burstOp:    interpolate(f, [1420, 1428, 1458], [0, 0.6, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    burstScale: interpolate(f, [1420, 1458], [0.2, 3.0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    // f1490 "수혜주는 찾을 수 있습니다"
    subOp:   lerp(0, 1, 1468, 1525)(f),
    subY:    lerp(18, 0, 1468, 1525)(f),
  };

  // ── Phase4 동적 글로우 ──
  const pulse4    = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz4      = interpolate(pulse4, [0, 1], [14, 40]);
  const climaxGlow = `0 0 ${gSz4}px #00FFD0, 0 0 ${gSz4 * 2}px rgba(0,255,208,0.6), 0 0 ${gSz4 * 4}px rgba(0,191,154,0.35)`;

  // ── Phase 전환 (Whisper 국씬3 기준) ──
  // f340~380: Ph1 페이드 / f1160~1200: Ph2 페이드 / Phase4 f1200~
  const showPh1 = f < 340 ? 1 : interpolate(f, [340, 380], [1, 0], { extrapolateRight: 'clamp' });
  const showPh2 = f < 380 ? 0 : f > 1160 ? interpolate(f, [1160, 1200], [1, 0], { extrapolateRight: 'clamp' }) : 1;
  const showPh4 = f < 1150 ? 0 : interpolate(f, [1150, 1210], [0, 1], { extrapolateRight: 'clamp' });

  // 자막 (Whisper 타이밍 기반 요약)
  const cap1Op = f < 380 ? interpolate(f, [140, 178], [0, 1], { extrapolateRight: 'clamp' }) : 0;
  const cap2Op = f >= 380 && f < 1160 ? interpolate(f, [958, 995], [0, 1], { extrapolateRight: 'clamp' }) : 0;
  const cap4Op = f >= 1200 ? interpolate(f, [1490, 1528], [0, 1], { extrapolateRight: 'clamp' }) : 0;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow,
      }} />

      {/* 스캔라인 (Phase1) */}
      <div style={{
        position: 'absolute', left: 0, right: 0,
        top: `${scanY}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scanOp * showPh1, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* 크로스 스캔 (Phase4 진입) */}
      <div style={{
        position: 'absolute', left: 0, right: 0,
        top: `${ph4.scan4Y}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: ph4.scan4Op, zIndex: 10, pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', top: 0, bottom: 0,
        left: `${ph4.scan4X}%`, width: 2,
        background: 'linear-gradient(180deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: ph4.scan4Op, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* ══════ PHASE 1: 원금 ══════ */}
      <AbsoluteFill style={{ opacity: showPh1 * ph1.fadeOut, pointerEvents: 'none' }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 20,
        }}>
          <div style={{
            fontSize: 28, fontWeight: 500, color: C.textSub, letterSpacing: 5,
            opacity: ph1.labelOp,
          }}>수익 시뮬레이션 · 5년 기준</div>

          <div style={{
            fontSize: 100, fontWeight: 900, color: C.textPrimary,
            opacity: ph1.titleOp, transform: `translateY(${ph1.titleY}px)`,
          }}>같은 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>3,000만원</span>으로</div>

          {/* 3,000만원 — 정적 등장 (출발점, 카운트업 없음) */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 24,
            opacity: ph1.numOp, transform: `scale(${ph1.numScale})`,
          }}>
            <div style={{ fontSize: 96 }}>💰</div>
            <div style={{
              fontSize: 160, fontWeight: 900, color: C.main,
              fontFamily: '"Consolas","Menlo",monospace',
              textShadow: strongGlow, lineHeight: 0.9,
            }}>3,000<span style={{ fontSize: 72 }}>만원</span></div>
          </div>

          <div style={{
            opacity: ph1.subOp, transform: `translateY(${ph1.subY}px)`,
            color: C.textSub, fontSize: 32, fontWeight: 500, letterSpacing: 2,
          }}>같은 돈 — 5년 후 결과가 다릅니다</div>

          {/* 두 갈래 화살표 */}
          <div style={{
            opacity: ph1.splitOp, transform: `translateY(${ph1.splitY}px)`,
            display: 'flex', gap: 120, marginTop: 16,
          }}>
            <div style={{ textAlign: 'center', color: C.textSub, fontSize: 28, fontWeight: 500 }}>
              ↙ 국민성장펀드
            </div>
            <div style={{ textAlign: 'center', color: C.main, fontSize: 28, fontWeight: 700, textShadow: GLOW.weak.text }}>
              반도체 ETF ↘
            </div>
          </div>
        </div>
      </AbsoluteFill>

      {/* ══════ PHASE 2+3: 비교 카드 ══════ */}
      <AbsoluteFill style={{ opacity: showPh2, pointerEvents: 'none' }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          paddingInline: 80, gap: 32,
        }}>

          <div style={{
            opacity: ph2.cardOp,
            color: C.textPrimary, fontSize: 48, fontWeight: 900, letterSpacing: -1,
          }}>같은 3,000만원 — 5년 후</div>
          <div style={{
            opacity: ph2.cardOp,
            color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 2,
          }}>연 수익률 동일 가정 | 세후 실수령 기준</div>

          {/* 비교 카드 영역 */}
          <div style={{
            display: 'flex', gap: 40, width: '100%', alignItems: 'flex-end',
            opacity: ph2.cardOp, transform: `translateY(${ph2.cardY}px)`,
          }}>

            {/* 펀드 카드 — Phase3에서 dim */}
            <div style={{
              flex: 1,
              opacity: ph3.fundDim,
              background: C.cardBg,
              border: `1.5px solid ${C.borderSub}`,
              borderRadius: 18, padding: '28px 24px',
            }}>
              <div style={{ color: C.textSub, fontSize: 28, letterSpacing: 4, marginBottom: 10 }}>
                국민성장펀드
              </div>
              <div style={{ color: C.textPrimary, fontSize: 26, fontWeight: 600, marginBottom: 20 }}>
                소득공제 + 운용수익 (연 6% 가정)
              </div>
              {/* 바 */}
              <div style={{
                height: 160, background: '#111', borderRadius: 8,
                display: 'flex', alignItems: 'flex-end', marginBottom: 20, position: 'relative',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: '100%', height: `${fundBarH}%`,
                  background: 'linear-gradient(180deg, rgba(0,255,208,0.5) 0%, rgba(0,255,208,0.15) 100%)',
                  borderRadius: '6px 6px 0 0',
                  border: `1px solid rgba(0,255,208,0.3)`,
                }} />
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <div style={{
                  color: C.textPrimary, fontSize: 64, fontWeight: 900,
                  fontFamily: '"Consolas","Menlo",monospace',
                  textShadow: GLOW.weak.text,
                }}>{ph2.fundNum.toLocaleString('ko-KR')}</div>
                <div style={{ color: C.textSub, fontSize: 28, fontWeight: 600 }}>만원</div>
              </div>
              <div style={{ opacity: ph2.taxOp, color: C.mainMid, fontSize: 24, fontWeight: 600, marginTop: 10 }}>
                소득공제 환급 317만원 포함 (세율 26.4%)
              </div>
            </div>

            {/* VS */}
            <div style={{
              opacity: ph3.vsOp,
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
              paddingBottom: 60,
            }}>
              <div style={{ width: 1, height: 60, background: 'rgba(255,255,255,0.15)' }} />
              <div style={{
                color: C.textSub, fontSize: 22, fontWeight: 800, letterSpacing: 2,
                border: '1px solid rgba(255,255,255,0.2)', borderRadius: 8, padding: '8px 14px',
              }}>VS</div>
              <div style={{ width: 1, height: 60, background: 'rgba(255,255,255,0.15)' }} />
            </div>

            {/* ETF 카드 — Phase3에서 글로우 강해짐 */}
            <div style={{
              flex: 1,
              background: ph3.etfReveal > 0.3 ? C.cardBgActive : C.cardBg,
              border: `1.5px solid ${ph3.etfReveal > 0.3 ? `rgba(0,255,208,${0.4 + ph3.etfReveal * 0.4})` : C.borderSub}`,
              borderRadius: 18, padding: '28px 24px',
              boxShadow: ph3.etfReveal > 0.2 ? `0 0 ${30 * ph3.etfReveal}px rgba(0,255,208,${0.15 * ph3.etfReveal})` : undefined,
            }}>
              <div style={{ color: C.textSub, fontSize: 28, letterSpacing: 4, marginBottom: 10 }}>
                TIGER 반도체 ETF
              </div>
              <div style={{ color: C.textPrimary, fontSize: 26, fontWeight: 600, marginBottom: 20 }}>
                시세차익 (연 10% 가정)
              </div>
              {/* 바 */}
              <div style={{
                height: 160, background: '#111', borderRadius: 8,
                display: 'flex', alignItems: 'flex-end', marginBottom: 20, position: 'relative',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: '100%', height: `${etfBarH}%`,
                  background: `linear-gradient(180deg, rgba(0,255,208,${0.5 + ph3.etfReveal * 0.4}) 0%, rgba(0,255,208,0.15) 100%)`,
                  borderRadius: '6px 6px 0 0',
                  border: `1px solid rgba(0,255,208,${0.3 + ph3.etfReveal * 0.5})`,
                  boxShadow: ph3.etfReveal > 0.3 ? `0 0 ${12 * ph3.etfReveal}px rgba(0,255,208,0.5)` : undefined,
                }} />
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <div style={{
                  color: C.main, fontSize: 64, fontWeight: 900,
                  fontFamily: '"Consolas","Menlo",monospace',
                  textShadow: etfGlow3,
                }}>{ph2.etfNum.toLocaleString('ko-KR')}</div>
                <div style={{ color: C.textSub, fontSize: 28, fontWeight: 600 }}>만원</div>
              </div>
              <div style={{ opacity: ph2.riskOp, color: C.textSub, fontSize: 24, fontWeight: 500, marginTop: 10 }}>
                ⚠ 타이밍 맞았을 때 기준
              </div>
            </div>
          </div>

          {/* 차이 강조 */}
          <div style={{
            opacity: ph3.diffOp, transform: `translateY(${ph3.diffY}px)`,
            textAlign: 'center',
          }}>
            <div style={{ color: C.textSub, fontSize: 28, marginBottom: 8 }}>5년 차이</div>
            <div style={{
              color: C.main, fontSize: 80, fontWeight: 900,
              fontFamily: '"Consolas","Menlo",monospace',
              textShadow: GLOW.strong.text,
            }}>+{ph3.diffNum.toLocaleString('ko-KR')}만원</div>
          </div>

        </div>
      </AbsoluteFill>

      {/* ══════ PHASE 4: 반전 클라이맥스형 ══════ */}
      <AbsoluteFill style={{ opacity: showPh4, pointerEvents: 'none' }}>

        {/* 씬 줌인 */}
        <div style={{ transform: `scale(${ph4.zoom})`, transformOrigin: 'center center', width: '100%', height: '100%' }}>

          {/* 글로우 버스트 */}
          <div style={{
            position: 'absolute', top: '48%', left: '50%',
            width: 600, height: 600, marginLeft: -300, marginTop: -300,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
            opacity: ph4.burstOp, transform: `scale(${ph4.burstScale})`, pointerEvents: 'none',
          }} />

          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 24,
          }}>

            <div style={{
              opacity: ph4.but, transform: `translateY(${ph4.butY}px)`,
              color: C.textSub, fontSize: 36, fontWeight: 500, letterSpacing: 4,
            }}>근데 여기서 중요한 게 있어요.</div>

            {/* Line1 — 위에서 Y슬라이드 + 자간 20→0 */}
            <div style={{
              fontSize: 150, fontWeight: 900, color: C.textPrimary,
              opacity: ph4.t1Op,
              transform: `translateY(${ph4.t1Y}px)`,
              letterSpacing: ph4.t1Ls,
              lineHeight: 1,
            }}>반도체 ETF는</div>

            {/* Line2 — 아래서 Y슬라이드 + 동적 글로우 */}
            <div style={{
              fontSize: 150, fontWeight: 900, color: C.main,
              opacity: ph4.t2Op,
              transform: `translateY(${ph4.t2Y}px)`,
              textShadow: ph4.t2Op > 0.9 ? climaxGlow : GLOW.mid.text,
              lineHeight: 1,
            }}>타이밍이 있습니다</div>

            {/* 질문 + 불확실성 시각화 */}
            <div style={{
              opacity: ph4.subOp, transform: `translateY(${ph4.subY}px)`,
              textAlign: 'center',
            }}>
              <div style={{
                fontSize: 52, fontWeight: 900, color: C.textPrimary,
                lineHeight: 1.3, marginBottom: 28,
              }}>
                지금 그 타이밍인지&nbsp;
                <span style={{ color: C.main, textShadow: GLOW.mid.text }}>알 수 있나요??</span>
              </div>

              {/* 불확실성 그래프 (봉차트형) */}
              <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 10, marginBottom: 24 }}>
                {[
                  { body: 30, upper: 8, lower: 5, up: true },
                  { body: 50, upper: 60, lower: 6, up: true, hi: true },
                  { body: 40, upper: 10, lower: 8, up: false },
                  { body: 35, upper: 6,  lower: 12, up: false },
                  { body: 28, upper: 5,  lower: 30, up: false, shadow: true },
                  { body: 44, upper: 8,  lower: 6, up: true },
                  { body: 20, upper: 45, lower: 5, up: false, hi2: true },
                ].map(({ body, upper, lower, up, hi, shadow, hi2 }, i) => {
                  const color = up ? C.dataUp : C.dataDown;
                  return (
                    <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div style={{ width: 2, height: upper, background: color }} />
                      <div style={{ width: hi || hi2 ? 32 : 28, height: body, background: color, borderRadius: 2, boxShadow: (hi || hi2) ? `0 0 10px ${color}` : 'none' }} />
                      <div style={{ width: 2, height: lower, background: color }} />
                    </div>
                  );
                })}
              </div>

              <div style={{ fontSize: 30, color: C.textSub, fontWeight: 600 }}>
                📌 펀드는 못 넣었지만 — <span style={{ color: C.main }}>수혜주는 찾을 수 있습니다</span>
              </div>
            </div>

          </div>
        </div>
      </AbsoluteFill>

      {/* 하단 자막 바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {/* Phase 1 자막 */}
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80,
          opacity: cap1Op,
        }}>5년 후 손에 쥐는 돈이 다릅니다</div>

        {/* Phase 2-3 자막 */}
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80,
          opacity: cap2Op,
        }}>
          같은 조건이라도&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>타이밍에 따라 결과가 달라집니다</span>
        </div>

        {/* Phase 4 자막 */}
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80,
          opacity: cap4Op,
        }}>
          펀드는 못 넣었지만&nbsp;—&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>수혜주는 찾을 수 있습니다</span>
        </div>
      </div>

    </AbsoluteFill>
  );
};
