// LS10 — 스포트라이트 클로징형
// 어둠 속에서 위에서 빛이 내려와 채널명을 비춤
// 자막: "로또의 주식 — 구독과 알림 설정 부탁드립니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

export const LS10 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 10], [0, 1], { extrapolateRight: 'clamp' });

  // 어두운 오버레이 (처음엔 완전히 어두움)
  const darkOp = interpolate(f, [0, 5], [1, 0.88], { extrapolateRight: 'clamp' });

  // 스포트라이트 빔 등장 + 좁혀짐
  const beamOp     = interpolate(f, [8, 38], [0, 1], { extrapolateRight: 'clamp' });
  const beamWidth  = interpolate(f, [8, 55], [80, 28], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 채널명 등장
  const nameOp    = interpolate(f, [42, 70], [0, 1], { extrapolateRight: 'clamp' });
  const nameY     = interpolate(f, [42, 70], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const nameScale = interpolate(f, [42, 70], [0.88, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 슬로건
  const sloganOp = interpolate(f, [68, 92], [0, 1], { extrapolateRight: 'clamp' });

  // 구독 버튼
  const btnOp    = interpolate(f, [95, 122], [0, 1], { extrapolateRight: 'clamp' });
  const btnScale = interpolate(f, [95, 122], [0.65, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  // 자막
  const captionOp = interpolate(f, [130, 152], [0, 1], { extrapolateRight: 'clamp' });

  // 채널명 민트 글로우 펄스
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 32]);
  const nameGlow = nameOp > 0.6
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5), 0 0 ${gSz * 4}px rgba(0,191,154,0.25)`
    : undefined;

  // 버튼 펄스
  const btnGlowSize = Math.sin(f * 0.1) * 0.5 + 0.5;
  const btnGlow = btnOp > 0.7
    ? `0 0 ${interpolate(btnGlowSize, [0, 1], [10, 30])}px rgba(0,255,208,0.9), 0 0 ${interpolate(btnGlowSize, [0, 1], [20, 60])}px rgba(0,255,208,0.4)`
    : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 어두운 오버레이 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: '#000000',
        opacity: darkOp * 0.72,
        pointerEvents: 'none',
      }} />

      {/* 스포트라이트 빔 (위→아래 원뿔) */}
      <div style={{
        position: 'absolute', top: 0, left: '50%',
        transform: 'translateX(-50%)',
        width: '80%', height: '72%',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.03) 70%, rgba(255,255,255,0) 100%)',
        clipPath: `polygon(${50 - beamWidth}% 0%, ${50 + beamWidth}% 0%, 75% 100%, 25% 100%)`,
        opacity: beamOp,
        pointerEvents: 'none',
      }} />

      {/* 빔 민트 헤일로 */}
      <div style={{
        position: 'absolute', top: '38%', left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 520, height: 220,
        background: 'radial-gradient(ellipse, rgba(0,255,208,0.07) 0%, transparent 70%)',
        opacity: beamOp, pointerEvents: 'none',
      }} />

      {/* 메인 콘텐츠 */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '16%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 0,
      }}>
        {/* 채널명 */}
        <div style={{
          color: C.main, fontSize: 148, fontWeight: 900,
          opacity: nameOp,
          transform: `translateY(${nameY}px) scale(${nameScale})`,
          textShadow: nameGlow,
          lineHeight: 1.15,
          marginBottom: 16,
        }}>로또의 주식</div>

        {/* 슬로건 */}
        <div style={{
          color: C.textSub, fontSize: 36, fontWeight: 500,
          opacity: sloganOp, letterSpacing: 2, marginBottom: 56,
        }}>수급 · 매물대 · 실전 매매의 모든 것</div>

        {/* 구독 버튼 */}
        <div style={{
          opacity: btnOp, transform: `scale(${btnScale})`,
          background: C.main, borderRadius: 18, padding: '22px 68px',
          boxShadow: btnGlow,
          display: 'flex', alignItems: 'center', gap: 16,
        }}>
          <span style={{ fontSize: 44 }}>🔔</span>
          <span style={{ color: '#000000', fontSize: 44, fontWeight: 900, letterSpacing: 1 }}>
            구독 &amp; 알림 설정
          </span>
        </div>
      </div>

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
