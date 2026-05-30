// GB05 — 씬5 STOCK BRAIN 노출 (녹음 전 버전 — HAS_AUDIO=false)
// Phase1: STOCK BRAIN 브랜딩 + 4기능 카드 (2×2) → Phase2: "고정 댓글 확인해 보세요" CTA
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO = 'audio/국씬5.m4a';
const HAS_AUDIO = false;

const FEATURES = [
  {
    icon: '📺',
    title: '유튜브 핫채널 요약',
    desc: '주요 채널 12개 자동 수집\n핫이슈·종목 키워드 추출',
    tag: 'YouTube',
  },
  {
    icon: '💬',
    title: '텔레그램 채널 요약',
    desc: '구독 채널 자동 수집·분류\n정책·뉴스·이벤트 분리',
    tag: 'Telegram',
  },
  {
    icon: '📰',
    title: '뉴스 키워드 트렌드',
    desc: '금일 상위 키워드 자동 추출\n주요 키워드 순위별 정리',
    tag: 'News',
  },
  {
    icon: '📊',
    title: '리포트 인사이트',
    desc: '증권사 리포트 핵심만 추출\n오늘 주목 포인트 자동 정리',
    tag: 'Report',
  },
];

export const GB05_StockBrain = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  // ── Phase 전환 ──
  const showPh1 = f < 700 ? 1 : interpolate(f, [700, 760], [1, 0], { extrapolateRight: 'clamp' });
  const showPh2 = f < 760 ? 0 : interpolate(f, [760, 840], [0, 1], { extrapolateRight: 'clamp' });

  // ── Phase 1: 브랜딩 + 카드 ──
  // 스캔라인 f0-38
  const scan1Y  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scan1Op = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // 아이콘 elastic f5-30
  const iconScale = interpolate(f, [5, 30], [0.4, 1], {
    extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)),
  });
  const iconOp = interpolate(f, [5, 20], [0, 1], { extrapolateRight: 'clamp' });

  // STOCK (위→아래) f30-68
  const brand1Op = interpolate(f, [30, 68], [0, 1], { extrapolateRight: 'clamp' });
  const brand1Y  = interpolate(f, [30, 68], [-50, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const brand1Ls = interpolate(f, [30, 68], [18, 0], { extrapolateRight: 'clamp' });

  // BRAIN (아래→위) f55-95
  const brand2Op = interpolate(f, [55, 95], [0, 1], { extrapolateRight: 'clamp' });
  const brand2Y  = interpolate(f, [55, 95], [50, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const breathe  = brand2Op > 0.9 ? Math.sin(f * 0.08) * 0.025 + 1 : 1;
  const pulse    = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz      = interpolate(pulse, [0, 1], [14, 40]);
  const dynGlow  = brand2Op > 0.9
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.6), 0 0 ${gSz * 4}px rgba(0,191,154,0.35)`
    : GLOW.mid.text;

  // 슬로건 f110-160
  const sloganOp = interpolate(f, [110, 160], [0, 1], { extrapolateRight: 'clamp' });

  // 구분선 f160-200
  const divOp = interpolate(f, [160, 200], [0, 1], { extrapolateRight: 'clamp' });

  // 카드 stagger (2×2 → 좌상/우상/좌하/우하 순)
  const CARD_START = [200, 260, 320, 380];
  const cards = CARD_START.map((s) => ({
    op:    interpolate(f, [s, s + 36], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    ty:    interpolate(f, [s, s + 36], [32, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scale: interpolate(f, [s, s + 36], [0.93, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scanY: interpolate(f, [s + 10, s + 28], [0, 110], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    scanO: interpolate(f, [s + 10, s + 15, s + 24, s + 28], [0, 0.9, 0.9, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
  }));

  // 순환 글로우 (f >= 460, 70프레임 주기)
  const allVis  = f >= 460;
  const ringPh  = allVis ? ((f - 460) % 70) / 70 : 0;
  const cardGlow = (i: number) => {
    if (!allVis) return 0;
    const cnt = FEATURES.length;
    const center = i / cnt + 1 / (cnt * 2);
    const dist = Math.min(Math.abs(ringPh - center), 1 - Math.abs(ringPh - center));
    return Math.max(0, 1 - dist * cnt * 1.8);
  };

  // ── Phase 2: CTA ──
  // 크로스 스캔 f760-798
  const scan2Y  = interpolate(f, [760, 798], [-2, 104], { extrapolateRight: 'clamp' });
  const scan2X  = interpolate(f, [760, 798], [-2, 104], { extrapolateRight: 'clamp' });
  const scan2Op = interpolate(f, [760, 765, 793, 798], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // "어떻게 만들었는지는" (작은 서브)
  const subCta1Op = interpolate(f, [850, 900], [0, 1], { extrapolateRight: 'clamp' });
  const subCta1Y  = interpolate(f, [850, 900], [20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "따로 영상으로" (강조 아젠다형 메인)
  const ctaMain1Op = interpolate(f, [890, 940], [0, 1], { extrapolateRight: 'clamp' });
  const ctaMain1Y  = interpolate(f, [890, 940], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const ctaMain1Ls = interpolate(f, [890, 940], [16, 0], { extrapolateRight: 'clamp' });

  // "찍어뒀는데" (민트 강조 elastic)
  const ctaMain2Op    = interpolate(f, [940, 990], [0, 1], { extrapolateRight: 'clamp' });
  const ctaMain2Scale = interpolate(f, [940, 990], [0.6, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const ctaMain2Y     = interpolate(f, [940, 990], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 버스트 f1000-1030
  const burst2Op    = interpolate(f, [1000, 1008, 1033], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burst2Scale = interpolate(f, [1000, 1033], [0.2, 2.8], { extrapolateRight: 'clamp' });

  // 📌 버튼
  const btnOp    = interpolate(f, [1040, 1100], [0, 1], { extrapolateRight: 'clamp' });
  const btnScale = interpolate(f, [1040, 1100], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const btnMag   = Math.min(1, (f - 1040) / 60);
  const btnGlow  = `0 0 ${20 * btnMag}px rgba(0,255,208,${0.6 * btnMag}), 0 0 ${40 * btnMag}px rgba(0,255,208,${0.3 * btnMag})`;

  // Phase2 동적 글로우
  const pulse2   = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz2     = interpolate(pulse2, [0, 1], [14, 40]);
  const cliGlow2 = ctaMain2Op > 0.9
    ? `0 0 ${gSz2}px #00FFD0, 0 0 ${gSz2 * 2}px rgba(0,255,208,0.6), 0 0 ${gSz2 * 4}px rgba(0,191,154,0.35)`
    : GLOW.mid.text;
  const breathe2 = ctaMain2Op > 0.9 ? Math.sin(f * 0.08) * 0.02 + 1 : 1;
  const ph2zoom  = interpolate(f, [760, 1380], [1, 1.04], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 자막
  const cap1Op = showPh1 > 0.5 ? interpolate(f, [430, 470], [0, 1], { extrapolateRight: 'clamp' }) : 0;
  const cap2Op = showPh2 > 0.1 ? interpolate(f, [1100, 1140], [0, 1], { extrapolateRight: 'clamp' }) : 0;

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

      {/* Phase2 크로스 스캔 */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: `${scan2Y}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scan2Op, zIndex: 10, pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: `${scan2X}%`, width: 2,
        background: 'linear-gradient(180deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scan2Op, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* ══ PHASE 1: 브랜딩 + 카드 ══ */}
      <AbsoluteFill style={{ opacity: showPh1, pointerEvents: 'none' }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', paddingInline: 100, paddingTop: 48,
        }}>
          {/* 브랜드 헤더 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 32, marginBottom: 12,
          }}>
            {/* 🧠 아이콘 */}
            <div style={{
              fontSize: 72, opacity: iconOp,
              transform: `scale(${iconScale})`,
              filter: GLOW.weak.filter,
            }}>🧠</div>

            {/* STOCK / BRAIN */}
            <div>
              <div style={{
                fontSize: 96, fontWeight: 900, color: C.textPrimary,
                opacity: brand1Op,
                transform: `translateY(${brand1Y}px)`,
                letterSpacing: brand1Ls, lineHeight: 1,
              }}>STOCK</div>
              <div style={{
                fontSize: 96, fontWeight: 900, color: C.main,
                opacity: brand2Op,
                transform: `translateY(${brand2Y}px) scale(${breathe})`,
                textShadow: dynGlow, lineHeight: 1,
              }}>BRAIN</div>
            </div>
          </div>

          {/* 슬로건 */}
          <div style={{
            opacity: sloganOp,
            color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 3, marginBottom: 28,
          }}>300개 정보 중 오늘 써먹을 3가지만</div>

          {/* 구분선 */}
          <div style={{
            width: '100%', height: 1, background: 'rgba(0,255,208,0.2)',
            opacity: divOp, marginBottom: 36,
          }} />

          {/* 2×2 카드 그리드 */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, width: '100%',
            flex: 1,
          }}>
            {FEATURES.map((feat, i) => {
              const gOp = cardGlow(i);
              return (
                <div key={i} style={{
                  opacity: cards[i].op,
                  transform: `translateY(${cards[i].ty}px) scale(${cards[i].scale})`,
                  background: C.cardBg,
                  border: `1.5px solid ${gOp > 0.3 ? C.main : C.borderSub}`,
                  borderRadius: 16, padding: '24px 28px',
                  position: 'relative', overflow: 'hidden',
                  boxShadow: gOp > 0.2 ? `0 0 ${16 * gOp}px rgba(0,255,208,${0.55 * gOp})` : undefined,
                  display: 'flex', flexDirection: 'column', gap: 10,
                }}>
                  {/* 카드 내부 스캔라인 */}
                  <div style={{
                    position: 'absolute', left: 0, right: 0,
                    top: `${cards[i].scanY}%`, height: 1,
                    background: 'linear-gradient(90deg, transparent, rgba(0,255,208,0.6), transparent)',
                    opacity: cards[i].scanO,
                  }} />

                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div style={{ fontSize: 52, filter: GLOW.weak.filter }}>{feat.icon}</div>
                    <div>
                      <div style={{
                        color: gOp > 0.3 ? C.main : C.textPrimary,
                        fontSize: 30, fontWeight: 700, lineHeight: 1.2,
                      }}>{feat.title}</div>
                      <div style={{
                        color: C.textSub, fontSize: 16, fontWeight: 600, letterSpacing: 2,
                        marginTop: 4,
                      }}>{feat.tag}</div>
                    </div>
                  </div>
                  <div style={{
                    color: C.textSub, fontSize: 20, fontWeight: 500,
                    lineHeight: 1.65, whiteSpace: 'pre-line',
                  }}>{feat.desc}</div>
                </div>
              );
            })}
          </div>
        </div>
      </AbsoluteFill>

      {/* ══ PHASE 2: CTA "고정 댓글 확인해 보세요" ══ */}
      <AbsoluteFill style={{ opacity: showPh2, pointerEvents: 'none' }}>
        {/* 버스트 */}
        <div style={{
          position: 'absolute', top: '45%', left: '50%',
          width: 560, height: 560, marginLeft: -280, marginTop: -280,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
          opacity: burst2Op, transform: `scale(${burst2Scale})`, pointerEvents: 'none',
        }} />

        <div style={{
          transform: `scale(${ph2zoom})`, transformOrigin: 'center center',
          width: '100%', height: '100%',
        }}>
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 16,
          }}>
            <div style={{
              opacity: subCta1Op, transform: `translateY(${subCta1Y}px)`,
              color: C.textSub, fontSize: 34, fontWeight: 500, letterSpacing: 2,
            }}>어떻게 만들었는지는</div>

            <div style={{
              fontSize: 100, fontWeight: 900, color: C.textPrimary,
              opacity: ctaMain1Op, transform: `translateY(${ctaMain1Y}px)`,
              letterSpacing: ctaMain1Ls, lineHeight: 1,
            }}>따로 영상으로</div>

            <div style={{
              fontSize: 120, fontWeight: 900, color: C.main,
              opacity: ctaMain2Op,
              transform: `translateY(${ctaMain2Y}px) scale(${ctaMain2Scale * breathe2})`,
              textShadow: cliGlow2, lineHeight: 1,
            }}>찍어뒀습니다.</div>

            {/* 📌 버튼 */}
            <div style={{
              opacity: btnOp,
              transform: `scale(${btnScale})`,
              marginTop: 24,
              background: C.main, borderRadius: 16,
              padding: '20px 64px',
              boxShadow: btnGlow,
              display: 'flex', alignItems: 'center', gap: 16,
            }}>
              <span style={{ fontSize: 32 }}>📌</span>
              <span style={{
                fontSize: 38, fontWeight: 900, color: '#000000',
              }}>고정 댓글 확인해 보세요</span>
            </div>
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
        }}>
          AI가 매일&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>자동으로 정리해줍니다.</span>
        </div>
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80, opacity: cap2Op,
        }}>
          어떻게 만드는지&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>고정 댓글 영상에서 전부 공개합니다.</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
