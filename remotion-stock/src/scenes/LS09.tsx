// LS09 — 반전 전환형 (결론)
// 회색 세계 → 플래시 → 민트 세계. 주도주를 사는 것과 안 사는 것.
// 자막: "주도주를 사는 것과 안 사는 것의 차이"
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const GRAY_WORDS = [
  { text: '횡보', x: '18%', y: '28%', size: 52 },
  { text: '지루함', x: '60%', y: '22%', size: 44 },
  { text: '기다림', x: '38%', y: '55%', size: 48 },
  { text: '소외감', x: '72%', y: '58%', size: 40 },
  { text: '손실', x: '22%', y: '72%', size: 56 },
];

const MINT_WORDS = [
  { text: '탄력', x: '20%', y: '28%', size: 52 },
  { text: '속도', x: '62%', y: '22%', size: 48 },
  { text: '수익', x: '40%', y: '55%', size: 56 },
  { text: '확신', x: '74%', y: '58%', size: 44 },
  { text: '성장', x: '25%', y: '72%', size: 48 },
];

export const LS09 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // Phase 1: 회색 세계 (f:0-72)
  const grayOp  = interpolate(f, [10, 35], [0, 1], { extrapolateRight: 'clamp' });
  const grayFadeOut = interpolate(f, [68, 82], [1, 0], { extrapolateRight: 'clamp' });
  const grayLabel   = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // Transition: 화이트 플래시 (f:72-92)
  const flashOp = interpolate(f, [72, 80, 92], [0, 1, 0], { extrapolateRight: 'clamp' });

  // Phase 2: 민트 세계 (f:92~)
  const mintOp   = interpolate(f, [88, 115], [0, 1], { extrapolateRight: 'clamp' });
  const mintLabel = interpolate(f, [92, 112], [0, 1], { extrapolateRight: 'clamp' });
  const bgMintOp = interpolate(f, [88, 140], [0, 0.08], { extrapolateRight: 'clamp' });

  // 민트 글로우 펄스
  const pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [8, 26]);
  const dynGlow = mintOp > 0.5
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.45)`
    : undefined;

  const captionOp = interpolate(f, [148, 168], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* Phase 2: 민트 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgMintOp, pointerEvents: 'none',
      }} />

      {/* Phase 1: 비주도주 단어들 */}
      {GRAY_WORDS.map((w, i) => (
        <div key={i} style={{
          position: 'absolute', left: w.x, top: w.y,
          transform: 'translate(-50%, -50%)',
          color: '#3a3a3a', fontSize: w.size, fontWeight: 900,
          opacity: grayOp * grayFadeOut,
        }}>{w.text}</div>
      ))}

      {/* Phase 1: 비주도주 레이블 */}
      <div style={{
        position: 'absolute', top: '8%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center',
        opacity: grayLabel * grayFadeOut,
      }}>
        <div style={{ color: '#444444', fontSize: 32, fontWeight: 500, letterSpacing: 5 }}>
          비주도주를 샀을 때
        </div>
      </div>

      {/* 화이트 플래시 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: '#ffffff',
        opacity: flashOp,
        pointerEvents: 'none',
      }} />

      {/* Phase 2: 주도주 단어들 */}
      {MINT_WORDS.map((w, i) => (
        <div key={i} style={{
          position: 'absolute', left: w.x, top: w.y,
          transform: 'translate(-50%, -50%)',
          color: C.main, fontSize: w.size, fontWeight: 900,
          opacity: mintOp,
          textShadow: mintOp > 0.6 ? dynGlow : undefined,
        }}>{w.text}</div>
      ))}

      {/* Phase 2: 주도주 레이블 */}
      <div style={{
        position: 'absolute', top: '8%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center',
        opacity: mintLabel,
      }}>
        <div style={{
          color: C.main, fontSize: 32, fontWeight: 700, letterSpacing: 5,
          textShadow: GLOW.weak.text,
        }}>주도주를 샀을 때</div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          주도주를 사는 것과 안 사는 것의 차이
        </div>
      </div>

    </AbsoluteFill>
  );
};
