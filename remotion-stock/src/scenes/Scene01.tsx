// S1 오프닝 — 임팩트형
// 자막: "주식 시장에 AI, 이미 시작됐습니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const Scene01 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const iconOp    = interpolate(f, [5, 28],  [0, 1], { extrapolateRight: 'clamp' });
  const iconScale = interpolate(f, [5, 28],  [0.4, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const labelOp   = interpolate(f, [22, 42], [0, 1], { extrapolateRight: 'clamp' });

  // Line 1 — 좌에서 슬라이드 + 자간 수축
  const t1X  = interpolate(f, [38, 68], [-180, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [38, 68], [0, 1],    { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [38, 68], [22, 0],   { extrapolateRight: 'clamp' });

  // Line 2 — 우에서 슬라이드 + 동적 N3 글로우
  const t2X  = interpolate(f, [55, 88], [180, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [55, 88], [0, 1],    { extrapolateRight: 'clamp' });

  const subOp = interpolate(f, [80, 105], [0, 1], { extrapolateRight: 'clamp' });

  // 스캔 라인 — 씬 시작 시 위→아래 1회
  const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // 글로우 버스트 (클라이맥스 ~ frame 90)
  const burstOp    = interpolate(f, [85, 92, 118], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burstScale = interpolate(f, [85, 118], [0.2, 2.8], { extrapolateRight: 'clamp' });

  // 배경 중앙 글로우 펄스
  const bgGlow = Math.sin(f * 0.04) * 0.035 + 0.05;

  // 동적 N3 글로우 + 브리드
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 34]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;
  const breathe = t2Op > 0.9 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 중앙 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 45%, rgba(0,255,208,1) 0%, transparent 65%)',
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

      {/* 글로우 버스트 */}
      <div style={{
        position: 'absolute', top: '45%', left: '50%',
        width: 560, height: 560, marginLeft: -280, marginTop: -280,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
        opacity: burstOp, transform: `scale(${burstScale})`, pointerEvents: 'none',
      }} />

      {/* 콘텐츠 */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{
          fontSize: 150, opacity: iconOp,
          transform: `scale(${iconScale})`,
          filter: GLOW.mid.filter, lineHeight: 1, marginBottom: 24,
        }}>📊</div>

        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 28,
        }}>2026 주식 시장</div>

        <div style={{
          color: C.textPrimary, fontSize: 148, fontWeight: 900,
          opacity: t1Op, transform: `translateX(${t1X}px)`,
          lineHeight: 1.1, letterSpacing: t1Ls,
        }}>AI 없이는</div>

        <div style={{
          color: C.main, fontSize: 148, fontWeight: 900,
          opacity: t2Op, transform: `translateX(${t2X}px) scale(${breathe})`,
          textShadow: t2Op > 0.5 ? dynGlow : undefined,
          lineHeight: 1.1,
        }}>못 버틴다</div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: subOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          주식 시장에 AI, 이미 시작됐습니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
