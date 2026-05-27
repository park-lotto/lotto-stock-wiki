// BH01 — 풀블리드 충돌형 (Layout A)
// 아이콘·라벨 없음. 두 거대 텍스트가 좌우에서 충돌.
// 자막: "왜 나만 사면 항상 고점일까요?"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

export const BH01 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // Line1 "내가 사면" — 왼쪽에서 충돌
  const l1X  = interpolate(f, [8, 48], [-700, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const l1Op = interpolate(f, [8, 40], [0, 1], { extrapolateRight: 'clamp' });
  const l1Ls = interpolate(f, [8, 48], [36, -4], { extrapolateRight: 'clamp' });

  // Line2 "떨어진다" — 오른쪽에서 충돌
  const l2X  = interpolate(f, [28, 68], [700, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const l2Op = interpolate(f, [28, 60], [0, 1], { extrapolateRight: 'clamp' });

  // 충돌 임팩트 링 (l2가 도착하는 f≈68)
  const impactOp    = interpolate(f, [64, 72, 115], [0, 0.8, 0], { extrapolateRight: 'clamp' });
  const impactScale = interpolate(f, [64, 115], [0.2, 4.0], { extrapolateRight: 'clamp' });

  // 충돌 후 흔들림
  const shakeX = f >= 68 && f <= 84
    ? Math.sin((f - 68) * 1.6) * interpolate(f, [68, 84], [18, 0], { extrapolateRight: 'clamp' })
    : 0;

  // 소제목 + 자막
  const subOp     = interpolate(f, [88, 118], [0, 1], { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [118, 142], [0, 1], { extrapolateRight: 'clamp' });

  // 배경 대각선 그리드 페이드인
  const gridOp = interpolate(f, [0, 40], [0, 0.055], { extrapolateRight: 'clamp' });

  // 민트 글로우 펄스
  const pulse  = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [14, 44]);
  const dynGlow = l2Op > 0.7 ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)` : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 대각선 그리드 (SVG) */}
      <svg
        style={{ position: 'absolute', inset: 0, opacity: gridOp, pointerEvents: 'none' }}
        width="1920" height="1080"
      >
        {[...Array(9)].map((_, i) => (
          <line
            key={i}
            x1={i * 260 - 160} y1="0"
            x2={i * 260 + 280} y2="1080"
            stroke="#00FFD0" strokeWidth="1"
          />
        ))}
      </svg>

      {/* 충돌 임팩트 링 */}
      <div style={{
        position: 'absolute', top: '40%', left: '50%',
        width: 440, height: 440, marginLeft: -220, marginTop: -220,
        borderRadius: '50%',
        border: '2px solid rgba(0,255,208,0.7)',
        opacity: impactOp, transform: `scale(${impactScale})`,
        pointerEvents: 'none',
      }} />

      {/* 메인 콘텐츠 */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        transform: `translateX(${shakeX}px)`,
      }}>
        <div style={{
          color: C.textPrimary, fontSize: 215, fontWeight: 900,
          opacity: l1Op, transform: `translateX(${l1X}px)`,
          letterSpacing: l1Ls, lineHeight: 1.0,
          marginBottom: -12,
        }}>내가 사면</div>

        <div style={{
          color: C.main, fontSize: 225, fontWeight: 900,
          opacity: l2Op, transform: `translateX(${l2X}px)`,
          textShadow: dynGlow, lineHeight: 1.0,
        }}>떨어진다</div>

        <div style={{
          color: C.textSub, fontSize: 34, fontWeight: 400,
          opacity: subOp, marginTop: 48, letterSpacing: 4,
        }}>— 모든 개미의 공통 고민</div>
      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          왜 나만 사면 항상 고점일까요?
        </div>
      </div>

    </AbsoluteFill>
  );
};
