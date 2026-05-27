// BH09 — 스코어보드 링형 결론 (Layout I)
// 중앙 원형 링 + 아이콘 + 링 아래 결론 텍스트.
// 자막: "고점 매수를 끊는 유일한 방법, 수급을 먼저 읽는 것입니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

export const BH09 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // "결론" 레이블
  const labelOp = interpolate(f, [5, 24], [0, 1], { extrapolateRight: 'clamp' });
  const labelY  = interpolate(f, [5, 24], [-20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 원형 링 탄성 등장
  const ringOp    = interpolate(f, [14, 40], [0, 1], { extrapolateRight: 'clamp' });
  const ringScale = interpolate(f, [14, 40], [0.3, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  // 링 내부 아이콘
  const iconOp = interpolate(f, [32, 50], [0, 1], { extrapolateRight: 'clamp' });

  // 결론 텍스트 Line1
  const t1Op = interpolate(f, [52, 78], [0, 1], { extrapolateRight: 'clamp' });
  const t1Y  = interpolate(f, [52, 78], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 결론 텍스트 Line2 (민트 강조)
  const t2Op = interpolate(f, [72, 98], [0, 1], { extrapolateRight: 'clamp' });
  const t2Y  = interpolate(f, [72, 98], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 보조 텍스트
  const subOp = interpolate(f, [108, 132], [0, 1], { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [134, 156], [0, 1], { extrapolateRight: 'clamp' });

  // 링 동적 글로우
  const pulse    = Math.sin(f * 0.07) * 0.5 + 0.5;
  const rGlow    = interpolate(pulse, [0, 1], [8, 30]);
  const ringGlow = ringOp > 0.8
    ? `0 0 ${rGlow}px rgba(0,255,208,0.9), 0 0 ${rGlow * 2}px rgba(0,255,208,0.45)`
    : undefined;

  // 텍스트 민트 글로우
  const gSz     = interpolate(pulse, [0, 1], [12, 36]);
  const dynGlow = t2Op > 0.5
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.28)`
    : undefined;

  // 배경 글로우
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.045;

  // 링 브리드 (완전 등장 후)
  const breatheScale = ringOp > 0.9 ? Math.sin(f * 0.06) * 0.012 + 1 : 1;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 42%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 레이블 */}
      <div style={{
        position: 'absolute', top: '8%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center',
        opacity: labelOp, transform: `translateY(${labelY}px)`,
      }}>
        <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 8 }}>결론</div>
      </div>

      {/* 메인 콘텐츠 */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 0,
      }}>
        {/* 원형 링 */}
        <div style={{
          width: 300, height: 300, borderRadius: '50%',
          border: `4px solid ${C.main}`,
          boxShadow: ringGlow,
          background: 'radial-gradient(circle, rgba(0,255,208,0.08) 0%, transparent 70%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          opacity: ringOp,
          transform: `scale(${ringScale * breatheScale})`,
          marginBottom: 40,
        }}>
          <div style={{ fontSize: 120, opacity: iconOp, lineHeight: 1 }}>🎯</div>
        </div>

        {/* 결론 Line1 */}
        <div style={{
          color: C.textPrimary, fontSize: 94, fontWeight: 900,
          opacity: t1Op, transform: `translateY(${t1Y}px)`,
          lineHeight: 1.15,
        }}>수급을 먼저 보고</div>

        {/* 결론 Line2 */}
        <div style={{
          color: C.main, fontSize: 94, fontWeight: 900,
          opacity: t2Op, transform: `translateY(${t2Y}px)`,
          textShadow: dynGlow,
          lineHeight: 1.15, marginBottom: 32,
        }}>남들보다 먼저 사라</div>

        {/* 보조 설명 */}
        <div style={{
          color: C.textSub, fontSize: 32, fontWeight: 500,
          opacity: subOp, textAlign: 'center', lineHeight: 1.6,
          paddingInline: 200,
        }}>
          수급이 비어있을 때 먼저 들어가는 것
        </div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          고점 매수를 끊는 유일한 방법, 수급을 먼저 읽는 것입니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
