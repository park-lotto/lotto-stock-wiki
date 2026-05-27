// BH05 — 워드 슬램형 (Layout E)
// 각 패턴이 아래서 충돌하며 순서대로 쌓임.
// 자막: "세 가지 모두 기관이 이미 포지션을 잡은 후입니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const WORDS = [
  { emoji: '📰', text: '뉴스 매수', sub: '정보 공개 → 이미 늦음' },
  { emoji: '🚀', text: '급등 추격', sub: '올랐으니 더 오를 것 → 착각' },
  { emoji: '⚡', text: '상한가 다음날', sub: '최고의 타이밍처럼 보이지만 → 함정' },
];

const STARTS = [15, 58, 101];

export const BH05 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const labelOp = interpolate(f, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [148, 168], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      <div style={{
        position: 'absolute', top: '8%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: labelOp,
      }}>
        <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 6 }}>
          고점 매수의 3가지 유형
        </div>
      </div>

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 18,
      }}>
        {WORDS.map((word, i) => {
          const isVisible = f >= STARTS[i];
          if (!isVisible) return null;

          const slamY = interpolate(f, [STARTS[i], STARTS[i] + 22], [220, 0], {
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          const op = interpolate(f, [STARTS[i], STARTS[i] + 18], [0, 1], { extrapolateRight: 'clamp' });
          const scale = interpolate(f, [STARTS[i], STARTS[i] + 22], [0.85, 1], {
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.elastic(0.8)),
          });

          const isLast = i === WORDS.length - 1;

          return (
            <div key={i} style={{
              opacity: op,
              transform: `translateY(${slamY}px) scale(${scale})`,
              display: 'flex', alignItems: 'center', gap: 36,
              background: isLast ? C.cardBgActive : C.cardBg,
              border: `2px solid ${isLast ? C.main : C.borderSub}`,
              borderRadius: 22, padding: '22px 56px',
              boxShadow: isLast ? GLOW.mid.box : undefined,
              width: 1300,
            }}>
              <span style={{ fontSize: 64, flexShrink: 0 }}>{word.emoji}</span>
              <div>
                <div style={{
                  fontSize: 68, fontWeight: 900,
                  color: isLast ? C.main : C.textPrimary,
                  textShadow: isLast ? GLOW.mid.text : undefined,
                  lineHeight: 1.1,
                }}>{word.text}</div>
                <div style={{ color: C.textSub, fontSize: 26, fontWeight: 400, marginTop: 6 }}>{word.sub}</div>
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
          세 가지 모두 기관이 이미 포지션을 잡은 후입니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
