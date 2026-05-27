// BH08 — 원형 노드 타임라인형 (Layout H)
// 수평선이 그려지고, 원형 노드들이 팝인하며 연결됨.
// 자막: "수급을 먼저 보고, 뉴스 전에 선진입하는 것이 정답입니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const NODES = [
  { icon: '🔍', title: '수급 탐지', sub: '빈집 확인' },
  { icon: '📡', title: '촉매 확인', sub: '뉴스 전' },
  { icon: '🎯', title: '선제 진입', sub: '기관보다 먼저' },
  { icon: '💹', title: '수익 실현', sub: '뉴스 공개 시' },
];

export const BH08 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  const labelOp = interpolate(f, [8, 28], [0, 1], { extrapolateRight: 'clamp' });
  const titleOp = interpolate(f, [20, 46], [0, 1], { extrapolateRight: 'clamp' });
  const titleY  = interpolate(f, [20, 46], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 수평선 그리기
  const lineW = interpolate(f, [50, 92], [0, 100], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 노드 팝인 (순차)
  const nodeAnims = NODES.map((_, i) => {
    const start = 56 + i * 20;
    return {
      opacity: interpolate(f, [start, start + 18], [0, 1], { extrapolateRight: 'clamp' }),
      scale:   interpolate(f, [start, start + 24], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) }),
    };
  });

  // 라벨 페이드인
  const nodeLabelAnims = NODES.map((_, i) => ({
    opacity: interpolate(f, [70 + i * 20, 90 + i * 20], [0, 1], { extrapolateRight: 'clamp' }),
  }));

  // 파이프라인 순환 하이라이트
  const CYCLE_START = 144;
  const cycleActive = f >= CYCLE_START;
  const cycleF = cycleActive ? (f - CYCLE_START) % 50 : -1;

  const captionOp = interpolate(f, [148, 168], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow    = Math.sin(f * 0.04) * 0.024 + 0.04;

  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz   = interpolate(pulse, [0, 1], [8, 26]);

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 55%, rgba(0,255,208,0.8) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 레이블 + 타이틀 */}
      <div style={{
        position: 'absolute', top: '8%', left: 0, right: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
      }}>
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 16,
        }}>올바른 매매 순서</div>
        <div style={{
          color: C.textPrimary, fontSize: 82, fontWeight: 900,
          opacity: titleOp, transform: `translateY(${titleY}px)`,
        }}>
          기관보다 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>먼저 들어가는 법</span>
        </div>
      </div>

      {/* 수평선 */}
      <div style={{
        position: 'absolute', top: '43%', left: '6%',
        height: 3, borderRadius: 2,
        width: `${lineW * 0.88}%`,
        background: `linear-gradient(90deg, ${C.main} 0%, ${C.mainMid} 100%)`,
        boxShadow: '0 0 14px rgba(0,255,208,0.55)',
      }} />

      {/* 노드 행 */}
      <div style={{
        position: 'absolute', top: '34%', left: '4%', right: '4%', bottom: '18%',
        display: 'flex', justifyContent: 'space-evenly', alignItems: 'flex-start',
        paddingTop: 0,
      }}>
        {NODES.map((node, i) => {
          const nodeGlow = cycleActive
            ? Math.max(0, 1 - Math.abs(cycleF - i * 12.5) / 9)
            : (i === NODES.length - 1 ? 0.55 : 0);

          return (
            <div key={i} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22,
              opacity: nodeAnims[i].opacity,
              transform: `scale(${nodeAnims[i].scale})`,
            }}>
              {/* 원형 노드 */}
              <div style={{
                width: 162, height: 162, borderRadius: '50%',
                background: nodeGlow > 0.3 ? C.cardBgActive : C.cardBg,
                border: `3px solid ${nodeGlow > 0.2 ? C.main : C.borderSub}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: nodeGlow > 0.1
                  ? `0 0 ${nodeGlow * 32}px rgba(0,255,208,${nodeGlow * 0.9}), 0 0 ${nodeGlow * 64}px rgba(0,255,208,${nodeGlow * 0.38})`
                  : (i === NODES.length - 1 ? GLOW.weak.box : undefined),
              }}>
                <div style={{ fontSize: 60, lineHeight: 1 }}>{node.icon}</div>
              </div>

              {/* 라벨 */}
              <div style={{ opacity: nodeLabelAnims[i].opacity, textAlign: 'center' }}>
                <div style={{
                  color: nodeGlow > 0.3 ? C.main : C.textPrimary,
                  fontSize: 34, fontWeight: 700,
                  textShadow: nodeGlow > 0.3 ? `0 0 ${gSz}px #00FFD0` : undefined,
                }}>{node.title}</div>
                <div style={{ color: C.textSub, fontSize: 24, fontWeight: 500, marginTop: 5 }}>{node.sub}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          수급을 먼저 보고, 뉴스 전에 선진입하는 것이 정답입니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
