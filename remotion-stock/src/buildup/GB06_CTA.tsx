// GB06 — 씬6 CTA 클로징 (녹음 전 버전 — HAS_AUDIO=false)
// Phase1: 다음 영상 예고 (섹터+수급빈집) → Phase2: 채널명 + 구독 버튼 클로징
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO = 'audio/국씬6.m4a';
const HAS_AUDIO = false;

const NEXT_ITEMS = [
  { icon: '🤖', tag: '다음 영상', title: 'STOCK BRAIN 세팅 방법', desc: '나처럼 자동화하는 법 처음부터 공개' },
  { icon: '📱', tag: 'STOCK BRAIN', title: '실제 브리핑 화면 그대로', desc: '매일 아침 자동으로 받는 정보 공개' },
];

export const GB06_CTA = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.045;

  // ── Phase 전환 ──
  const showPh1 = f < 490 ? 1 : interpolate(f, [490, 550], [1, 0], { extrapolateRight: 'clamp' });
  const showPh2 = f < 550 ? 0 : interpolate(f, [550, 620], [0, 1], { extrapolateRight: 'clamp' });

  // ── Phase 1: 다음 영상 예고 ──
  // 대각선 스윕 f0-40
  const diagX  = interpolate(f, [0, 40], [-120, 120], { extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad) });
  const diagOp = interpolate(f, [0, 5, 32, 40], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  const label1Op = interpolate(f, [10, 40], [0, 1], { extrapolateRight: 'clamp' });

  // 타이틀 "다음 영상에서 보여드릴게요" f30-68
  const titleOp = interpolate(f, [30, 68], [0, 1], { extrapolateRight: 'clamp' });
  const titleY  = interpolate(f, [30, 68], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 카드 2개
  const CARD_S = [90, 180];
  const cardAnims = CARD_S.map((s) => ({
    op:    interpolate(f, [s, s + 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    tx:    interpolate(f, [s, s + 40], [-80, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scale: interpolate(f, [s, s + 40], [0.92, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scanY: interpolate(f, [s + 12, s + 30], [0, 110], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    scanO: interpolate(f, [s + 12, s + 17, s + 26, s + 30], [0, 0.9, 0.9, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
  }));

  // 순환 글로우 (f >= 260, 70프레임 주기)
  const allVis = f >= 260;
  const ringPh = allVis ? ((f - 260) % 70) / 70 : 0;
  const cardGlow = (i: number) => {
    if (!allVis) return 0;
    const cnt = NEXT_ITEMS.length;
    const center = i / cnt + 1 / (cnt * 2);
    const dist = Math.min(Math.abs(ringPh - center), 1 - Math.abs(ringPh - center));
    return Math.max(0, 1 - dist * cnt * 1.8);
  };

  // 구독 유도 한 줄
  const sub1Op = interpolate(f, [300, 360], [0, 1], { extrapolateRight: 'clamp' });
  const sub1Y  = interpolate(f, [300, 360], [20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── Phase 2: 채널 클로징 ──
  // 대각선 스윕 다시
  const diag2X  = interpolate(f, [550, 590], [-120, 120], { extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad) });
  const diag2Op = interpolate(f, [550, 555, 582, 590], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // 채널 아이콘 elastic
  const ch_iconScale = interpolate(f, [605, 640], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(1)),
  });
  const ch_iconOp = interpolate(f, [605, 620], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 채널명 f640-680
  const chNameOp  = interpolate(f, [640, 680], [0, 1], { extrapolateRight: 'clamp' });
  const chNameY   = interpolate(f, [640, 680], [70, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const chNameLs  = interpolate(f, [640, 680], [12, -2], { extrapolateRight: 'clamp' });

  // 슬로건 f680-710
  const sloganOp = interpolate(f, [680, 710], [0, 1], { extrapolateRight: 'clamp' });
  const sloganY  = interpolate(f, [680, 710], [30, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 구독 버튼 elastic f720-755
  const btnOp    = interpolate(f, [720, 755], [0, 1], { extrapolateRight: 'clamp' });
  const btnScale = interpolate(f, [720, 755], [0.4, 1], {
    extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)),
  });
  const btnMag = Math.min(1, (f - 720) / 50);
  const btnPulse = Math.sin(f * 0.1) * 0.5 + 0.5;
  const btnGlow  = `0 0 ${interpolate(btnPulse, [0, 1], [16, 32]) * btnMag}px rgba(0,255,208,${0.7 * btnMag}), 0 0 ${interpolate(btnPulse, [0, 1], [24, 48]) * btnMag}px rgba(0,255,208,${0.35 * btnMag})`;

  // 파티클 (6개, 위로 이동)
  const PARTICLES = [
    { x: 22, delay: 10, size: 5 }, { x: 38, delay: 25, size: 7 },
    { x: 55, delay: 5,  size: 4 }, { x: 68, delay: 35, size: 6 },
    { x: 78, delay: 15, size: 5 }, { x: 88, delay: 40, size: 4 },
  ];

  // 배경 글로우 증폭 (구독버튼 이후)
  const bgGlowAmp = interpolate(f, [720, 870], [0, 0.06], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const bgGlowPh2 = Math.sin(f * 0.05) * 0.04 + 0.06 + bgGlowAmp;

  // Phase2 아이콘 펄스
  const iconPulse = Math.sin(f * 0.08) * 0.015 + 1;

  const cap1Op = showPh1 > 0.5 ? interpolate(f, [220, 260], [0, 1], { extrapolateRight: 'clamp' }) : 0;
  const cap2Op = showPh2 > 0.1 ? interpolate(f, [760, 800], [0, 1], { extrapolateRight: 'clamp' }) : 0;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: showPh2 > 0.5 ? bgGlowPh2 : bgGlow,
      }} />

      {/* Phase1 대각선 스윕 */}
      <div style={{
        position: 'absolute', top: '-20%', bottom: '-20%',
        left: `${diagX}%`, width: 60,
        background: 'linear-gradient(90deg, transparent 0%, rgba(0,255,208,0.6) 40%, rgba(128,255,232,0.9) 50%, rgba(0,255,208,0.6) 60%, transparent 100%)',
        transform: 'rotate(30deg)', transformOrigin: 'center center',
        opacity: diagOp * showPh1, pointerEvents: 'none', zIndex: 10,
      }} />

      {/* Phase2 대각선 스윕 */}
      <div style={{
        position: 'absolute', top: '-20%', bottom: '-20%',
        left: `${diag2X}%`, width: 60,
        background: 'linear-gradient(90deg, transparent 0%, rgba(0,255,208,0.6) 40%, rgba(128,255,232,0.9) 50%, rgba(0,255,208,0.6) 60%, transparent 100%)',
        transform: 'rotate(30deg)', transformOrigin: 'center center',
        opacity: diag2Op, pointerEvents: 'none', zIndex: 10,
      }} />

      {/* ══ PHASE 1: 다음 영상 예고 ══ */}
      <AbsoluteFill style={{ opacity: showPh1, pointerEvents: 'none' }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          paddingInline: 140, gap: 28,
        }}>
          <div style={{
            fontSize: 28, fontWeight: 500, color: C.textSub, letterSpacing: 5,
            opacity: label1Op,
          }}>다음 영상 예고</div>

          <div style={{
            fontSize: 80, fontWeight: 900, color: C.textPrimary,
            opacity: titleOp, transform: `translateY(${titleY}px)`,
            lineHeight: 1, textAlign: 'center',
          }}>다음 영상에서&nbsp;
            <span style={{ color: C.main, textShadow: GLOW.mid.text }}>보여드릴게요</span>
          </div>

          {/* 예고 카드 2개 */}
          <div style={{ display: 'flex', gap: 28, width: '100%' }}>
            {NEXT_ITEMS.map((item, i) => {
              const gOp = cardGlow(i);
              return (
                <div key={i} style={{
                  flex: 1,
                  opacity: cardAnims[i].op,
                  transform: `translateX(${cardAnims[i].tx}px) scale(${cardAnims[i].scale})`,
                  background: C.cardBg,
                  border: `1.5px solid ${gOp > 0.3 ? C.main : C.borderSub}`,
                  borderRadius: 16, padding: '28px 32px',
                  position: 'relative', overflow: 'hidden',
                  boxShadow: gOp > 0.2 ? `0 0 ${16 * gOp}px rgba(0,255,208,${0.55 * gOp})` : undefined,
                }}>
                  <div style={{
                    position: 'absolute', left: 0, right: 0,
                    top: `${cardAnims[i].scanY}%`, height: 1,
                    background: 'linear-gradient(90deg, transparent, rgba(0,255,208,0.6), transparent)',
                    opacity: cardAnims[i].scanO,
                  }} />

                  <div style={{ fontSize: 56, marginBottom: 16, filter: GLOW.weak.filter }}>{item.icon}</div>
                  <div style={{
                    color: C.textSub, fontSize: 20, fontWeight: 600, letterSpacing: 4, marginBottom: 8,
                  }}>{item.tag}</div>
                  <div style={{
                    color: gOp > 0.3 ? C.main : C.textPrimary,
                    fontSize: 36, fontWeight: 700, lineHeight: 1.3, marginBottom: 12,
                  }}>{item.title}</div>
                  <div style={{
                    color: C.textSub, fontSize: 22, fontWeight: 500, lineHeight: 1.6,
                  }}>{item.desc}</div>
                </div>
              );
            })}
          </div>

          {/* 구독 유도 */}
          <div style={{
            opacity: sub1Op, transform: `translateY(${sub1Y}px)`,
            color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 2,
          }}>구독하시면 놓치지 않습니다&nbsp;👇</div>
        </div>
      </AbsoluteFill>

      {/* ══ PHASE 2: 채널 클로징 ══ */}
      <AbsoluteFill style={{ opacity: showPh2, pointerEvents: 'none' }}>
        {/* 파티클 */}
        {PARTICLES.map((p, i) => {
          const age = (f - 550 - p.delay + 500) % 90;
          const progress = age / 90;
          const py = 75 - progress * 50;
          const partOp = progress < 0.2 ? progress / 0.2 : progress > 0.7 ? (1 - progress) / 0.3 : 1;
          return (
            <div key={i} style={{
              position: 'absolute', left: `${p.x}%`, top: `${py}%`,
              width: p.size, height: p.size, borderRadius: '50%',
              background: C.main,
              boxShadow: `0 0 ${p.size * 2}px ${C.main}`,
              opacity: Math.max(0, partOp) * 0.55 * (f > 600 ? 1 : 0),
              pointerEvents: 'none',
            }} />
          );
        })}

        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 16,
        }}>
          {/* 채널 아이콘 */}
          <div style={{
            fontSize: 80,
            opacity: ch_iconOp,
            transform: `scale(${ch_iconScale * iconPulse})`,
            filter: GLOW.mid.filter,
          }}>📈</div>

          {/* 채널명 */}
          <div style={{
            fontSize: 96, fontWeight: 900, color: C.main,
            opacity: chNameOp,
            transform: `translateY(${chNameY}px)`,
            letterSpacing: chNameLs,
            textShadow: GLOW.strong.text,
            lineHeight: 1,
          }}>로또의 주식인사이트</div>

          {/* 슬로건 */}
          <div style={{
            fontSize: 34, fontWeight: 500, color: C.textSub,
            opacity: sloganOp, transform: `translateY(${sloganY}px)`,
            letterSpacing: 2,
          }}>정보는 자동으로 — 판단은 내가</div>

          {/* 구독 버튼 */}
          <div style={{
            opacity: btnOp,
            transform: `scale(${btnScale})`,
            marginTop: 20,
            background: C.main, borderRadius: 16,
            padding: '22px 72px',
            boxShadow: btnGlow,
            display: 'flex', alignItems: 'center', gap: 14,
          }}>
            <span style={{ fontSize: 36 }}>🔔</span>
            <span style={{
              fontSize: 46, fontWeight: 900, color: '#000000',
            }}>구독 + 알림</span>
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
        }}><span style={{ color: C.main, textShadow: GLOW.weak.text }}>STOCK BRAIN 세팅 방법</span>
          &nbsp;다음 영상에서 공개합니다
        </div>
        <div style={{
          position: 'absolute',
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80, opacity: cap2Op,
        }}>구독 누르시면&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>놓치지 않습니다.</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
