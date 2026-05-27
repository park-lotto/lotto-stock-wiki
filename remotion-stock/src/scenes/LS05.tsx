// LS05 — SVG 파도 대비형
// 큰 파도(주도주) vs 작은 파도들(추종주). 파도가 왼쪽→오른쪽 흐름.
// 자막: "주도주는 파도를 만들고, 추종주는 뒤를 따릅니다"
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

const W = 1920;
const STEPS = 120;

const makePath = (cy: number, amplitude: number, phase: number): string => {
  let d = `M 0,${cy}`;
  for (let i = 1; i <= STEPS; i++) {
    const x = (i / STEPS) * W;
    const y = cy - amplitude * Math.sin((i / STEPS) * Math.PI * 3.2 + phase);
    d += ` L ${Math.round(x)},${Math.round(y)}`;
  }
  d += ` L ${W},1080 L 0,1080 Z`;
  return d;
};

export const LS05 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 파도 위상 (움직임)
  const phase = f * 0.045;

  // 큰 파도 등장
  const mainAmpProg = interpolate(f, [10, 60], [0, 1], { extrapolateRight: 'clamp' });
  const mainAmp = 200 * mainAmpProg;

  // 작은 파도 등장 (약간 뒤에)
  const sub1AmpProg = interpolate(f, [25, 75], [0, 1], { extrapolateRight: 'clamp' });
  const sub1Amp = 90 * sub1AmpProg;

  const sub2AmpProg = interpolate(f, [38, 85], [0, 1], { extrapolateRight: 'clamp' });
  const sub2Amp = 55 * sub2AmpProg;

  // 파도 Y 중심선
  const mainCY = 540;
  const sub1CY = 530;
  const sub2CY = 520;

  // 레이블 등장
  const label1Op = interpolate(f, [65, 90], [0, 1], { extrapolateRight: 'clamp' });
  const label2Op = interpolate(f, [78, 105], [0, 1], { extrapolateRight: 'clamp' });

  // 상단 제목
  const titleOp = interpolate(f, [0, 22], [0, 1], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [145, 165], [0, 1], { extrapolateRight: 'clamp' });

  // 파도 경로
  const mainPath = makePath(mainCY, mainAmp, phase);
  const sub1Path = makePath(sub1CY, sub1Amp, phase + 1.1);
  const sub2Path = makePath(sub2CY, sub2Amp, phase + 2.3);

  // 파도 글로우 펄스
  const pulse = Math.sin(f * 0.06) * 0.5 + 0.5;
  const glowAlpha = interpolate(pulse, [0, 1], [0.35, 0.65]);

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 제목 */}
      <div style={{
        position: 'absolute', top: '6%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: titleOp,
      }}>
        <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 6 }}>
          파도의 크기가 수익률을 결정한다
        </div>
      </div>

      <svg
        viewBox="0 0 1920 1080"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <defs>
          <linearGradient id="wave1grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={C.main} stopOpacity={glowAlpha} />
            <stop offset="100%" stopColor={C.mainDark} stopOpacity="0.1" />
          </linearGradient>
          <linearGradient id="wave2grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#333333" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#111111" stopOpacity="0.1" />
          </linearGradient>
          <filter id="waveGlow">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* 작은 파도 2 (가장 뒤) */}
        <path d={sub2Path} fill="url(#wave2grad)" opacity={0.25} />
        <path
          d={`M 0,${sub2CY} ${sub2Path.split(' ').slice(1, STEPS + 1).join(' ')}`}
          fill="none" stroke="#2a2a2a" strokeWidth="1.5"
          opacity={sub2AmpProg}
        />

        {/* 작은 파도 1 */}
        <path d={sub1Path} fill="url(#wave2grad)" opacity={0.38} />
        <path
          d={`M 0,${sub1CY} ${sub1Path.split(' ').slice(1, STEPS + 1).join(' ')}`}
          fill="none" stroke="#3a3a3a" strokeWidth="2"
          opacity={sub1AmpProg}
        />

        {/* 큰 파도 (주도주, 가장 앞) */}
        <path d={mainPath} fill="url(#wave1grad)" />
        <path
          d={`M 0,${mainCY} ${mainPath.split(' ').slice(1, STEPS + 1).join(' ')}`}
          fill="none" stroke={C.main} strokeWidth="3.5"
          filter="url(#waveGlow)"
          opacity={mainAmpProg}
        />

        {/* 레이블 */}
        <text x="120" y={mainCY - mainAmp - 30} fill={C.main}
          fontSize="42" fontWeight="900" fontFamily={FONT}
          opacity={label1Op}>
          주도주 파도
        </text>
        <text x="120" y={mainCY - mainAmp - 78} fill={C.textSub}
          fontSize="28" fontFamily={FONT} opacity={label1Op}>
          수급 집중 → 큰 진폭
        </text>

        <text x="120" y={sub1CY + sub1Amp + 56} fill="#555555"
          fontSize="32" fontWeight="500" fontFamily={FONT}
          opacity={label2Op}>
          추종주 — 뒤따라 움직임
        </text>
      </svg>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          주도주는 파도를 만들고, 추종주는 뒤를 따릅니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
