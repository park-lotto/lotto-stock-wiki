// BH02 — 단일 숫자 폭발형 (Layout B)
// 화면을 지배하는 "78%". 물결 링. 아이콘·라벨 없음.
// 자막: "개인 투자자 10명 중 8명이 고점 매수를 경험합니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

const RING_DELAYS = [0, 28, 56];

export const BH02 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  const labelOp = interpolate(f, [0, 22], [0, 1], { extrapolateRight: 'clamp' });

  const countProg = interpolate(f, [15, 92], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const count = Math.round(78 * countProg);

  const numOp    = interpolate(f, [10, 32], [0, 1], { extrapolateRight: 'clamp' });
  const numScale = interpolate(f, [10, 36], [0.25, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });

  const pctOp = interpolate(f, [90, 102], [0, 1], { extrapolateRight: 'clamp' });
  const pctY  = interpolate(f, [90, 102], [-50, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  const descOp    = interpolate(f, [108, 135], [0, 1], { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [138, 160], [0, 1], { extrapolateRight: 'clamp' });

  const pulse   = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [22, 65]);
  const numGlow = count > 55
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.45), 0 0 ${gSz * 3}px rgba(0,191,154,0.22)`
    : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {RING_DELAYS.map((delay, i) => {
        const age = f - 92 - delay;
        if (age < 0) return null;
        const rScale = interpolate(age, [0, 72], [0.08, 4.2], { extrapolateRight: 'clamp' });
        const rOp    = interpolate(age, [0, 10, 58, 72], [0, 0.75, 0.38, 0], { extrapolateRight: 'clamp' });
        return (
          <div key={i} style={{
            position: 'absolute', top: '50%', left: '50%',
            width: 280, height: 280, marginLeft: -140, marginTop: -140,
            borderRadius: '50%',
            border: `${2 - i * 0.4}px solid rgba(0,255,208,${0.75 - i * 0.18})`,
            opacity: rOp, transform: `scale(${rScale})`,
            pointerEvents: 'none',
          }} />
        );
      })}

      <div style={{
        position: 'absolute', top: '11%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: labelOp,
      }}>
        <div style={{
          color: C.textSub, fontSize: 30, fontWeight: 500, letterSpacing: 7,
          borderBottom: `1px solid ${C.borderSub}`, paddingBottom: 14,
        }}>고점 매수 피해 통계</div>
      </div>

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{
          display: 'flex', alignItems: 'flex-start',
          opacity: numOp, transform: `scale(${numScale})`,
        }}>
          <div style={{
            color: C.main, fontSize: 390, fontWeight: 900, lineHeight: 1,
            textShadow: numGlow,
          }}>{count}</div>
          <div style={{
            color: C.main, fontSize: 165, fontWeight: 900, lineHeight: 1,
            marginTop: 44, opacity: pctOp, transform: `translateY(${pctY}px)`,
            textShadow: numGlow,
          }}>%</div>
        </div>
      </div>

      <div style={{
        position: 'absolute', bottom: '18%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: descOp, paddingBottom: 20,
      }}>
        <div style={{ color: C.textSub, fontSize: 36, fontWeight: 400, textAlign: 'center', letterSpacing: 1 }}>
          개인 투자자 중 고점 매수 손실 경험자
        </div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          개인 투자자 10명 중 8명이 고점 매수를 경험합니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
