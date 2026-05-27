// LS03 — 극단 바차트형
// 3개 바가 바닥에서 자라남. 높이 차이가 극단적.
// 자막: "같은 장세에서 수익률이 이렇게 다릅니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const BARS = [
  { label: '주도주', pct: 127, color: C.main, glowColor: 'rgba(0,255,208,0.6)', textColor: '#000000' },
  { label: '시장 평균', pct: 18, color: '#555555', glowColor: 'rgba(255,255,255,0.1)', textColor: '#ffffff' },
  { label: '비주도주', pct: -14, color: '#CC3333', glowColor: 'rgba(204,51,51,0.3)', textColor: '#ffffff' },
];

const MAX_HEIGHT_PX = 560; // 주도주 바 최대 높이

export const LS03 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 레이블 등장
  const labelOp = interpolate(f, [0, 20], [0, 1], { extrapolateRight: 'clamp' });

  // 바 성장 (f:22 → f:88)
  const barProg = interpolate(f, [22, 88], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 숫자 라벨 등장
  const numOp = interpolate(f, [90, 112], [0, 1], { extrapolateRight: 'clamp' });
  const numScale = interpolate(f, [90, 112], [0.6, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  // 주도주 바 펄스 글로우
  const pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [10, 30]);
  const barGlow = numOp > 0.5 ? `0 0 ${gSz}px rgba(0,255,208,0.9), 0 0 ${gSz * 2}px rgba(0,255,208,0.4)` : undefined;

  const captionOp = interpolate(f, [138, 160], [0, 1], { extrapolateRight: 'clamp' });

  const BOTTOM_Y = 780; // 바 바닥 y 기준 (화면 상 위치)

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 상단 레이블 */}
      <div style={{
        position: 'absolute', top: '7%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: labelOp,
      }}>
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 6,
          borderBottom: `1px solid ${C.borderSub}`, paddingBottom: 12,
        }}>동일 기간 수익률 비교</div>
      </div>

      {/* 바닥 기준선 */}
      <div style={{
        position: 'absolute', top: `${(BOTTOM_Y / 1080) * 100}%`,
        left: '8%', right: '8%', height: 2,
        background: '#222222', opacity: labelOp,
      }} />

      {/* 바 영역 */}
      <div style={{
        position: 'absolute', top: '15%', left: '8%', right: '8%',
        bottom: '25%',
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-evenly',
      }}>
        {BARS.map((bar, i) => {
          const isNegative = bar.pct < 0;
          const absHeight = Math.abs(bar.pct) / 127 * MAX_HEIGHT_PX * barProg;
          const isMain = i === 0;

          return (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
              {/* 숫자 (바 위) */}
              <div style={{
                opacity: numOp,
                transform: `scale(${numScale})`,
                color: isMain ? C.main : (isNegative ? '#FF5555' : C.textSub),
                fontSize: isMain ? 80 : 60, fontWeight: 900,
                textShadow: isMain ? GLOW.mid.text : undefined,
                minHeight: 100, display: 'flex', alignItems: 'flex-end',
              }}>
                {bar.pct > 0 ? '+' : ''}{bar.pct}%
              </div>

              {/* 바 */}
              <div style={{
                width: isMain ? 260 : 220,
                height: absHeight,
                background: bar.color,
                borderRadius: isNegative ? '0 0 8px 8px' : '8px 8px 0 0',
                boxShadow: isMain ? barGlow : `0 0 8px ${bar.glowColor}`,
                display: 'flex', alignItems: isNegative ? 'flex-end' : 'flex-start',
                justifyContent: 'center', paddingBlock: 12,
                flexDirection: isNegative ? 'column-reverse' : 'column',
                transition: undefined,
              }} />

              {/* 바 아래 레이블 */}
              <div style={{
                color: isMain ? C.main : C.textSub,
                fontSize: 32, fontWeight: isMain ? 700 : 500,
                opacity: labelOp, textAlign: 'center',
                textShadow: isMain ? GLOW.weak.text : undefined,
              }}>{bar.label}</div>
            </div>
          );
        })}
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          같은 장세에서 수익률이 이렇게 다릅니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
