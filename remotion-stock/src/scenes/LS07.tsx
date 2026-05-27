// LS07 — SVG 섹터 순환형
// 섹터들이 원형 배치, 빛나는 볼이 섹터를 순회
// 자막: "돈은 항상 다음 섹터를 향해 이동합니다"
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

const CX = 960, CY = 460;
const R = 300;

const SECTORS = ['반도체', '조선', '방산', '바이오', '전력기기', 'AI·로봇'];
const N = SECTORS.length;

export const LS07 = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 원 + 섹터 등장
  const circleOp = interpolate(f, [8, 35], [0, 1], { extrapolateRight: 'clamp' });
  const sectorOp = interpolate(f, [28, 55], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 볼 등장
  const ballOp = interpolate(f, [55, 72], [0, 1], { extrapolateRight: 'clamp' });

  // 볼 이동 (섹터를 순서대로 방문)
  // 한 섹터당 약 20프레임 머뭄 + 10프레임 이동 = 30프레임/섹터
  const totalFrames = 180 - 72; // f:72~180
  const ballProgress = f >= 72 ? Math.min((f - 72) / totalFrames, 1) : 0;
  const ballAngleDeg = ballProgress * 360 * 1.3; // 1.3 바퀴
  const ballRad = (ballAngleDeg / 360) * Math.PI * 2 - Math.PI / 2; // -90° 보정(위에서 시작)
  const ballX = CX + R * Math.cos(ballRad);
  const ballY = CY + R * Math.sin(ballRad);

  // 현재 가장 가까운 섹터
  const currentSectorAngle = ((ballAngleDeg % 360) + 360) % 360;
  const currentSectorIdx = Math.round((currentSectorAngle / 360) * N) % N;

  // 제목
  const titleOp = interpolate(f, [0, 22], [0, 1], { extrapolateRight: 'clamp' });

  // 중앙 텍스트
  const centerOp = interpolate(f, [60, 80], [0, 1], { extrapolateRight: 'clamp' });

  const captionOp = interpolate(f, [148, 168], [0, 1], { extrapolateRight: 'clamp' });

  const pulse = Math.sin(f * 0.08) * 0.5 + 0.5;
  const ballR = 22 + pulse * 6;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>

      {/* 제목 */}
      <div style={{
        position: 'absolute', top: '5%', left: 0, right: 0,
        display: 'flex', justifyContent: 'center', opacity: titleOp,
      }}>
        <div style={{ color: C.textSub, fontSize: 28, fontWeight: 500, letterSpacing: 6 }}>
          섹터 로테이션 — 돈이 이동한다
        </div>
      </div>

      <svg
        viewBox="0 0 1920 1080"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <defs>
          <filter id="ballGlow">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="sectorGlow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* 원형 트랙 */}
        <circle cx={CX} cy={CY} r={R}
          stroke={C.borderSub} strokeWidth="1.5" fill="none"
          strokeDasharray="6 8"
          opacity={circleOp} />

        {/* 섹터 노드 + 레이블 */}
        {SECTORS.map((sector, i) => {
          const angle = (i / N) * Math.PI * 2 - Math.PI / 2;
          const nx = CX + R * Math.cos(angle);
          const ny = CY + R * Math.sin(angle);
          const lx = CX + (R + 64) * Math.cos(angle);
          const ly = CY + (R + 64) * Math.sin(angle);
          const isActive = i === currentSectorIdx && ballOp > 0.5;

          return (
            <g key={i} opacity={sectorOp}>
              {/* 연결선 */}
              <line x1={CX} y1={CY} x2={nx} y2={ny}
                stroke={isActive ? C.main : C.borderSub}
                strokeWidth={isActive ? 1.5 : 0.8}
                strokeDasharray="4 8"
                opacity={isActive ? 0.5 : 0.2} />

              {/* 섹터 노드 */}
              {isActive && (
                <circle cx={nx} cy={ny} r="24" fill={C.main} opacity="0.2"
                  filter="url(#sectorGlow)" />
              )}
              <circle cx={nx} cy={ny} r="12"
                fill={isActive ? C.main : '#222222'}
                stroke={isActive ? C.main : C.borderSub}
                strokeWidth="2" />

              {/* 섹터 레이블 */}
              <text x={lx} y={ly + 6}
                textAnchor="middle" dominantBaseline="middle"
                fill={isActive ? C.main : C.textSub}
                fontSize={isActive ? '34' : '28'}
                fontWeight={isActive ? '900' : '400'}
                fontFamily={FONT}
                filter={isActive ? 'url(#sectorGlow)' : undefined}>
                {sector}
              </text>
            </g>
          );
        })}

        {/* 볼 (현재 주도 섹터) */}
        {ballOp > 0 && (
          <g opacity={ballOp}>
            <circle cx={ballX} cy={ballY} r={ballR + 12} fill={C.main}
              opacity="0.22" filter="url(#ballGlow)" />
            <circle cx={ballX} cy={ballY} r={ballR} fill={C.main}
              filter="url(#ballGlow)" />
            <circle cx={ballX} cy={ballY} r={ballR * 0.45} fill={C.bg} opacity="0.6" />
          </g>
        )}

        {/* 중앙 텍스트 */}
        <text x={CX} y={CY - 16} textAnchor="middle"
          fill={C.textSub} fontSize="28" fontFamily={FONT} opacity={centerOp}>
          현재 주도
        </text>
        <text x={CX} y={CY + 24} textAnchor="middle"
          fill={C.main} fontSize="44" fontWeight="900" fontFamily={FONT} opacity={centerOp}>
          {SECTORS[currentSectorIdx]}
        </text>
      </svg>

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: captionOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700, textAlign: 'center', paddingInline: 80 }}>
          돈은 항상 다음 섹터를 향해 이동합니다
        </div>
      </div>

    </AbsoluteFill>
  );
};
