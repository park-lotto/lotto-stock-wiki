// LS04 — 텍스트 수렴형
// 투자 키워드들이 사방에서 "주도주"로 빨려들어감
// 자막: "수급이 집중될수록 탄력이 극대화됩니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

const CX = 50, CY = 43; // 수렴 중심 (% 단위)

const FLOATERS = [
  { text: '수급', sx: 8,  sy: 16, size: 36 },
  { text: '기관 매수', sx: 72, sy: 11, size: 30 },
  { text: '외국인', sx: 84, sy: 58, size: 32 },
  { text: '모멘텀', sx: 66, sy: 80, size: 34 },
  { text: '뉴스 선행', sx: 10, sy: 76, size: 28 },
  { text: '차트 신호', sx: 4,  sy: 44, size: 30 },
  { text: '실적 개선', sx: 40, sy: 4,  size: 28 },
  { text: '이평선', sx: 56, sy: 84, size: 32 },
  { text: '섹터 모멘텀', sx: 30, sy: 20, size: 26 },
];

export const LS04 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 플로터 초기 등장
  const scatterOp = interpolate(f, [5, 30], [0, 1], { extrapolateRight: 'clamp' });

  // 수렴 진행 (f:35 → f:120)
  const converge = interpolate(f, [35, 118], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 플로터 페이드아웃 (중심 도착 직전)
  const floaterOp = interpolate(f, [108, 128], [1, 0], { extrapolateRight: 'clamp' });

  // 중앙 "주도주" 성장
  const mainScale  = interpolate(f, [35, 130], [1.0, 2.8], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const mainGlowOp = interpolate(f, [80, 130], [0, 1], { extrapolateRight: 'clamp' });
  const mainOp     = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // 배경 중앙 글로우
  const bgGlowOp = interpolate(f, [80, 135], [0, 0.12], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [145, 165], [0, 1], { extrapolateRight: 'clamp' });

  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [14, 44]);
  const dynGlow = mainGlowOp > 0.3
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.28)`
    : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 중앙 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse 460px 380px at 50% 43%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlowOp, pointerEvents: 'none',
      }} />

      {/* 플로터들 */}
      {FLOATERS.map((item, i) => {
        const x = item.sx + (CX - item.sx) * converge;
        const y = item.sy + (CY - item.sy) * converge;
        return (
          <div key={i} style={{
            position: 'absolute',
            left: `${x}%`, top: `${y}%`,
            transform: 'translate(-50%, -50%)',
            color: C.textSub, fontSize: item.size, fontWeight: 500,
            opacity: scatterOp * floaterOp,
            pointerEvents: 'none',
          }}>{item.text}</div>
        );
      })}

      {/* 중앙 "주도주" */}
      <div style={{
        position: 'absolute', top: `${CY}%`, left: `${CX}%`,
        transform: `translate(-50%, -50%) scale(${mainScale})`,
        color: C.main, fontSize: 88, fontWeight: 900,
        textShadow: dynGlow,
        letterSpacing: 4, opacity: mainOp,
        pointerEvents: 'none',
      }}>주도주</div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          수급이 집중될수록 탄력이 극대화됩니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
