// GB02 — 씬2 리스트형 (45초 = 1350프레임)
// 리스트형: 24프레임 stagger + 카드 내부 스캔 + 순환 글로우
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO = 'audio/국씬2.m4a';
const HAS_AUDIO = true;

// Whisper: 총 463프레임(15.44s) / [01]f0~136 / [02]f152~225 / [03]f257~329 / [04]f352~463
// 대사: 소득공제40%+정부손실방어 → 무조건넣어야할것같죠? → 조건이하나 → ETF가훨씬더
// Card1·2: 혜택(seg1) / Card3: 반전(seg3)
const CARD_START = [60, 110, 257];

const CONDITIONS = [
  {
    icon: '📈',
    title: '소득공제 40%',
    desc: '납입액의 40% 소득공제\n절세 효과 연 최대 264만원',
    warn: false,
  },
  {
    icon: '🛡️',
    title: '정부 손실 방어',
    desc: '원금 손실 일부를 정부 보전\n하락장에서도 안전망 역할',
    warn: false,
  },
  {
    icon: '⚠️',
    title: '근데 조건이 있어요',
    desc: '이 조건 하나가 안 맞으면\nETF가 훨씬 더 많이 법니다',
    warn: true,
  },
];

const TOTAL = CONDITIONS.length;

export const GB02_Checklist = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });

  // ── 배경 글로우 (리스트형 기준) ──
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  // ── 수직 스캔라인 좌→우 (데이터 로딩, f0-38) ──
  const scanX  = interpolate(f, [0, 38], [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // ── 라벨 (f10-30) ──
  const labelOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // ── 타이틀 (f22-48, 100px Y슬라이드) ──
  const titleY  = interpolate(f, [22, 48], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const titleOp = interpolate(f, [22, 48], [0, 1],  { extrapolateRight: 'clamp' });

  // ── 카드 stagger ──
  const cards = CARD_START.map((s) => ({
    op:    interpolate(f, [s, s + 22], [0, 1],   { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    tx:    interpolate(f, [s, s + 22], [-80, 0],  { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scale: interpolate(f, [s, s + 22], [0.92, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    scanY: interpolate(f, [s + 10, s + 28], [0, 110], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    scanO: interpolate(f, [s + 10, s + 15, s + 24, s + 28], [0, 0.9, 0.9, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
    // 체크마크: 카드 등장 후 40프레임 뒤 elastic (압축)
    checkScale: interpolate(f, [s + 40, s + 62], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) }),
    checkOp:    interpolate(f, [s + 40, s + 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
  }));

  // ── 순환 글로우 (f >= 310, 60프레임 주기) ──
  const allVisible = f >= 310;
  const ringPhase = allVisible ? ((f - 310) % 60) / 60 : 0;
  const cardGlow = (i: number) => {
    if (!allVisible) return 0;
    const center = i / TOTAL + 1 / (TOTAL * 2);
    const dist = Math.min(Math.abs(ringPhase - center), 1 - Math.abs(ringPhase - center));
    return Math.max(0, 1 - dist * TOTAL * 1.8);
  };

  // ── 판결 박스 (f352 "이 조건이 안 맞으면 반도체 ETF") ──
  const verdictOp = interpolate(f, [352, 410], [0, 1], { extrapolateRight: 'clamp' });
  const verdictY  = interpolate(f, [352, 410], [20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── 자막 바 (f380-420) ──
  const capOp = interpolate(f, [380, 420], [0, 1], { extrapolateRight: 'clamp' });


  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow,
      }} />

      {/* 수직 스캔라인 */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0,
        left: `${scanX}%`, width: 2,
        background: 'linear-gradient(180deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scanOp, zIndex: 10, pointerEvents: 'none',
      }} />

      {/* 콘텐츠 영역 (상단 82%) */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        paddingInline: 160, gap: 32,
      }}>

        {/* 라벨 */}
        <div style={{
          fontSize: 28, fontWeight: 500, color: C.textSub, letterSpacing: 5,
          opacity: labelOp, alignSelf: 'flex-start',
        }}>펀드 혜택</div>

        {/* 타이틀 */}
        <div style={{
          fontSize: 100, fontWeight: 900, color: C.textPrimary,
          opacity: titleOp,
          transform: `translateY(${titleY}px)`,
          alignSelf: 'flex-start', lineHeight: 1,
        }}>들으면&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.mid.text }}>넣어야 할 것 같죠?</span>
        </div>

        {/* 카드 3개 */}
        <div style={{ display: 'flex', gap: 24, width: '100%' }}>
          {CONDITIONS.map((cond, i) => {
            const gOp = cardGlow(i);
            const isWarn = cond.warn;
            const accentColor = isWarn ? '#FFB800' : C.main;
            return (
              <div key={i} style={{
                flex: 1,
                opacity: cards[i].op,
                transform: `translateX(${cards[i].tx}px) scale(${cards[i].scale})`,
                background: isWarn ? 'rgba(255,184,0,0.06)' : C.cardBg,
                border: `1.5px solid ${gOp > 0.3 ? accentColor : (isWarn ? 'rgba(255,184,0,0.4)' : C.borderSub)}`,
                borderRadius: 16, padding: '26px 32px',
                position: 'relative', overflow: 'hidden',
                boxShadow: gOp > 0.2 ? `0 0 ${16 * gOp}px rgba(${isWarn ? '255,184,0' : '0,255,208'},${0.6 * gOp})` : undefined,
              }}>

                {/* 카드 내부 스캔라인 */}
                <div style={{
                  position: 'absolute', left: 0, right: 0,
                  top: `${cards[i].scanY}%`, height: 1,
                  background: 'linear-gradient(90deg, transparent, rgba(0,255,208,0.6), transparent)',
                  opacity: cards[i].scanO,
                }} />

                {/* 번호 배지 */}
                <div style={{
                  width: 64, height: 64, borderRadius: 14,
                  background: accentColor, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginBottom: 16,
                  boxShadow: isWarn ? '0 0 12px rgba(255,184,0,0.4)' : GLOW.weak.box,
                }}>
                  <span style={{ fontSize: 30, fontWeight: 900, color: '#000' }}>0{i + 1}</span>
                </div>

                {/* 아이콘 */}
                <div style={{
                  fontSize: 68, marginBottom: 12,
                  filter: GLOW.weak.filter,
                }}>{cond.icon}</div>

                {/* 제목 */}
                <div style={{
                  fontSize: 42, fontWeight: 700,
                  color: gOp > 0.3 ? accentColor : (isWarn ? '#FFB800' : C.textPrimary),
                  lineHeight: 1.3, marginBottom: 12,
                }}>{cond.title}</div>

                {/* 설명 */}
                <div style={{
                  fontSize: 26, fontWeight: 500, color: C.textSub,
                  lineHeight: 1.65, whiteSpace: 'pre-line',
                }}>{cond.desc}</div>

                {/* 체크마크 */}
                <div style={{
                  position: 'absolute', top: 20, right: 20,
                  opacity: cards[i].checkOp,
                  transform: `scale(${cards[i].checkScale})`,
                  width: 48, height: 48,
                  background: C.main, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: GLOW.mid.box,
                }}>
                  <svg width="24" height="18" viewBox="0 0 24 18">
                    <path d="M2 9L9 16L22 2" stroke="#000" strokeWidth="3.5"
                      strokeLinecap="round" strokeLinejoin="round" fill="none" />
                  </svg>
                </div>

              </div>
            );
          })}
        </div>

        {/* 판결 박스 */}
        <div style={{
          opacity: verdictOp,
          transform: `translateY(${verdictY}px)`,
          width: '100%',
          border: `1.5px solid rgba(0,255,208,0.35)`,
          borderRadius: 14, padding: '22px 40px',
          background: 'rgba(0,255,208,0.04)',
          display: 'flex', justifyContent: 'space-around', alignItems: 'center',
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 4, marginBottom: 10 }}>
              조건 해당되면
            </div>
            <div style={{
              color: C.main, fontSize: 42, fontWeight: 900,
              textShadow: GLOW.mid.text,
            }}>✅ 펀드 GO</div>
          </div>
          <div style={{ width: 1, background: 'rgba(255,255,255,0.15)', alignSelf: 'stretch' }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 4, marginBottom: 10 }}>
              조건 안 맞으면
            </div>
            <div style={{
              color: '#FFB800', fontSize: 42, fontWeight: 900,
              border: '1.5px solid rgba(255,184,0,0.4)',
              padding: '4px 20px', borderRadius: 8,
            }}>⚡ ETF가 낫다</div>
          </div>
        </div>

      </div>

      {/* 하단 자막 바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: capOp,
      }}>
        <div style={{
          color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80,
        }}>
          이 조건이 안 맞으면&nbsp;
          <span style={{ color: '#FFB800' }}>반도체 ETF가 훨씬 더 많이 법니다</span>
        </div>
      </div>

    </AbsoluteFill>
  );
};
