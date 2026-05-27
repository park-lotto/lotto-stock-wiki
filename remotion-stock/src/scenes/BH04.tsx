// BH04 — 스포트라이트형 (Layout D)
// 어두운 비녜트 가장자리 + 중앙 빛 원. 아이템이 스포트라이트 안으로 등장.
// 자막: "이 세 가지 패턴이 고점 매수를 만듭니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const TRAPS = [
  { num: '01', text: '뉴스 보고 즉시 매수' },
  { num: '02', text: '급등주 추격 매수' },
  { num: '03', text: '상한가 다음날 매수' },
];

export const BH04 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 비녜트 강도
  const vigBase = interpolate(f, [0, 30], [0.96, 0.78], { extrapolateRight: 'clamp' });

  // 타이틀
  const subTitleOp = interpolate(f, [28, 50], [0, 1], { extrapolateRight: 'clamp' });
  const titleOp    = interpolate(f, [14, 40], [0, 1], { extrapolateRight: 'clamp' });
  const titleY     = interpolate(f, [14, 40], [-44, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 아이템 순차 등장
  const itemAnims = TRAPS.map((_, i) => {
    const start = 56 + i * 30;
    return {
      opacity: interpolate(f, [start, start + 24], [0, 1], { extrapolateRight: 'clamp' }),
      scale:   interpolate(f, [start, start + 24], [0.65, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) }),
    };
  });

  const captionOp = interpolate(f, [152, 172], [0, 1], { extrapolateRight: 'clamp' });

  // 스포트라이트 크기 펄스
  const spotW = 570 + Math.sin(f * 0.05) * 10;
  const spotH = 450 + Math.sin(f * 0.05) * 8;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 중앙 스포트라이트 민트 헤일로 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse 500px 380px at 50% 46%, rgba(0,255,208,0.045) 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      {/* 비녜트 (가장자리 어둡게) */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse ${spotW}px ${spotH}px at 50% 46%, rgba(0,0,0,0) 0%, rgba(0,0,0,${vigBase}) 100%)`,
        pointerEvents: 'none',
      }} />

      {/* 타이틀 */}
      <div style={{
        position: 'absolute', top: '9%', left: 0, right: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
      }}>
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 8, opacity: subTitleOp, marginBottom: 18,
        }}>나를 물리게 하는</div>
        <div style={{
          color: C.textPrimary, fontSize: 114, fontWeight: 900,
          opacity: titleOp, transform: `translateY(${titleY}px)`,
        }}>
          3가지 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>함정</span>
        </div>
      </div>

      {/* 아이템 */}
      <div style={{
        position: 'absolute', top: '40%', left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'space-evenly', paddingInline: 220,
      }}>
        {TRAPS.map((trap, i) => (
          <div key={i} style={{
            opacity: itemAnims[i].opacity,
            transform: `scale(${itemAnims[i].scale})`,
            display: 'flex', alignItems: 'center', gap: 40, width: '100%',
          }}>
            <div style={{
              background: C.main, borderRadius: 14,
              width: 76, height: 76, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: GLOW.weak.box,
            }}>
              <span style={{ color: '#000', fontSize: 34, fontWeight: 900 }}>{trap.num}</span>
            </div>
            <div style={{ color: C.textPrimary, fontSize: 58, fontWeight: 700 }}>{trap.text}</div>
          </div>
        ))}
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          이 세 가지 패턴이 고점 매수를 만듭니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
