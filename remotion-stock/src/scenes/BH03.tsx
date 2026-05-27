// BH03 — 수직 분할선형 (Layout C)
// 중앙 수직선이 그려지며 개인 vs 기관 비교. 아이콘·라벨 없음.
// 자막: "개인과 기관, 같은 종목 다른 타이밍의 비밀"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const LEFT_ITEMS = [
  { stat: '78%', label: '손실 경험률' },
  { stat: '뉴스 후', label: '매수 타이밍' },
  { stat: '감정', label: '판단 기준' },
];

const RIGHT_ITEMS = [
  { stat: '선취매', label: '포지션 방식' },
  { stat: '뉴스 전', label: '매수 타이밍' },
  { stat: '수급', label: '판단 기준' },
];

export const BH03 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 수직 중앙선 그리기 (위→아래)
  const lineH = interpolate(f, [8, 46], [0, 80], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 헤더 (개인/기관)
  const headerOp = interpolate(f, [42, 62], [0, 1], { extrapolateRight: 'clamp' });

  // 아이템 순차 등장
  const itemAnims = LEFT_ITEMS.map((_, i) => {
    const start = 64 + i * 24;
    return {
      opacity: interpolate(f, [start, start + 20], [0, 1], { extrapolateRight: 'clamp' }),
      x: interpolate(f, [start, start + 20], [80, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    };
  });

  const captionOp = interpolate(f, [144, 165], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow    = Math.sin(f * 0.04) * 0.022 + 0.038;

  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [8, 24]);
  const mintGlow = itemAnims[2].opacity > 0.5
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.4)`
    : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 72% 50%, rgba(0,255,208,0.85) 0%, transparent 58%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 수직 중앙선 */}
      <div style={{
        position: 'absolute', left: '50%', top: '10%',
        width: 2, height: `${lineH}%`, marginLeft: -1,
        background: `linear-gradient(180deg, transparent 0%, ${C.main} 12%, ${C.main} 88%, transparent 100%)`,
        boxShadow: '0 0 12px rgba(0,255,208,0.65)',
      }} />

      {/* 헤더 */}
      <div style={{
        position: 'absolute', top: '9%', left: 0, right: 0,
        display: 'flex', opacity: headerOp,
      }}>
        <div style={{
          flex: 1, textAlign: 'center', paddingRight: 24,
          color: C.textSub, fontSize: 44, fontWeight: 800, letterSpacing: 3,
        }}>😰 개인</div>
        <div style={{
          flex: 1, textAlign: 'center', paddingLeft: 24,
          color: C.main, fontSize: 44, fontWeight: 800, letterSpacing: 3,
          textShadow: mintGlow,
        }}>🏦 기관</div>
      </div>

      {/* 내용 영역 */}
      <div style={{
        position: 'absolute', top: '24%', left: 0, right: 0, bottom: '18%',
        display: 'flex',
      }}>
        {/* 왼쪽 — 개인 */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          justifyContent: 'space-evenly', alignItems: 'flex-end',
          paddingRight: 64, paddingBlock: 16,
        }}>
          {LEFT_ITEMS.map((item, i) => (
            <div key={i} style={{
              opacity: itemAnims[i].opacity,
              transform: `translateX(-${itemAnims[i].x}px)`,
              textAlign: 'right',
            }}>
              <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, marginBottom: 6 }}>{item.label}</div>
              <div style={{ color: '#555555', fontSize: 68, fontWeight: 900 }}>{item.stat}</div>
            </div>
          ))}
        </div>

        {/* 오른쪽 — 기관 */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          justifyContent: 'space-evenly', alignItems: 'flex-start',
          paddingLeft: 64, paddingBlock: 16,
        }}>
          {RIGHT_ITEMS.map((item, i) => (
            <div key={i} style={{
              opacity: itemAnims[i].opacity,
              transform: `translateX(${itemAnims[i].x}px)`,
              textAlign: 'left',
            }}>
              <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, marginBottom: 6 }}>{item.label}</div>
              <div style={{
                color: C.main, fontSize: 68, fontWeight: 900,
                textShadow: itemAnims[i].opacity > 0.6 ? GLOW.mid.text : undefined,
              }}>{item.stat}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          개인과 기관, 같은 종목 다른 타이밍의 비밀
        </div>
      </div>

    </AbsoluteFill>
  );
};
