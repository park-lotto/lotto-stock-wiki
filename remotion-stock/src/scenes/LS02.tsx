// LS02 — 스캐터 스포트라이트형
// 어두운 화면에 종목명들 산재 → 주도주 하나에만 빛이 집중
// 자막: "시장의 에너지가 집중되는 단 하나의 종목"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

const SCATTERED = [
  { text: '삼성전자', x: '14%', y: '18%', size: 28 },
  { text: '카카오', x: '70%', y: '12%', size: 24 },
  { text: 'LG에너지솔루션', x: '78%', y: '54%', size: 22 },
  { text: '포스코홀딩스', x: '62%', y: '78%', size: 26 },
  { text: '현대차', x: '8%', y: '72%', size: 24 },
  { text: 'SK하이닉스', x: '5%', y: '42%', size: 26 },
  { text: '셀트리온', x: '38%', y: '8%', size: 22 },
  { text: 'NAVER', x: '52%', y: '82%', size: 24 },
  { text: 'KB금융', x: '86%', y: '32%', size: 20 },
  { text: '한화오션', x: '26%', y: '86%', size: 22 },
];

export const LS02 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 흩어진 종목명 등장
  const scatterOp = interpolate(f, [5, 35], [0, 1], { extrapolateRight: 'clamp' });

  // 스포트라이트 좁혀짐 (f:35 → f:90)
  const spotW = interpolate(f, [35, 90], [1100, 380], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const spotH = interpolate(f, [35, 90], [900, 300], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 주변 어두워짐
  const dimOp = interpolate(f, [35, 90], [0, 0.78], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 주도주 텍스트 성장
  const mainScale  = interpolate(f, [55, 110], [1, 2.2], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const mainGlowOp = interpolate(f, [55, 110], [0, 1], { extrapolateRight: 'clamp' });

  // 서브 설명
  const subOp = interpolate(f, [115, 138], [0, 1], { extrapolateRight: 'clamp' });
  const captionOp = interpolate(f, [142, 162], [0, 1], { extrapolateRight: 'clamp' });

  // 주도주 민트 글로우 펄스
  const pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [12, 38]);
  const dynGlow = mainGlowOp > 0.3
    ? `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.28)`
    : undefined;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 흩어진 종목명들 */}
      {SCATTERED.map((item, i) => (
        <div key={i} style={{
          position: 'absolute', left: item.x, top: item.y,
          transform: 'translate(-50%, -50%)',
          color: C.textSub, fontSize: item.size, fontWeight: 500,
          opacity: scatterOp * 0.5,
        }}>{item.text}</div>
      ))}

      {/* 어두워지는 오버레이 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse ${spotW}px ${spotH}px at 50% 44%, transparent 0%, rgba(0,0,0,${dimOp}) 100%)`,
        pointerEvents: 'none',
      }} />

      {/* 스포트라이트 민트 헤일로 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse 300px 240px at 50% 44%, rgba(0,255,208,0.06) 0%, transparent 70%)',
        opacity: mainGlowOp,
        pointerEvents: 'none',
      }} />

      {/* 중앙 "주도주" */}
      <div style={{
        position: 'absolute', top: '44%', left: '50%',
        transform: `translate(-50%, -50%) scale(${mainScale})`,
        color: C.main, fontSize: 90, fontWeight: 900,
        textShadow: dynGlow,
        letterSpacing: 6,
      }}>주도주</div>

      {/* 서브 설명 */}
      <div style={{
        position: 'absolute', bottom: '20%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: subOp,
      }}>
        <div style={{
          color: C.textSub, fontSize: 30, fontWeight: 400, textAlign: 'center', lineHeight: 1.7,
        }}>수많은 종목 중에서<br />시장의 에너지가 한 곳으로 쏠린다</div>
      </div>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          시장의 에너지가 집중되는 단 하나의 종목
        </div>
      </div>

    </AbsoluteFill>
  );
};
