// BH07 — 배경 워터마크형 클라이맥스 (Layout G)
// 거대 배경 텍스트 "뉴스" + 선명한 전경 메시지. 깊이감.
// 자막: "뉴스 공개 시점에 기관은 이미 익절하고 있습니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

export const BH07 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 배경 워터마크 — 천천히 페이드인 + 미세 줌아웃
  const bgTextOp    = interpolate(f, [0, 65], [0, 0.065], { extrapolateRight: 'clamp' });
  const bgTextScale = interpolate(f, [0, 90], [1.1, 1.0], { extrapolateRight: 'clamp' });

  // 전경 Line1 "뉴스가 나오면"
  const fg1Op = interpolate(f, [32, 60], [0, 1], { extrapolateRight: 'clamp' });
  const fg1Y  = interpolate(f, [32, 60], [54, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 전경 Line2 "이미 늦다" — 탄성 팝인
  const fg2Op    = interpolate(f, [65, 94], [0, 1], { extrapolateRight: 'clamp' });
  const fg2Scale = interpolate(f, [65, 94], [0.55, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.1)) });

  // 씬 전체 줌인
  const sceneZoom = interpolate(f, [0, 180], [1.0, 1.055], { extrapolateRight: 'clamp' });

  // 민트 글로우 펄스
  const pulse    = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz      = interpolate(pulse, [0, 1], [18, 55]);
  const mainGlow = fg2Op > 0.5
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.52), 0 0 ${gSz * 4}px rgba(0,191,154,0.26)`
    : undefined;

  // 글로우 버스트
  const burstOp    = interpolate(f, [90, 98, 135], [0, 0.65, 0], { extrapolateRight: 'clamp' });
  const burstScale = interpolate(f, [90, 135], [0.18, 3.8], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [120, 144], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 워터마크 */}
      <div style={{
        position: 'absolute', inset: 0, overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: bgTextOp,
        transform: `scale(${bgTextScale})`,
      }}>
        <div style={{
          color: C.main, fontSize: 440, fontWeight: 900,
          whiteSpace: 'nowrap', lineHeight: 1, letterSpacing: -8,
          userSelect: 'none', pointerEvents: 'none',
        }}>뉴스</div>
      </div>

      {/* 글로우 버스트 */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        width: 520, height: 520, marginLeft: -260, marginTop: -260,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,255,208,0.32) 0%, transparent 70%)',
        opacity: burstOp, transform: `scale(${burstScale})`, pointerEvents: 'none',
      }} />

      {/* 전경 메시지 */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        transform: `scale(${sceneZoom})`,
      }}>
        <div style={{
          color: C.textPrimary, fontSize: 122, fontWeight: 700,
          opacity: fg1Op, transform: `translateY(${fg1Y}px)`,
          letterSpacing: 5, marginBottom: 12,
        }}>뉴스가 나오면</div>

        <div style={{
          color: C.main, fontSize: 210, fontWeight: 900,
          opacity: fg2Op, transform: `scale(${fg2Scale})`,
          textShadow: mainGlow, lineHeight: 1.0, letterSpacing: -6,
        }}>이미 늦다</div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          뉴스 공개 시점에 기관은 이미 익절하고 있습니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
