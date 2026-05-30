// GB04 — 씬4 전환 "저 어떻게 알았냐고요?" (녹음 전 버전 — HAS_AUDIO=false)
// Phase1: 클라이맥스형 질문 훅 → Phase2: 텔레그램 브리핑 목업 → Phase3: "전부 자동으로요"
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO = 'audio/국씬4.m4a';
const HAS_AUDIO = false;

const MSGS = [
  {
    icon: '🏦', tag: '정책',
    title: '국민성장펀드 발표',
    body: '6,000억 모집 개시 · 소득공제 40% 확정\n5년 의무 보유 조건 주의',
  },
  {
    icon: '📊', tag: '리포트',
    title: '증권사 리포트 11건',
    body: '오늘 접수 11건 자동 요약\n핵심 변경사항 3건 추출',
  },
  {
    icon: '📺', tag: '유튜브',
    title: '핫이슈 채널 요약',
    body: '"국민성장 vs ETF" 오늘 최다 언급\n주요 채널 12곳 자동 수집·정리',
  },
  {
    icon: '🔑', tag: '키워드',
    title: '뉴스 키워드 TOP5',
    body: '국민성장펀드 · 소득공제 · 의무보유\n코스피 · 미국금리',
  },
];

export const GB04_Telegram = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  // ── Phase 전환 ──
  const showPh1 = f < 480 ? 1 : interpolate(f, [480, 540], [1, 0], { extrapolateRight: 'clamp' });
  const showPh2 =
    f < 540 ? 0
    : f > 1030 ? interpolate(f, [1030, 1080], [1, 0], { extrapolateRight: 'clamp' })
    : interpolate(f, [540, 620], [0, 1], { extrapolateRight: 'clamp' });
  const showPh3 = f < 1080 ? 0 : interpolate(f, [1080, 1150], [0, 1], { extrapolateRight: 'clamp' });

  // ── Phase 1 ──
  const scan1Y  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scan1Op = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const burst1Op    = interpolate(f, [100, 108, 133], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burst1Scale = interpolate(f, [100, 133], [0.2, 2.8], { extrapolateRight: 'clamp' });
  const label1Op = interpolate(f, [10, 40],  [0, 1], { extrapolateRight: 'clamp' });
  const t1Op     = interpolate(f, [30, 68],  [0, 1], { extrapolateRight: 'clamp' });
  const t1Y      = interpolate(f, [30, 68],  [-60, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Ls     = interpolate(f, [30, 68],  [20, 0],  { extrapolateRight: 'clamp' });
  const t2Op     = interpolate(f, [58, 98],  [0, 1],   { extrapolateRight: 'clamp' });
  const t2Y      = interpolate(f, [58, 98],  [60, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const sub1Op   = interpolate(f, [180, 240], [0, 1],  { extrapolateRight: 'clamp' });
  const pulse1   = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz1     = interpolate(pulse1, [0, 1], [14, 40]);
  const breathe1 = t2Op > 0.9 ? Math.sin(f * 0.08) * 0.025 + 1 : 1;
  const dynGlow1 = t2Op > 0.9
    ? `0 0 ${gSz1}px #00FFD0, 0 0 ${gSz1 * 2}px rgba(0,255,208,0.6), 0 0 ${gSz1 * 4}px rgba(0,191,154,0.35)`
    : GLOW.mid.text;
  const zoom1 = interpolate(f, [0, 540], [1, 1.02], { extrapolateRight: 'clamp' });

  // ── Phase 2: 텔레그램 목업 ──
  const scan2X  = interpolate(f, [540, 578], [-2, 104], { extrapolateRight: 'clamp' });
  const scan2Op = interpolate(f, [540, 545, 573, 578], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const headerOp = interpolate(f, [560, 600], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const MSG_START = [600, 690, 780, 870];
  const msgAnims = MSG_START.map((s) => ({
    op:    interpolate(f, [s, s + 32], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    tx:    interpolate(f, [s, s + 32], [-60, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scale: interpolate(f, [s, s + 32], [0.94, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
  }));
  const allVis2   = f >= 940;
  const ringPhase2 = allVis2 ? ((f - 940) % 80) / 80 : 0;
  const msgGlow = (i: number) => {
    if (!allVis2) return 0;
    const cnt = MSGS.length;
    const center = i / cnt + 1 / (cnt * 2);
    const dist = Math.min(Math.abs(ringPhase2 - center), 1 - Math.abs(ringPhase2 - center));
    return Math.max(0, 1 - dist * cnt * 1.8);
  };

  // ── Phase 3: "전부 자동으로요." ──
  const scan3Y  = interpolate(f, [1080, 1118], [-2, 104], { extrapolateRight: 'clamp' });
  const scan3Op = interpolate(f, [1080, 1085, 1113, 1118], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const scan3X  = interpolate(f, [1080, 1118], [-2, 104], { extrapolateRight: 'clamp' });
  const pre3Op   = interpolate(f, [1130, 1160], [0, 1], { extrapolateRight: 'clamp' });
  const ph3t1Op  = interpolate(f, [1160, 1198], [0, 1], { extrapolateRight: 'clamp' });
  const ph3t1Y   = interpolate(f, [1160, 1198], [-60, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const ph3t1Ls  = interpolate(f, [1160, 1198], [20, 0], { extrapolateRight: 'clamp' });
  const ph3t2Op  = interpolate(f, [1198, 1238], [0, 1], { extrapolateRight: 'clamp' });
  const ph3t2Y   = interpolate(f, [1198, 1238], [60, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const ph3zoom  = interpolate(f, [1080, 1380], [1, 1.04], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const burst3Op    = interpolate(f, [1250, 1258, 1285], [0, 0.6, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const burst3Scale = interpolate(f, [1250, 1285], [0.2, 3.0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const pulse3   = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz3     = interpolate(pulse3, [0, 1], [14, 40]);
  const breathe3 = ph3t2Op > 0.9 ? Math.sin(f * 0.08) * 0.025 + 1 : 1;
  const dynGlow3 = ph3t2Op > 0.9
    ? `0 0 ${gSz3}px #00FFD0, 0 0 ${gSz3 * 2}px rgba(0,255,208,0.6), 0 0 ${gSz3 * 4}px rgba(0,191,154,0.35)`
    : GLOW.mid.text;

  // 자막
  const cap1Op = showPh1 > 0.5 ? interpolate(f, [160, 210], [0, 1], { extrapolateRight: 'clamp' }) : 0;
  const cap2Op = showPh2 > 0.1 ? interpolate(f, [640, 680], [0, 1], { extrapolateRight: 'clamp' }) : 0;
  const cap3Op = showPh3 > 0 ? interpolate(f, [1290, 1330], [0, 1], { extrapolateRight: 'clamp' }) : 0;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow,
      }} />

      {/* Phase1 스캔라인 */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: `${scan1Y}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scan1Op * showPh1, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* Phase2 수직 스캔 */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: `${scan2X}%`, width: 2,
        background: 'linear-gradient(180deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scan2Op, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* Phase3 크로스 스캔 */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: `${scan3Y}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scan3Op, zIndex: 10, pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: `${scan3X}%`, width: 2,
        background: 'linear-gradient(180deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scan3Op, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* ══ PHASE 1: 질문 훅 ══ */}
      <AbsoluteFill style={{ opacity: showPh1, pointerEvents: 'none' }}>
        {/* 버스트 */}
        <div style={{
          position: 'absolute', top: '45%', left: '50%',
          width: 560, height: 560, marginLeft: -280, marginTop: -280,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
          opacity: burst1Op, transform: `scale(${burst1Scale})`, pointerEvents: 'none',
        }} />
        <div style={{
          transform: `scale(${zoom1})`, transformOrigin: 'center center',
          width: '100%', height: '100%',
        }}>
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 10,
          }}>
            <div style={{
              fontSize: 28, fontWeight: 500, color: C.textSub, letterSpacing: 5,
              opacity: label1Op, marginBottom: 20,
            }}>궁금하실 텐데요</div>

            <div style={{
              fontSize: 130, fontWeight: 900, color: C.textPrimary,
              opacity: t1Op, transform: `translateY(${t1Y}px)`,
              letterSpacing: t1Ls, lineHeight: 1.05,
            }}>저 이런 거</div>

            <div style={{
              fontSize: 130, fontWeight: 900, color: C.main,
              opacity: t2Op,
              transform: `translateY(${t2Y}px) scale(${breathe1})`,
              textShadow: dynGlow1, lineHeight: 1.05,
            }}>어떻게 알았냐고요?</div>

            <div style={{
              opacity: sub1Op,
              color: C.textSub, fontSize: 30, fontWeight: 500, marginTop: 32, letterSpacing: 1,
            }}>국민성장펀드 발표 당일 아침, 이미 알고 있었어요.</div>
          </div>
        </div>
      </AbsoluteFill>

      {/* ══ PHASE 2: 텔레그램 목업 ══ */}
      <AbsoluteFill style={{ opacity: showPh2, pointerEvents: 'none' }}>
        <div style={{
          position: 'absolute', top: 40, left: 120, right: 120, bottom: '18%',
          display: 'flex', flexDirection: 'column', gap: 18,
        }}>
          {/* 채널 헤더 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 20,
            opacity: headerOp, marginBottom: 8,
          }}>
            <div style={{
              width: 54, height: 54, borderRadius: '50%',
              background: 'linear-gradient(135deg, #00FFD0 0%, #0099AA 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 26, flexShrink: 0,
            }}>📡</div>
            <div>
              <div style={{ color: C.main, fontSize: 26, fontWeight: 700, textShadow: GLOW.weak.text }}>
                STOCK BRAIN 브리핑
              </div>
              <div style={{ color: C.textSub, fontSize: 18, fontWeight: 500 }}>매일 07:03 자동 발송</div>
            </div>
            <div style={{ marginLeft: 'auto', color: C.textSub, fontSize: 18 }}>오늘</div>
          </div>

          {/* 메시지 카드 4개 */}
          {MSGS.map((msg, i) => {
            const gOp = msgGlow(i);
            return (
              <div key={i} style={{
                opacity: msgAnims[i].op,
                transform: `translateX(${msgAnims[i].tx}px) scale(${msgAnims[i].scale})`,
                background: C.cardBg,
                border: `1px solid ${gOp > 0.3 ? C.main : C.borderSub}`,
                borderRadius: 14, padding: '16px 24px',
                display: 'flex', alignItems: 'flex-start', gap: 20,
                boxShadow: gOp > 0.2 ? `0 0 ${14 * gOp}px rgba(0,255,208,${0.5 * gOp})` : undefined,
              }}>
                <div style={{ fontSize: 38, lineHeight: 1, flexShrink: 0, marginTop: 4 }}>{msg.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                    <div style={{
                      background: C.mainDark, border: `1px solid ${C.borderActive}`,
                      borderRadius: 6, padding: '2px 10px',
                      color: C.main, fontSize: 15, fontWeight: 700, letterSpacing: 2,
                    }}>{msg.tag}</div>
                    <div style={{ color: C.textPrimary, fontSize: 24, fontWeight: 700 }}>{msg.title}</div>
                  </div>
                  <div style={{
                    color: C.textSub, fontSize: 20, fontWeight: 500,
                    lineHeight: 1.65, whiteSpace: 'pre-line',
                  }}>{msg.body}</div>
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>

      {/* ══ PHASE 3: "전부 자동으로요." ══ */}
      <AbsoluteFill style={{ opacity: showPh3, pointerEvents: 'none' }}>
        <div style={{
          transform: `scale(${ph3zoom})`, transformOrigin: 'center center',
          width: '100%', height: '100%',
        }}>
          {/* 버스트 */}
          <div style={{
            position: 'absolute', top: '48%', left: '50%',
            width: 600, height: 600, marginLeft: -300, marginTop: -300,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
            opacity: burst3Op, transform: `scale(${burst3Scale})`, pointerEvents: 'none',
          }} />
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 16,
          }}>
            <div style={{
              opacity: pre3Op,
              color: C.textSub, fontSize: 34, fontWeight: 500, letterSpacing: 3,
            }}>리포트·유튜브·뉴스·정책까지</div>

            <div style={{
              fontSize: 150, fontWeight: 900, color: C.textPrimary,
              opacity: ph3t1Op,
              transform: `translateY(${ph3t1Y}px)`,
              letterSpacing: ph3t1Ls, lineHeight: 1,
            }}>전부</div>

            <div style={{
              fontSize: 150, fontWeight: 900, color: C.main,
              opacity: ph3t2Op,
              transform: `translateY(${ph3t2Y}px) scale(${breathe3})`,
              textShadow: dynGlow3, lineHeight: 1,
            }}>자동으로요.</div>
          </div>
        </div>
      </AbsoluteFill>

      {/* 하단 자막 바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80, opacity: cap1Op,
        }}>발표 당일 아침&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>이미 알람이 와 있었어요.</span>
        </div>
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80, opacity: cap2Op,
        }}>리포트·유튜브·뉴스·정책&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>한 번에 정리</span>
        </div>
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80, opacity: cap3Op,
        }}>매일 아침&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>자동으로 받습니다.</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
