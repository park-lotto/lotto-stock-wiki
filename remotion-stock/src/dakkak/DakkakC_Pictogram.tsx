// Sample C — 픽토그램 도시
// 부감 시점 미니멀 도시. 건물 4동(서버실·내집·증권사·시장)
// 시간이 흐르면서 각 건물에 빛이 켜졌다 꺼졌다. 08:00에 내 집이 가장 밝게.
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 240;

type Building = {
  id: string;
  label: string;
  x: number; y: number; w: number; h: number;
  // 각 시간대별 점등 강도 (0~1)
  // index 0~5: 04 / 08 / 09 / 12 / 15 / 23
  lights: number[];
};

const SLOTS = [0.10, 0.40, 0.50, 0.62, 0.72, 0.85]; // 시간대 등장 progress

const BUILDINGS: Building[] = [
  // 좌상: 서버실 (새벽에만 밝게)
  { id: 'server',  label: '서버실',     x: 280,  y: 230, w: 260, h: 220, lights: [1.0, 0.5, 0.3, 0.3, 0.3, 0.6] },
  // 우상: 증권사 (장중에만)
  { id: 'broker',  label: '증권사',     x: 1380, y: 230, w: 260, h: 220, lights: [0.0, 0.2, 1.0, 1.0, 0.9, 0.0] },
  // 좌하: 내 집 (아침 8시 클라이맥스)
  { id: 'home',    label: '내 집',      x: 280,  y: 600, w: 260, h: 220, lights: [0.0, 1.0, 0.7, 0.5, 0.6, 1.0] },
  // 우하: 시장 (장중)
  { id: 'market',  label: '시장',       x: 1380, y: 600, w: 260, h: 220, lights: [0.0, 0.1, 1.0, 1.0, 0.9, 0.0] },
];

// 건물 사이 연결선 (서버실 → 내집)
const CONNECTIONS = [
  { from: 'server', to: 'home', onAt: 0.30 },
  { from: 'home',   to: 'broker', onAt: 0.55 },
  { from: 'broker', to: 'market', onAt: 0.55 },
];

const TIME_LABELS = ['04:00', '08:00', '09:00', '12:00', '15:30', '23:00'];

