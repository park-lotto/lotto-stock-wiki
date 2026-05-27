// S6 비교형 — 사람(회색) vs AI(민트)
// 자막: "사람과 AI, 직접 비교해봤습니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const Scene06 = () => {
  const f = useCurrentFrame();

  const fadeIn    = interpolate(f, [0, 15],  [0, 1], { extrapolateRight: 'clamp' });
  const labelOp   = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const titleY    = interpolate(f, [22, 48], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const titleOp   = interpolate(f, [22, 48], [0, 1],  { extrapolateRight: 'clamp' });

  // 좌 카드 — 왼쪽에서
  const leftOp  = interpolate(f, [42, 68], [0, 1],  { extrapolateRight: 'clamp' });
  const leftX   = interpolate(f, [42, 68], [-80, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 우 카드 — 오른쪽에서
  const rightOp = interpolate(f, [65, 95], [0, 1],  { extrapolateRight: 'clamp' });
  const rightX  = interpolate(f, [65, 95], [80, 0],  { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 양쪽 카드 등장 후: 좌 카드 점점 어두워지고, 우 카드 글로우 강해짐
  const aiReveal  = interpolate(f, [100, 140], [0, 1], { extrapolateRight: 'clamp' });
  const humanDim  = interpolate(f, [100, 140], [1, 0.38], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [108, 130], [0, 1], { extrapolateRight: 'clamp' });

  // AI 카드 동적 글로우
  const pulse   = Math.sin(f * 0.08) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 26]);
  const aiGlow  = `0 0 ${gSz}px rgba(0,255,208,${0.6 + 0.4 * aiReveal}), 0 0 ${gSz * 2}px rgba(0,255,208,${0.3 * aiReveal})`;

  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  const rows = [
    { label: '처리 속도', human: '하루 종일', ai: '0.3초' },
    { label: '감정',      human: '공포·욕심', ai: '없음' },
    { label: '커버 범위', human: '1~3 종목',  ai: '전 종목' },
  ];

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        paddingInline: 120,
      }}>
        {/* 라벨 */}
        <div style={{
          color: C.textSub, fontSize: 28, fontWeight: 500,
          letterSpacing: 5, opacity: labelOp, marginBottom: 18,
        }}>누가 더 빠를까?</div>

        {/* 타이틀 */}
        <div style={{
          fontSize: 100, fontWeight: 900,
          opacity: titleOp, transform: `translateY(${titleY}px)`,
          marginBottom: 44, textAlign: 'center',
        }}>
          <span style={{ color: C.textPrimary }}>사람 </span>
          <span style={{ color: C.textSub, fontSize: 72 }}>vs </span>
          <span style={{ color: C.main, textShadow: GLOW.weak.text }}>AI</span>
        </div>

        {/* 두 카드 */}
        <div style={{ display: 'flex', gap: 32, width: '100%' }}>

          {/* 좌 — 사람 */}
          <div style={{
            flex: 1, background: C.cardBg,
            border: '1.5px solid #333',
            borderRadius: 18, padding: '28px 32px',
            opacity: leftOp * humanDim,
            transform: `translateX(${leftX}px)`,
          }}>
            <div style={{ fontSize: 90, textAlign: 'center', marginBottom: 16 }}>🧑‍💼</div>
            <div style={{ color: C.textSub, fontSize: 40, fontWeight: 700, textAlign: 'center', marginBottom: 28 }}>사람</div>
            {rows.map((r, i) => (
              <div key={i} style={{ marginBottom: 18 }}>
                <div style={{ color: '#444', fontSize: 22, fontWeight: 500, marginBottom: 6 }}>{r.label}</div>
                <div style={{ color: C.textSub, fontSize: 32, fontWeight: 700 }}>{r.human}</div>
              </div>
            ))}
          </div>

          {/* 우 — AI */}
          <div style={{
            flex: 1, background: C.cardBgActive,
            border: `2px solid ${C.main}`,
            borderRadius: 18, padding: '28px 32px',
            opacity: rightOp,
            transform: `translateX(${rightX}px)`,
            boxShadow: rightOp > 0.5 ? aiGlow : undefined,
          }}>
            <div style={{
              fontSize: 90, textAlign: 'center',
              filter: GLOW.mid.filter, marginBottom: 16,
            }}>🤖</div>
            <div style={{
              color: C.main, fontSize: 40, fontWeight: 700,
              textAlign: 'center', marginBottom: 28,
              textShadow: GLOW.mid.text,
            }}>AI</div>
            {rows.map((r, i) => (
              <div key={i} style={{ marginBottom: 18 }}>
                <div style={{ color: C.borderSub, fontSize: 22, fontWeight: 500, marginBottom: 6 }}>{r.label}</div>
                <div style={{ color: C.main, fontSize: 32, fontWeight: 700 }}>{r.ai}</div>
              </div>
            ))}
          </div>

        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          사람과 AI, 직접 비교해봤습니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
