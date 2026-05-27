// S10 클로징 — 채널 구독 유도 + 펄스 글로우
// 자막: "로또의 주식 — 구독과 알림 설정 부탁드립니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

// 배경 파티클 — 위로 천천히 떠오름
const PARTICLES = [
  { x: 15, startY: 85, delay: 0,  size: 6 },
  { x: 35, startY: 90, delay: 20, size: 4 },
  { x: 62, startY: 82, delay: 10, size: 8 },
  { x: 80, startY: 88, delay: 35, size: 5 },
  { x: 50, startY: 92, delay: 45, size: 4 },
  { x: 25, startY: 78, delay: 55, size: 6 },
];

export const Scene10 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const iconOp    = interpolate(f, [8, 30],  [0, 1], { extrapolateRight: 'clamp' });
  const iconScale = interpolate(f, [8, 30],  [0.4, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  // 채널명 — 아래서 슬라이드 + 자간
  const t1Y  = interpolate(f, [38, 68], [70, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [38, 68], [0, 1],  { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [38, 68], [12, -2], { extrapolateRight: 'clamp' });

  const t2Y  = interpolate(f, [62, 90], [30, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [62, 90], [0, 1],  { extrapolateRight: 'clamp' });

  // 구독 버튼 — 일래스틱
  const btnOp    = interpolate(f, [88, 115], [0, 1],   { extrapolateRight: 'clamp' });
  const btnScale = interpolate(f, [88, 115], [0.7, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  const captionOp = interpolate(f, [118, 140], [0, 1], { extrapolateRight: 'clamp' });

  // 버튼 펄스 — 강도가 시간에 따라 강해짐
  const pulseMag   = Math.min(1, (f - 88) / 40);
  const pulseRaw   = Math.sin(f * 0.1) * 0.5 + 0.5;
  const pGlowSize  = interpolate(pulseRaw, [0, 1], [10, 28 + 12 * pulseMag]);
  const pulseGlow  = `0 0 ${pGlowSize}px rgba(0,255,208,0.9), 0 0 ${pGlowSize * 2}px rgba(0,255,208,0.4)`;

  // 아이콘 펄스
  const iconPulse  = iconOp > 0.8 ? `drop-shadow(0 0 ${pGlowSize}px #00FFD0)` : GLOW.mid.filter;

  // 배경 글로우 — 점점 강해짐
  const bgGlowBase = Math.sin(f * 0.05) * 0.04 + 0.06;
  const bgGlowAmp  = interpolate(f, [88, 170], [0, 0.06], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 60%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: bgGlowBase + bgGlowAmp, pointerEvents: 'none',
      }} />

      {/* 배경 파티클 */}
      {PARTICLES.map((p, i) => {
        const age = f - p.delay;
        if (age < 0) return null;
        const progress = (age % 90) / 90;
        const y = p.startY - progress * 50;
        const op = progress < 0.2 ? progress / 0.2 : progress > 0.7 ? (1 - progress) / 0.3 : 1;
        return (
          <div key={i} style={{
            position: 'absolute',
            left: `${p.x}%`, top: `${y}%`,
            width: p.size, height: p.size, borderRadius: '50%',
            background: C.main,
            opacity: op * 0.55,
            boxShadow: `0 0 ${p.size * 2}px rgba(0,255,208,0.8)`,
            pointerEvents: 'none',
          }} />
        );
      })}

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        {/* 아이콘 */}
        <div style={{
          fontSize: 150, opacity: iconOp,
          transform: `scale(${iconScale})`,
          filter: iconPulse, lineHeight: 1, marginBottom: 32,
        }}>💹</div>

        {/* 채널명 — 민트 글로우 */}
        <div style={{
          fontSize: 160, fontWeight: 900,
          opacity: t1Op,
          transform: `translateY(${t1Y}px)`,
          letterSpacing: t1Ls,
          color: C.main,
          textShadow: GLOW.strong.text,
          lineHeight: 1.15,
        }}>로또의 주식</div>

        {/* 서브 슬로건 */}
        <div style={{
          color: C.textSub, fontSize: 38, fontWeight: 500,
          opacity: t2Op, transform: `translateY(${t2Y}px)`,
          marginTop: 16, marginBottom: 52, letterSpacing: 1,
        }}>수급 · 매물대 · 실전 매매의 모든 것</div>

        {/* 구독 버튼 */}
        <div style={{
          opacity: btnOp,
          transform: `scale(${btnScale})`,
          background: C.main,
          borderRadius: 16,
          padding: '22px 72px',
          boxShadow: btnOp > 0.5 ? pulseGlow : undefined,
          display: 'flex', alignItems: 'center', gap: 16,
        }}>
          <span style={{ fontSize: 46 }}>🔔</span>
          <span style={{ color: '#000000', fontSize: 46, fontWeight: 900, letterSpacing: 1 }}>
            구독 &amp; 알림 설정
          </span>
        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          로또의 주식 — 구독과 알림 설정 부탁드립니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
