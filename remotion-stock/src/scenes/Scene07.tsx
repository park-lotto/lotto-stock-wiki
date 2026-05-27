// S7 핵심 메시지 — N3 강한 글로우 클라이맥스
// 자막: "빠른 자가 먼저 먹는 시대가 됐습니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const Scene07 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const iconOp    = interpolate(f, [8, 28],  [0, 1], { extrapolateRight: 'clamp' });
  const iconScale = interpolate(f, [8, 28],  [0.4, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const labelOp   = interpolate(f, [25, 45], [0, 1], { extrapolateRight: 'clamp' });

  // Line 1 — 위에서 슬라이드 + 자간
  const t1Y  = interpolate(f, [40, 68], [-60, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [40, 68], [0, 1],   { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [40, 68], [20, 0],  { extrapolateRight: 'clamp' });

  // Line 2 — 아래서 슬라이드 + 동적 N3 글로우 (클라이맥스)
  const t2Y  = interpolate(f, [58, 90], [60, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [58, 90], [0, 1],   { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [98, 120], [0, 1], { extrapolateRight: 'clamp' });

  // 스캔 라인
  const scanY  = interpolate(f, [0, 38],  [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // 글로우 버스트 (frame 92-125)
  const burstOp    = interpolate(f, [88, 95, 125], [0, 0.6, 0], { extrapolateRight: 'clamp' });
  const burstScale = interpolate(f, [88, 125], [0.2, 3.0], { extrapolateRight: 'clamp' });

  // 동적 펄스 글로우 (클라이맥스용)
  const pulse     = Math.sin(f * 0.08) * 0.5 + 0.5;
  const glowSize  = interpolate(pulse, [0, 1], [14, 40]);
  const dynGlow   = `0 0 ${glowSize}px rgba(0,255,208,0.95), 0 0 ${glowSize * 2}px rgba(0,255,208,0.5), 0 0 ${glowSize * 4}px rgba(0,191,154,0.28)`;
  const breathe   = t2Op > 0.9 ? Math.sin(f * 0.08) * 0.025 + 1 : 1;

  // 전체 씬 미세 줌인 (클라이맥스 느낌)
  const sceneZoom = interpolate(f, [0, 180], [1, 1.04], { extrapolateRight: 'clamp' });

  const bgGlow = Math.sin(f * 0.05) * 0.04 + 0.06;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 중앙 글로우 — 더 강하게 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 60%)',
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
        position: 'absolute', top: '48%', left: '50%',
        width: 600, height: 600, marginLeft: -300, marginTop: -300,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,255,208,0.32) 0%, transparent 70%)',
        opacity: burstOp, transform: `scale(${burstScale})`, pointerEvents: 'none',
      }} />

      {/* 콘텐츠 — 줌인 */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        transform: `scale(${sceneZoom})`,
      }}>
        {/* 아이콘 */}
        <div style={{
          fontSize: 150, opacity: iconOp,
          transform: `scale(${iconScale})`,
          filter: GLOW.strong.filter, lineHeight: 1, marginBottom: 24,
        }}>⚡</div>

        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 24,
        }}>시장의 법칙</div>

        {/* Line 1 — 흰색 */}
        <div style={{
          color: C.textPrimary, fontSize: 150, fontWeight: 900,
          opacity: t1Op, transform: `translateY(${t1Y}px)`,
          lineHeight: 1.1, letterSpacing: t1Ls,
        }}>빠른 자가</div>

        {/* Line 2 — 민트 + 펄스 글로우 */}
        <div style={{
          color: C.main, fontSize: 150, fontWeight: 900,
          opacity: t2Op,
          transform: `translateY(${t2Y}px) scale(${breathe})`,
          textShadow: t2Op > 0.5 ? dynGlow : undefined,
          lineHeight: 1.1,
        }}>먼저 먹는다</div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          빠른 자가 먼저 먹는 시대가 됐습니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
