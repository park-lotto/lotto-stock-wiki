// S5 리스트형 — AI 핵심 기능 3가지 (넘버배지 + 카드 순차등장)
// 자막: "수급 자동 탐지, 뉴스 실시간 해석, 매수 타이밍 포착"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const ITEMS = [
  { icon: '📡', title: '수급 자동 탐지',   sub: '외인·기관 움직임 실시간 감지' },
  { icon: '📰', title: '뉴스 실시간 해석', sub: '호재·악재 0.3초 분류' },
  { icon: '🎯', title: '매수 타이밍 포착', sub: '빈집 + 촉매 교집합 자동 감지' },
];

const CARD_START = [48, 72, 96]; // 각 카드 등장 시작 프레임

export const Scene05 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const labelOp   = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const titleY    = interpolate(f, [22, 48], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const titleOp   = interpolate(f, [22, 48], [0, 1],  { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [120, 142], [0, 1], { extrapolateRight: 'clamp' });

  const itemAnims = ITEMS.map((_, i) => {
    const s = CARD_START[i];
    return {
      opacity: interpolate(f, [s, s + 22], [0, 1], { extrapolateRight: 'clamp' }),
      tx: interpolate(f, [s, s + 22], [-80, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
      scale: interpolate(f, [s, s + 22], [0.92, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
      // 카드 위를 가로지르는 스캔 라인
      scanY:  interpolate(f, [s + 10, s + 28], [0, 110], { extrapolateRight: 'clamp' }),
      scanOp: interpolate(f, [s + 10, s + 15, s + 24, s + 28], [0, 0.9, 0.9, 0], { extrapolateRight: 'clamp' }),
    };
  });

  // 모든 카드 등장 후 — 카드 경계선 글로우 순환 (frame 125 이후)
  const allVisible = f >= 125;
  const ringPhase  = allVisible ? ((f - 125) % 60) / 60 : 0;

  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        paddingInline: 160,
      }}>
        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 18,
        }}>AI 핵심 기능</div>

        {/* 타이틀 */}
        <div style={{
          color: C.textPrimary, fontSize: 100, fontWeight: 900,
          opacity: titleOp, transform: `translateY(${titleY}px)`,
          marginBottom: 44, textAlign: 'center',
        }}>
          AI가 <span style={{ color: C.main }}>대신 해주는 것</span>
        </div>

        {/* 카드 리스트 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
          {ITEMS.map((item, i) => {
            // 순환 글로우 — 각 카드가 차례로 밝아짐
            const cardCenter = i / ITEMS.length + 1 / (ITEMS.length * 2);
            const dist = Math.min(Math.abs(ringPhase - cardCenter), 1 - Math.abs(ringPhase - cardCenter));
            const ringOp = allVisible ? Math.max(0, 1 - dist * ITEMS.length * 1.8) : 0;

            return (
              <div
                key={i}
                style={{
                  position: 'relative', overflow: 'hidden',
                  display: 'flex', alignItems: 'center', gap: 28,
                  background: C.cardBg,
                  border: `1.5px solid ${ringOp > 0.3 ? C.main : C.borderSub}`,
                  borderRadius: 16,
                  padding: '26px 32px',
                  opacity: itemAnims[i].opacity,
                  transform: `translateX(${itemAnims[i].tx}px) scale(${itemAnims[i].scale})`,
                  boxShadow: ringOp > 0.2 ? `0 0 ${16 * ringOp}px rgba(0,255,208,${0.6 * ringOp})` : (itemAnims[i].opacity > 0.8 ? GLOW.weak.box : undefined),
                }}
              >
                {/* 카드 스캔 라인 */}
                <div style={{
                  position: 'absolute', left: 0, right: 0,
                  top: `${itemAnims[i].scanY}%`, height: 2,
                  background: 'linear-gradient(90deg, transparent, #00FFD0, transparent)',
                  opacity: itemAnims[i].scanOp, pointerEvents: 'none',
                }} />

                {/* 번호 배지 */}
                <div style={{
                  width: 64, height: 64, borderRadius: 14,
                  background: C.main, color: '#000',
                  fontSize: 30, fontWeight: 900,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>{i + 1}</div>

                {/* 아이콘 */}
                <div style={{
                  fontSize: 68, flexShrink: 0,
                  filter: ringOp > 0.3 ? GLOW.mid.filter : GLOW.weak.filter,
                }}>{item.icon}</div>

                {/* 텍스트 */}
                <div>
                  <div style={{
                    color: ringOp > 0.3 ? C.main : C.textPrimary,
                    fontSize: 42, fontWeight: 700, marginBottom: 6,
                    textShadow: ringOp > 0.3 ? GLOW.weak.text : undefined,
                  }}>{item.title}</div>
                  <div style={{ color: C.textSub, fontSize: 26, fontWeight: 500 }}>{item.sub}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          수급 자동 탐지, 뉴스 실시간 해석, 매수 타이밍 포착
        </div>
      </div>

    </AbsoluteFill>
  );
};
