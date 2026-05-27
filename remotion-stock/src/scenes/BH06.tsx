// BH06 — 인용구형 (Layout F)
// 거대 따옴표 + 인용문. 아이콘·카드 없음. 순수 타이포그래피.
// 자막: "뉴스를 보고 사는 것은 이미 늦은 것입니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const BH06 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 열린 따옴표 — 회전하며 등장
  const q1Op    = interpolate(f, [8, 36], [0, 1], { extrapolateRight: 'clamp' });
  const q1Scale = interpolate(f, [8, 36], [2.8, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const q1Rot   = interpolate(f, [8, 36], [-22, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 닫힌 따옴표
  const q2Op    = interpolate(f, [18, 46], [0, 1], { extrapolateRight: 'clamp' });
  const q2Scale = interpolate(f, [18, 46], [2.8, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const q2Rot   = interpolate(f, [18, 46], [22, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 인용문 라인
  const l1Op = interpolate(f, [48, 74], [0, 1], { extrapolateRight: 'clamp' });
  const l1Y  = interpolate(f, [48, 74], [32, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const l2Op = interpolate(f, [66, 92], [0, 1], { extrapolateRight: 'clamp' });
  const l2Y  = interpolate(f, [66, 92], [32, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 구분선 + 출처
  const lineW   = interpolate(f, [90, 118], [0, 100], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const authorOp = interpolate(f, [104, 126], [0, 1], { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [130, 152], [0, 1], { extrapolateRight: 'clamp' });

  const bgGlow = Math.sin(f * 0.04) * 0.018 + 0.032;

  // 텍스트 부드러운 화이트 글로우
  const pulse   = Math.sin(f * 0.06) * 0.5 + 0.5;
  const wGlow   = interpolate(pulse, [0, 1], [0, 0.28]);
  const textGlow = l2Op > 0.5 ? `0 0 24px rgba(255,255,255,${wGlow})` : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 70%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        paddingInline: 140,
      }}>
        {/* 열린 따옴표 */}
        <div style={{
          alignSelf: 'flex-start', marginLeft: 60,
          fontSize: 230, lineHeight: 0.65, color: C.main,
          opacity: q1Op,
          transform: `scale(${q1Scale}) rotate(${q1Rot}deg)`,
          transformOrigin: 'left bottom',
          textShadow: GLOW.mid.text,
          marginBottom: -52,
        }}>{'“'}</div>

        {/* 인용문 */}
        <div style={{ textAlign: 'center' }}>
          <div style={{
            color: C.textPrimary, fontSize: 88, fontWeight: 800, lineHeight: 1.35,
            opacity: l1Op, transform: `translateY(${l1Y}px)`,
            textShadow: textGlow,
          }}>정보가 공개될 때는</div>
          <div style={{
            color: C.textPrimary, fontSize: 88, fontWeight: 800, lineHeight: 1.35,
            opacity: l2Op, transform: `translateY(${l2Y}px)`,
            textShadow: textGlow,
          }}>
            이미 <span style={{ color: C.main, textShadow: GLOW.strong.text }}>기관이 먹은 후</span>다
          </div>
        </div>

        {/* 닫힌 따옴표 */}
        <div style={{
          alignSelf: 'flex-end', marginRight: 60,
          fontSize: 230, lineHeight: 0.65, color: C.main,
          opacity: q2Op,
          transform: `scale(${q2Scale}) rotate(${q2Rot}deg)`,
          transformOrigin: 'right top',
          textShadow: GLOW.mid.text,
          marginTop: -20,
        }}>{'”'}</div>

        {/* 구분선 + 출처 */}
        <div style={{
          width: `${lineW}%`, maxWidth: 420, height: 1,
          background: `linear-gradient(90deg, transparent, ${C.main}, transparent)`,
          marginTop: 44, marginBottom: 22,
        }} />
        <div style={{
          color: C.textSub, fontSize: 30, fontWeight: 400, letterSpacing: 3,
          opacity: authorOp,
        }}>— 고점 매수의 진실</div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          뉴스를 보고 사는 것은 이미 늦은 것입니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
