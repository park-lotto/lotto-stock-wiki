// YT_AI10_S01_훅 — 씬1 훅 (780프레임 / 25초)

import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(
  f: number, a: number, b: number,
  from = 0, to = 1,
  ease: (t: number) => number = Easing.out(Easing.cubic),
) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease,
  });
}

// ── 자막 세그먼트 ─────────────────────────────────────────────────
const SUBS = [
  { s: 0,   e: 150, text: '여러분은 밤새 텔레그램, 뉴스, 리포트를 뒤적이며 내일의 대장주를 찾고 계신가요?' },
  { s: 150, e: 300, text: '아닙니다.' },
  { s: 300, e: 450, text: '진짜 승부는 여러분이 잠든 새벽 4시, 이미 시작됩니다.' },
  { s: 450, e: 510, text: '' }, // 2초 쉬기
  { s: 510, e: 780, text: '저희 로또의 주식인사이트가 자랑하는 AI 직원 10명이 밤새 일해서 찾아낸 \'수급 빈집\' 대장주 3개가 궁금하지 않으신가요?' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

export const YT_AI10_S01_훅: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const bgGlow = Math.sin(f * 0.04) * 0.028 + 0.05;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // Common text style
  const textStyle: React.CSSProperties = {
    fontFamily: FONT,
    fontSize: 72,
    fontWeight: 700,
    color: '#FFF',
    textAlign: 'center',
    textShadow: '0 4px 16px rgba(0,0,0,0.8)',
    position: 'absolute',
    width: '100%',
    paddingInline: 80,
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
  };

  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14' }}>
      <Html5Audio src={staticFile('voice/yt_ai10_s01_훅.m4a')} />

      {/* Background Glow Effect */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(circle at center, rgba(0,255,208,${bgGlow}) 0%, transparent 70%)`,
          opacity: ip(f, 0, 30, 0, 1),
        }}
      />

      {/* Phase 1 (0-5s): "여러분은 밤새 텔레그램, 뉴스, 리포트를 뒤적이며 내일의 [대장주]를 찾고 계신가요?" */}
      {f >= 0 && f < 150 && (
        <div
          style={{
            ...textStyle,
            opacity: ip(f, 0, 30, 0, 1) * ip(f, 120, 150, 1, 0),
          }}
        >
          여러분은 밤새 텔레그램, 뉴스, 리포트를 뒤적이며 내일의 <span style={{ color: C.main, textShadow: dynGlow }}>대장주</span>를 찾고 계신가요?
        </div>
      )}

      {/* Phase 2 (5-10s): "아닙니다." */}
      {f >= 150 && f < 300 && (
        <div
          style={{
            ...textStyle,
            fontSize: 100,
            transform: `translate(-50%, -50%) scale(${ip(f, 150, 180, 0.5, 1, Easing.out(Easing.back))})`,
            opacity: ip(f, 150, 180, 0, 1) * ip(f, 270, 300, 1, 0),
            color: '#FF4757', // Red for strong negation
            textShadow: dynGlow,
          }}
        >
          아닙니다.
        </div>
      )}

      {/* Phase 3 (10-15s): "진짜 승부는 여러분이 잠든 [새벽 4시], 이미 시작됩니다." */}
      {f >= 300 && f < 450 && (
        <div style={{ ...textStyle, opacity: ip(f, 300, 330, 0, 1) * ip(f, 420, 450, 1, 0) }}>
          <div
            style={{
              transform: `translateX(${ip(f, 300, 330, -100, 0, Easing.out(Easing.back))}px)`,
              display: 'inline-block',
            }}
          >
            진짜 승부는 여러분이 잠든
          </div>{' '}
          <div
            style={{
              transform: `translateX(${ip(f, 300, 330, 100, 0, Easing.out(Easing.back))}px)`,
              display: 'inline-block',
            }}
          >
            <span style={{ color: C.main, textShadow: dynGlow }}>새벽 4시</span>, 이미 시작됩니다.
          </div>
        </div>
      )}

      {/* Phase 4 (15-20s): [2초 쉬기] 후 "AI 직원 10명" 텍스트 등장 */}
      {f >= 510 && f < 600 && ( // Note: 2s break f450-f510, text starts at f510
        <div style={{ ...textStyle, opacity: ip(f, 510, 540, 0, 1) * ip(f, 570, 600, 1, 0) }}>
          <div
            style={{
              transform: `translateX(${ip(f, 510, 540, 100, 0, Easing.out(Easing.back))}px)`,
              display: 'inline-block',
            }}
          >
            저희 <span style={{ color: '#FFA502', textShadow: dynGlow }}>로또의 주식인사이트</span>가 자랑하는
          </div>{' '}
          <div
            style={{
              transform: `translateX(${ip(f, 510, 540, -100, 0, Easing.out(Easing.back))}px)`,
              display: 'inline-block',
            }}
          >
            <span style={{ color: C.main, textShadow: dynGlow }}>AI 직원 10명</span>이
          </div>
        </div>
      )}

      {/* Phase 5 (20-25s): "밤새 일해서 찾아낸 '수급 빈집' 대장주 3개가 궁금하지 않으신가요?" */}
      {f >= 600 && f < 780 && (
        <div
          style={{
            ...textStyle,
            transform: `translate(-50%, ${ip(f, 600, 630, 100, -50, Easing.out(Easing.back))}%)`,
            opacity: ip(f, 600, 630, 0, 1) * ip(f, 750, 780, 1, 0),
          }}
        >
          밤새 일해서 찾아낸 '<span style={{ color: C.main, textShadow: dynGlow }}>수급 빈집</span>' <span style={{ color: C.main, textShadow: dynGlow }}>대장주</span> 3개가 궁금하지 않으신가요?
        </div>
      )}

      {/* Subtitle Bar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80,
        background: 'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)',
      }}>
        {sub && <div style={{
          color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center',
          opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)',
        }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};