export const DakkakC_Pictogram = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [10, DUR - 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const labelOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.02 + 0.035;

  // 현재 어느 시간 슬롯에 있는지 (보간)
  const slotIndex = (() => {
    for (let i = SLOTS.length - 1; i >= 0; i--) {
      if (prog >= SLOTS[i]) return i;
    }
    return 0;
  })();
  const currentTime = TIME_LABELS[slotIndex];

  // 08:00 클라이맥스 — 내 집 강조
  const homeClimax = interpolate(prog, [0.38, 0.46], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const homeFade = interpolate(prog, [0.46, 0.55], [1, 0.5], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const homeHero = homeClimax * homeFade;

  // 딸깍 자막
  const ddakOp = interpolate(prog, [0.85, 0.94], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 시간 자막 변화 페이드
  const timeKeyFrame = SLOTS.findIndex(s => s >= prog - 0.01);
  const timeOp = interpolate(prog, [Math.max(0, (timeKeyFrame >= 0 ? SLOTS[timeKeyFrame] : 0) - 0.02), (timeKeyFrame >= 0 ? SLOTS[timeKeyFrame] : 0) + 0.04], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 현재 밝기 보간 — 슬롯 간 부드럽게
  const buildingBrightness = (b: Building) => {
    if (slotIndex >= b.lights.length - 1) return b.lights[b.lights.length - 1];
    const a = SLOTS[slotIndex];
    const c = SLOTS[Math.min(slotIndex + 1, SLOTS.length - 1)];
    const t = (prog - a) / Math.max(0.001, c - a);
    return b.lights[slotIndex] * (1 - t) + b.lights[Math.min(slotIndex + 1, b.lights.length - 1)] * t;
  };

  // 건물 위치 찾기
  const getBuilding = (id: string) => BUILDINGS.find(b => b.id === id)!;

  return (
    <AbsoluteFill style={{ background: '#020806', opacity: fadeIn, fontFamily: FONT }}>
      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 60%, rgba(0,255,208,1) 0%, transparent 70%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 40, right: 60,
        color: C.textSub, fontSize: 22, fontWeight: 600, letterSpacing: 4,
        opacity: labelOp, zIndex: 50,
      }}>SAMPLE C · PICTOGRAM CITY</div>

      {/* 좌상단 현재 시간 디지털 디스플레이 */}
      <div style={{
        position: 'absolute', top: 60, left: 80,
        opacity: labelOp,
      }}>
        <div style={{ color: C.textSub, fontSize: 20, fontWeight: 500, letterSpacing: 4, marginBottom: 6 }}>NOW</div>
        <div style={{
          color: C.main, fontSize: 88, fontWeight: 900,
          fontFamily: '"Consolas", "Menlo", monospace',
          textShadow: GLOW.mid.text,
          letterSpacing: 2,
          opacity: timeOp,
        }}>{currentTime}</div>
      </div>

      {/* 도시 격자 (배경) */}
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, opacity: 0.08, pointerEvents: 'none' }}>
        {Array.from({ length: 13 }).map((_, i) => (
          <line key={`v${i}`} x1={i * 160} y1={0} x2={i * 160} y2={1080} stroke={C.main} strokeWidth={1} />
        ))}
        {Array.from({ length: 8 }).map((_, i) => (
          <line key={`h${i}`} x1={0} y1={i * 135} x2={1920} y2={i * 135} stroke={C.main} strokeWidth={1} />
        ))}
      </svg>

      {/* 연결선 */}
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        {CONNECTIONS.map((conn, i) => {
          const from = getBuilding(conn.from);
          const to = getBuilding(conn.to);
          const fx = from.x + from.w / 2;
          const fy = from.y + from.h / 2;
          const tx = to.x + to.w / 2;
          const ty = to.y + to.h / 2;
          const drawProg = interpolate(prog, [conn.onAt, conn.onAt + 0.08], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
          // 흐르는 점 (펄스)
          const dotProg = ((f * 0.012) % 1);
          const dotX = fx + (tx - fx) * dotProg;
          const dotY = fy + (ty - fy) * dotProg;
          return (
            <g key={i}>
              <line
                x1={fx} y1={fy}
                x2={fx + (tx - fx) * drawProg}
                y2={fy + (ty - fy) * drawProg}
                stroke={C.main} strokeWidth={2} strokeDasharray="8 8"
                opacity={0.45 * drawProg}
                style={{ filter: 'drop-shadow(0 0 4px rgba(0,255,208,0.6))' }}
              />
              {drawProg > 0.9 && (
                <circle cx={dotX} cy={dotY} r={6} fill={C.main}
                  style={{ filter: 'drop-shadow(0 0 8px #00FFD0)' }} />
              )}
            </g>
          );
        })}
      </svg>

      {/* 건물들 */}
      {BUILDINGS.map((b, i) => {
        const brightness = buildingBrightness(b);
        const isHome = b.id === 'home';
        const hero = isHome ? homeHero : 0;
        const totalGlow = Math.max(brightness, hero);

        return (
          <div key={i} style={{
            position: 'absolute',
            left: b.x, top: b.y, width: b.w, height: b.h,
          }}>
            {/* 건물 본체 */}
            <div style={{
              position: 'absolute', inset: 0,
              background: `rgba(17, 17, 17, ${0.7 + totalGlow * 0.2})`,
              border: `2px solid ${totalGlow > 0.3 ? C.main : C.borderSub}`,
              borderRadius: 14,
              boxShadow: totalGlow > 0.1
                ? `0 0 ${12 + totalGlow * 40}px rgba(0,255,208,${0.3 + totalGlow * 0.7}), inset 0 0 ${20 + totalGlow * 30}px rgba(0,255,208,${totalGlow * 0.25})`
                : 'none',
              transition: 'all 0.3s',
            }} />

            {/* 창문 그리드 (3x4) */}
            <div style={{
              position: 'absolute', inset: '18% 20% 30% 20%',
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gridTemplateRows: 'repeat(3, 1fr)', gap: 8,
            }}>
              {Array.from({ length: 9 }).map((_, w) => {
                const winOn = totalGlow > 0.1 && ((Math.sin((f + i * 13 + w * 7) * 0.05) * 0.5 + 0.5) > 0.3);
                return (
                  <div key={w} style={{
                    background: winOn ? `rgba(0, 255, 208, ${0.4 + totalGlow * 0.5})` : 'rgba(255,255,255,0.05)',
                    borderRadius: 3,
                    boxShadow: winOn ? `0 0 6px rgba(0,255,208,${totalGlow * 0.8})` : 'none',
                  }} />
                );
              })}
            </div>

            {/* 건물 라벨 */}
            <div style={{
              position: 'absolute', bottom: -42, left: 0, right: 0,
              textAlign: 'center',
              color: totalGlow > 0.3 ? C.main : C.textSub,
              fontSize: 26, fontWeight: 800, letterSpacing: 3,
              textShadow: totalGlow > 0.3 ? GLOW.weak.text : 'none',
            }}>{b.label}</div>
          </div>
        );
      })}

      {/* 딸깍 자막 */}
      <div style={{
        position: 'absolute', bottom: 100, left: 0, right: 0,
        textAlign: 'center',
        color: C.main, fontSize: 96, fontWeight: 900, letterSpacing: 8,
        textShadow: GLOW.strong.text,
        opacity: ddakOp,
        transform: `scale(${0.85 + ddakOp * 0.15})`,
      }}>딸깍</div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '8%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: labelOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 30, fontWeight: 700, opacity: 0.8 }}>
          도시의 불빛이 시간을 말한다
        </div>
      </div>
    </AbsoluteFill>
  );
};
