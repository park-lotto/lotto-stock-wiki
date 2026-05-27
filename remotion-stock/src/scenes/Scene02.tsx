// S2 문제제기 — 카운트업 숫자
// 자막: "하루에만 50,000개의 정보가 쏟아집니다. 사람이 다 볼 수 있을까요?"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

// 배경 떠다니는 숫자 위치 (고정, 랜덤처럼 보이도록)
const BG_NUMS = [
  { x: 8,  y: 15, delay: 5,  val: '1,243' },
  { x: 78, y: 22, delay: 12, val: '8,502' },
  { x: 20, y: 68, delay: 8,  val: '312'   },
  { x: 88, y: 55, delay: 18, val: '4,871' },
  { x: 50, y: 80, delay: 3,  val: '9,106' },
  { x: 5,  y: 45, delay: 22, val: '731'   },
  { x: 92, y: 12, delay: 15, val: '2,488' },
];

export const Scene02 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const labelOp   = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const iconOp    = interpolate(f, [8, 28],  [0, 1], { extrapolateRight: 'clamp' });
  const iconScale = interpolate(f, [8, 28],  [0.5, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  // 카운트업
  const progress  = interpolate(f, [25, 115], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const count     = Math.round(50000 * progress);
  const numOp     = interpolate(f, [25, 50],  [0, 1], { extrapolateRight: 'clamp' });
  const numScale  = interpolate(f, [25, 50],  [0.8, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  const subOp     = interpolate(f, [60, 85],  [0, 1], { extrapolateRight: 'clamp' });
  const q1Y       = interpolate(f, [80, 108], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const q1Op      = interpolate(f, [80, 108], [0, 1],  { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [100, 120],[0, 1],  { extrapolateRight: 'clamp' });

  const numStr = count >= 50000 ? '50,000+' : count.toLocaleString();

  // 배경 펄스
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 중앙 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 배경 떠다니는 숫자들 */}
      {BG_NUMS.map((n, i) => {
        const op = interpolate(f, [n.delay, n.delay + 20, n.delay + 55, n.delay + 75],
          [0, 0.12, 0.12, 0], { extrapolateRight: 'clamp' });
        return (
          <div key={i} style={{
            position: 'absolute', left: `${n.x}%`, top: `${n.y}%`,
            color: C.main, fontSize: 22, fontWeight: 700, opacity: op,
            filter: 'blur(0.5px)',
          }}>{n.val}</div>
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
          filter: GLOW.mid.filter, lineHeight: 1, marginBottom: 24,
        }}>📰</div>

        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 24,
        }}>하루에 쏟아지는 정보</div>

        {/* 카운트업 숫자 */}
        <div style={{
          fontSize: 200, fontWeight: 900,
          opacity: numOp,
          transform: `scale(${numScale})`,
          color: C.main,
          textShadow: GLOW.strong.text,
          lineHeight: 1.05,
        }}>{numStr}</div>

        {/* 단위 */}
        <div style={{
          color: C.textSub, fontSize: 36, fontWeight: 500,
          opacity: subOp, marginTop: 16, marginBottom: 40,
        }}>개의 뉴스 · 공시 · 종목 신호</div>

        {/* 질문 */}
        <div style={{
          color: C.textPrimary, fontSize: 56, fontWeight: 700,
          opacity: q1Op, transform: `translateY(${q1Y}px)`,
          paddingInline: 160, textAlign: 'center',
        }}>
          사람이 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>다 볼 수 있을까요?</span>
        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          하루에만 50,000개의 정보가 쏟아집니다. 사람이 다 볼 수 있을까요?
        </div>
      </div>

    </AbsoluteFill>
  );
};
