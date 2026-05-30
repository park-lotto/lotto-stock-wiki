// GB02 — 씬2 리스트형 (45초 = 1350프레임)
// 리스트형: 24프레임 stagger + 카드 내부 스캔 + 순환 글로우
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO = 'audio/GB02_voice.mp3';
const HAS_AUDIO = false;

const CARD_START = [200, 420, 640];

const CONDITIONS = [
  {
    icon: '💰',
    title: '소득공제 여유 확인',
    desc: '기타소득공제 연 한도 2,500만원\n이미 꽉 찼다면 절세 효과 없음',
  },
  {
    icon: '🔒',
    title: '5년간 안 써도 되는 돈',
    desc: '중도 해지 시 세금 추징 + 손실\n생활비·비상금은 절대 금지',
  },
  {
    icon: '📊',
    title: '금융소득 2,000만원 이하',
    desc: '금융소득종합과세 대상자는 불리\n가입 전 반드시 홈택스 확인',
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
    // 체크마크: 카드 등장 후 60프레임 뒤 elastic
    checkScale: interpolate(f, [s + 60, s + 82], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) }),
    checkOp:    interpolate(f, [s + 60, s + 70], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
  }));

  // ── 순환 글로우 (f >= 900, 60프레임 주기) ──
  const allVisible = f >= 900;
  const ringPhase = allVisible ? ((f - 900) % 60) / 60 : 0;
  const cardGlow = (i: number) => {
    if (!allVisible) return 0;
    const center = i / TOTAL + 1 / (TOTAL * 2);
    const dist = Math.min(Math.abs(ringPhase - center), 1 - Math.abs(ringPhase - center));
    return Math.max(0, 1 - dist * TOTAL * 1.8);
  };

  // ── 판결 박스 (f950-1030) ──
  const verdictOp = interpolate(f, [950, 1030], [0, 1], { extrapolateRight: 'clamp' });
  const verdictY  = interpolate(f, [950, 1030], [20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── 자막 바 (f1100-1130) ──
  const capOp = interpolate(f, [1100, 1130], [0, 1], { extrapolateRight: 'clamp' });

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
        }}>조건 분석</div>

        {/* 타이틀 */}
        <div style={{
          fontSize: 100, fontWeight: 900, color: C.textPrimary,
          opacity: titleOp,
          transform: `translateY(${titleY}px)`,
          alignSelf: 'flex-start', lineHeight: 1,
        }}>조건이&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.mid.text }}>있습니다.</span>
        </div>

        {/* 카드 3개 */}
        <div style={{ display: 'flex', gap: 24, width: '100%' }}>
          {CONDITIONS.map((cond, i) => {
            const gOp = cardGlow(i);
            return (
              <div key={i} style={{
                flex: 1,
                opacity: cards[i].op,
                transform: `translateX(${cards[i].tx}px) scale(${cards[i].scale})`,
                background: C.cardBg,
                border: `1.5px solid ${gOp > 0.3 ? C.main : C.borderSub}`,
                borderRadius: 16, padding: '26px 32px',
                position: 'relative', overflow: 'hidden',
                boxShadow: gOp > 0.2 ? `0 0 ${16 * gOp}px rgba(0,255,208,${0.6 * gOp})` : undefined,
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
                  background: C.main, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginBottom: 16,
                  boxShadow: GLOW.weak.box,
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
                  color: gOp > 0.3 ? C.main : C.textPrimary,
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
              조건 3개 모두 해당
            </div>
            <div style={{
              color: C.main, fontSize: 42, fontWeight: 900,
              textShadow: GLOW.mid.text,
            }}>✅ 펀드 적합</div>
          </div>
          <div style={{ width: 1, background: 'rgba(255,255,255,0.15)', alignSelf: 'stretch' }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 4, marginBottom: 10 }}>
              하나라도 미해당
            </div>
            <div style={{
              color: C.textPrimary, fontSize: 42, fontWeight: 900,
              border: `1.5px solid rgba(255,255,255,0.25)`,
              padding: '4px 20px', borderRadius: 8,
            }}>ETF가 유리</div>
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
          하나라도 미해당이면&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>반도체 ETF가 유리합니다</span>
        </div>
      </div>

    </AbsoluteFill>
  );
};
