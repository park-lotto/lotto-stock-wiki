// S9 결론 — "AI는 도구 / 판단은 내가"
// 자막: "AI는 도구입니다. 판단은 여전히 내가 합니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const Scene09 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const iconOp    = interpolate(f, [8, 28],  [0, 1], { extrapolateRight: 'clamp' });
  const iconScale = interpolate(f, [8, 28],  [0.4, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const labelOp   = interpolate(f, [25, 45], [0, 1], { extrapolateRight: 'clamp' });

  // Line 1 — 좌에서 슬라이드 + 자간
  const t1X  = interpolate(f, [40, 68], [-120, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [40, 68], [0, 1],    { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [40, 68], [16, 0],   { extrapolateRight: 'clamp' });

  // Line 2 — 우에서 슬라이드
  const t2X  = interpolate(f, [60, 92], [120, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [60, 92], [0, 1],    { extrapolateRight: 'clamp' });

  const subY  = interpolate(f, [88, 115], [30, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const subOp = interpolate(f, [88, 115], [0, 1],   { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [110, 132], [0, 1], { extrapolateRight: 'clamp' });

  // 스캔 라인
  const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // 브리드
  const breathe = iconOp > 0.9 ? Math.sin(f * 0.06) * 0.015 + 1 : 1;

  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.045;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 스캔 라인 */}
      <div style={{
        position: 'absolute', left: 0, right: 0,
        top: `${scanY}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)',
        opacity: scanOp, zIndex: 10, pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        {/* 아이콘 */}
        <div style={{
          fontSize: 150, opacity: iconOp,
          transform: `scale(${iconScale * breathe})`,
          filter: GLOW.mid.filter, lineHeight: 1, marginBottom: 24,
        }}>💡</div>

        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 24,
        }}>결론</div>

        {/* Line 1 — AI는 도구다 */}
        <div style={{
          fontSize: 140, fontWeight: 900,
          opacity: t1Op, transform: `translateX(${t1X}px)`,
          lineHeight: 1.1, letterSpacing: t1Ls,
        }}>
          <span style={{ color: C.textPrimary }}>AI는 </span>
          <span style={{ color: C.main, textShadow: GLOW.mid.text }}>도구</span>
          <span style={{ color: C.textPrimary }}>다</span>
        </div>

        {/* Line 2 — 판단은 내가 한다 */}
        <div style={{
          color: C.textPrimary, fontSize: 110, fontWeight: 900,
          opacity: t2Op, transform: `translateX(${t2X}px)`,
          lineHeight: 1.1,
        }}>
          판단은 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>내가 한다</span>
        </div>

        {/* 보조 설명 */}
        <div style={{
          color: C.textSub, fontSize: 34, fontWeight: 500,
          opacity: subOp, transform: `translateY(${subY}px)`,
          marginTop: 40, paddingInline: 180, textAlign: 'center', lineHeight: 1.6,
        }}>
          AI는 속도와 데이터를 주고<br />
          나는 맥락과 판단을 더한다
        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          AI는 도구입니다. 판단은 여전히 내가 합니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
