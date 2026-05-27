// S3 속도 비교 — 바차트형 (회색 vs 민트)
// 자막: "사람은 하루 종일 걸리는 분석을, AI는 0.3초에 끝냅니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW, GRAD } from '../constants';

export const Scene03 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const labelOp   = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const titleY    = interpolate(f, [22, 48], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const titleOp   = interpolate(f, [22, 48], [0, 1],  { extrapolateRight: 'clamp' });

  // 바1 (사람) — 느리게 채워짐
  const bar1Prog  = interpolate(f, [45, 120], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const bar1Op    = interpolate(f, [42, 55],  [0, 1], { extrapolateRight: 'clamp' });

  // 바2 (AI) — 빠르게 채워짐
  const bar2Prog  = interpolate(f, [80, 110], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const bar2Op    = interpolate(f, [78, 92],  [0, 1], { extrapolateRight: 'clamp' });

  // 배지 — 바2 완료 후 팝인
  const badgeOp   = interpolate(f, [115, 130], [0, 1], { extrapolateRight: 'clamp' });
  const badgeScale= interpolate(f, [115, 130], [0.4, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const badgeRot  = interpolate(f, [115, 130], [-15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  const captionOp = interpolate(f, [108, 128], [0, 1], { extrapolateRight: 'clamp' });

  // AI 바 완료 후 펄스 글로우
  const barPulse    = bar2Prog >= 0.95 ? Math.sin(f * 0.1) * 0.5 + 0.5 : 0;
  const barGlowSize = interpolate(barPulse, [0, 1], [8, 20]);
  const barGlow     = `0 0 ${barGlowSize}px rgba(0,255,208,0.9), 0 0 ${barGlowSize * 2}px rgba(0,255,208,0.4)`;

  const BAR_MAX = 720;
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
        paddingInline: 180,
      }}>
        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 18,
        }}>분석 속도 비교</div>

        {/* 타이틀 */}
        <div style={{
          color: C.textPrimary, fontSize: 100, fontWeight: 900,
          opacity: titleOp, transform: `translateY(${titleY}px)`,
          marginBottom: 64, textAlign: 'center',
        }}>
          누가 <span style={{ color: C.main }}>더 빠를까?</span>
        </div>

        {/* Bar 1 — 사람 */}
        <div style={{ width: '100%', marginBottom: 36, opacity: bar1Op }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
            <span style={{ color: C.textSub, fontSize: 36, fontWeight: 700 }}>🧑 사람</span>
            <span style={{ color: C.textSub, fontSize: 36, fontWeight: 700 }}>하루 종일</span>
          </div>
          <div style={{ width: '100%', height: 44, background: '#1A1A1A', borderRadius: 999 }}>
            <div style={{
              width: bar1Prog * BAR_MAX, height: '100%',
              background: '#555555', borderRadius: 999,
            }} />
          </div>
        </div>

        {/* Bar 2 — AI */}
        <div style={{ width: '100%', opacity: bar2Op }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
            <span style={{ color: C.main, fontSize: 36, fontWeight: 700, textShadow: GLOW.weak.text }}>🤖 AI</span>
            <span style={{ color: C.main, fontSize: 36, fontWeight: 700, textShadow: GLOW.mid.text }}>0.3초</span>
          </div>
          <div style={{ width: '100%', height: 44, background: '#0A1F1A', borderRadius: 999 }}>
            <div style={{
              width: bar2Prog * (BAR_MAX * 0.07), height: '100%',
              background: GRAD.horizontal, borderRadius: 999,
              boxShadow: barGlow,
            }} />
          </div>
        </div>

        {/* 1000x 배지 */}
        <div style={{
          marginTop: 40,
          opacity: badgeOp,
          transform: `scale(${badgeScale}) rotate(${badgeRot}deg)`,
          display: 'flex', alignItems: 'center', gap: 16,
        }}>
          <span style={{
            color: C.main, fontSize: 60, fontWeight: 900,
            textShadow: GLOW.strong.text,
          }}>AI가 1,000배 빠르다</span>
          <span style={{ fontSize: 52 }}>⚡</span>
        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          사람은 하루 종일 걸리는 분석을, AI는 0.3초에 끝냅니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
