// S8 플로우형 — AI 매매 파이프라인 4단계
// 자막: "데이터 수집부터 매매 실행까지, AI가 파이프라인을 잇습니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { Arrow } from '../components/Arrow';
import { C, FONT, GLOW } from '../constants';

const STEPS = [
  { icon: '📡', label: '데이터\n수집' },
  { icon: '🤖', label: 'AI\n분석' },
  { icon: '🎯', label: '신호\n포착' },
  { icon: '💹', label: '매매\n실행' },
];

export const Scene08 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const labelOp   = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const titleY    = interpolate(f, [22, 48], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const titleOp   = interpolate(f, [22, 48], [0, 1],  { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [140, 162], [0, 1], { extrapolateRight: 'clamp' });

  const stepAnims = STEPS.map((_, i) => {
    const start = 52 + i * 20;
    return {
      opacity: interpolate(f, [start, start + 20], [0, 1], { extrapolateRight: 'clamp' }),
      scale:   interpolate(f, [start, start + 20], [0.6, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) }),
    };
  });

  const arrowAnims = [0, 1, 2].map(i => ({
    opacity: interpolate(f, [64 + i * 20, 80 + i * 20], [0, 1], { extrapolateRight: 'clamp' }),
    scaleX:  interpolate(f, [64 + i * 20, 80 + i * 20], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
  }));

  // 파이프라인 순환 하이라이트 (frame 145 이후)
  const CYCLE_START = 145;
  const CYCLE_LEN   = 44;
  const cycleActive = f >= CYCLE_START;
  const cycleF      = cycleActive ? (f - CYCLE_START) % CYCLE_LEN : -1;

  const stepGlow = STEPS.map((_, i) => {
    if (!cycleActive) return 0;
    const peak = i * 11;
    return Math.max(0, 1 - Math.abs(cycleF - peak) / 8);
  });

  const descOp = interpolate(f, [138, 158], [0, 1], { extrapolateRight: 'clamp' });
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
        paddingInline: 100,
      }}>
        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 18,
        }}>AI 매매 파이프라인</div>

        {/* 타이틀 */}
        <div style={{
          color: C.textPrimary, fontSize: 100, fontWeight: 900,
          opacity: titleOp, transform: `translateY(${titleY}px)`,
          marginBottom: 60, textAlign: 'center',
        }}>
          4단계 <span style={{ color: C.main }}>자동 흐름</span>
        </div>

        {/* 플로우 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%', justifyContent: 'center' }}>
          {STEPS.map((step, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>

              {/* 박스 */}
              <div style={{
                opacity: stepAnims[i].opacity,
                transform: `scale(${stepAnims[i].scale})`,
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                background: (i === STEPS.length - 1 || stepGlow[i] > 0.3) ? C.cardBgActive : C.cardBg,
                border: `2px solid ${(i === STEPS.length - 1 || stepGlow[i] > 0.3) ? C.main : C.borderSub}`,
                borderRadius: 16, padding: '22px 24px', minWidth: 168,
                boxShadow: stepGlow[i] > 0.1
                  ? `0 0 ${20 * stepGlow[i]}px rgba(0,255,208,${0.8 * stepGlow[i]}), 0 0 ${40 * stepGlow[i]}px rgba(0,255,208,${0.3 * stepGlow[i]})`
                  : (i === STEPS.length - 1 && stepAnims[i].opacity > 0.5 ? GLOW.mid.box : undefined),
              }}>
                <div style={{
                  fontSize: 72, marginBottom: 14,
                  filter: (stepGlow[i] > 0.3 || i === STEPS.length - 1) ? GLOW.mid.filter : undefined,
                }}>{step.icon}</div>
                <div style={{
                  color: (stepGlow[i] > 0.3 || i === STEPS.length - 1) ? C.main : C.textPrimary,
                  fontSize: 28, fontWeight: 700,
                  textAlign: 'center', whiteSpace: 'pre-line', lineHeight: 1.4,
                  textShadow: stepGlow[i] > 0.3 ? GLOW.weak.text : undefined,
                }}>{step.label}</div>
              </div>

              {/* 화살표 */}
              {i < STEPS.length - 1 && (
                <div style={{ transform: `scaleX(${arrowAnims[i].scaleX})`, transformOrigin: 'left center' }}>
                  <Arrow
                    size={70}
                    opacity={arrowAnims[i].opacity}
                    color={stepGlow[i] > 0.3 || stepGlow[i + 1] > 0.3 ? C.main : C.mainMid}
                  />
                </div>
              )}

            </div>
          ))}
        </div>

        {/* 하단 설명 */}
        <div style={{
          marginTop: 44, color: C.textSub, fontSize: 32, fontWeight: 500,
          opacity: descOp, textAlign: 'center',
        }}>
          사람이 자료를 옮길 필요 없음 · <span style={{ color: C.main }}>완전 자동화</span>
        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          데이터 수집부터 매매 실행까지, AI가 파이프라인을 잇습니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
