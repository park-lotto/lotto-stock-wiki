// S4 아젠다형 — "3가지"
// 자막: "AI가 매매의 판도를 3가지로 바꿔놨습니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const Scene04 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const iconOp    = interpolate(f, [8, 28],  [0, 1], { extrapolateRight: 'clamp' });
  const iconScale = interpolate(f, [8, 28],  [0.4, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const labelOp   = interpolate(f, [25, 45], [0, 1], { extrapolateRight: 'clamp' });

  // 메인 타이틀 — 아래서 슬라이드 + 자간
  const t1Y  = interpolate(f, [40, 68], [60, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [40, 68], [0, 1],   { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [40, 68], [18, 0],  { extrapolateRight: 'clamp' });

  // "3가지" — 슈퍼 일래스틱 + 스케일 업
  const t2Op    = interpolate(f, [62, 92], [0, 1],    { extrapolateRight: 'clamp' });
  const t2Scale = interpolate(f, [62, 92], [0.5, 1],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const t2Y     = interpolate(f, [62, 92], [50, 0],   { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  const captionOp = interpolate(f, [95, 118], [0, 1], { extrapolateRight: 'clamp' });

  // 스캔 라인
  const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // "3가지" 동적 N3 글로우 + 브리드
  const pulse    = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz      = interpolate(pulse, [0, 1], [12, 36]);
  const dynGlow  = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.6), 0 0 ${gSz * 4}px rgba(0,191,154,0.35)`;
  const breathe  = t2Op > 0.9 ? Math.sin(f * 0.08) * 0.025 + 1 : 1;

  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.05;

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
          transform: `scale(${iconScale})`,
          filter: GLOW.mid.filter, lineHeight: 1, marginBottom: 24,
        }}>⚡</div>

        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 24,
        }}>AI가 바꾼 것</div>

        {/* 메인 타이틀 */}
        <div style={{
          color: C.textPrimary, fontSize: 140, fontWeight: 900,
          opacity: t1Op, transform: `translateY(${t1Y}px)`,
          lineHeight: 1.1, letterSpacing: t1Ls,
        }}>
          매매의 <span style={{ color: C.main }}>판도</span>
        </div>

        {/* "3가지" — 클라이맥스 */}
        <div style={{
          color: C.main, fontSize: 150, fontWeight: 900,
          opacity: t2Op,
          transform: `translateY(${t2Y}px) scale(${breathe * t2Scale})`,
          textShadow: t2Op > 0.5 ? dynGlow : undefined,
          lineHeight: 1.1, marginTop: 8,
        }}>3가지</div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          AI가 매매의 판도를 3가지로 바꿔놨습니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
