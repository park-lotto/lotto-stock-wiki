// LS08 — 단어 폭격형 (핵심 정의)
// "주도주 = 수급 × 섹터 × 모멘텀" 단위별로 충돌 등장
// 자막: "이것이 주도주의 공식입니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const LS08 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 10], [0, 1], { extrapolateRight: 'clamp' });

  // "주도주" — 위에서 내려옴
  const w1Y   = interpolate(f, [8, 38], [-250, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const w1Op  = interpolate(f, [8, 32], [0, 1], { extrapolateRight: 'clamp' });
  const w1Scale = interpolate(f, [8, 38], [1.6, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "=" — 오른쪽에서
  const eqX   = interpolate(f, [38, 58], [300, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const eqOp  = interpolate(f, [38, 55], [0, 1], { extrapolateRight: 'clamp' });

  // "수급" — 왼쪽에서
  const w2X   = interpolate(f, [55, 78], [-350, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const w2Op  = interpolate(f, [55, 75], [0, 1], { extrapolateRight: 'clamp' });

  // "×" + "섹터" — 오른쪽에서
  const w3X   = interpolate(f, [75, 100], [350, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const w3Op  = interpolate(f, [75, 97], [0, 1], { extrapolateRight: 'clamp' });

  // "×" + "모멘텀" — 아래서
  const w4Y   = interpolate(f, [98, 122], [200, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.9)) });
  const w4Op  = interpolate(f, [98, 118], [0, 1], { extrapolateRight: 'clamp' });

  // 전체 완성 후 글로우 증폭
  const allDone = w4Op > 0.8;
  const completeGlowOp = interpolate(f, [122, 145], [0, 1], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [148, 168], [0, 1], { extrapolateRight: 'clamp' });

  const pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [14, 40]);
  const dynGlow = allDone && completeGlowOp > 0.2
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`
    : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 (완성 후) */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: completeGlowOp * 0.06 * (Math.sin(f * 0.04) * 0.3 + 0.7),
        pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 0,
      }}>
        {/* "주도주" */}
        <div style={{
          color: C.main, fontSize: 180, fontWeight: 900,
          opacity: w1Op, transform: `translateY(${w1Y}px) scale(${w1Scale})`,
          textShadow: allDone ? dynGlow : GLOW.mid.text,
          lineHeight: 1.1, letterSpacing: -4,
        }}>주도주</div>

        {/* 아래 줄: = 수급 × 섹터 × 모멘텀 */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'nowrap',
        }}>
          {/* = */}
          <div style={{
            color: C.textSub, fontSize: 110, fontWeight: 300,
            opacity: eqOp, transform: `translateX(${eqX}px)`,
            lineHeight: 1,
          }}>=</div>

          {/* 수급 */}
          <div style={{
            color: C.textPrimary, fontSize: 100, fontWeight: 900,
            opacity: w2Op, transform: `translateX(${w2X}px)`,
            lineHeight: 1,
          }}>수급</div>

          {/* × 섹터 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            opacity: w3Op, transform: `translateX(${w3X}px)`,
          }}>
            <div style={{ color: C.textSub, fontSize: 80, fontWeight: 300, lineHeight: 1 }}>×</div>
            <div style={{ color: C.textPrimary, fontSize: 100, fontWeight: 900, lineHeight: 1 }}>섹터</div>
          </div>

          {/* × 모멘텀 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            opacity: w4Op, transform: `translateY(${w4Y}px)`,
          }}>
            <div style={{ color: C.textSub, fontSize: 80, fontWeight: 300, lineHeight: 1 }}>×</div>
            <div style={{
              color: C.main, fontSize: 100, fontWeight: 900, lineHeight: 1,
              textShadow: dynGlow,
            }}>모멘텀</div>
          </div>
        </div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          이것이 주도주의 공식입니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
