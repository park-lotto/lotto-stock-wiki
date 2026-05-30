// AG_S04_1 — 씬4-1 총괄 소개 (412프레임 / 13.74초)
// [01] f0000~0094  "총괄입니다. 팀장 역할"
// [02] f0119~0223  "직원들 지시하고 취합하는 역할"
// [03] f0243~0293  "저는 이 친구한테만 지시합니다"
// [04] f0316~0412  "팀장이 나머지한테 일을 분배해줘요"
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

const SUBS = [
  { s: 0,   e: 94,  text: '가운데 있는 친구가 팀장 역할의 총괄입니다.' },
  { s: 119, e: 223, text: '직원들에게 지시하고 결과를 취합하는 역할이에요.' },
  { s: 243, e: 293, text: '저는 이 친구한테만 지시합니다.' },
  { s: 316, e: 412, text: '팀장이 알아서 나머지 팀원들한테 일을 분배해줘요.' },
];
function getSub(f: number) {
  const s = SUBS.find(x => f >= x.s && f <= x.e);
  if (!s) return null;
  return { text: s.text, op: Math.min((f - s.s) / 8, 1, (s.e - f) / 8) };
}

// 직원 아이콘 (보스 아래 부채꼴)
const WORKERS = ['📡','🇺🇸','📄','🔍','⚠️','📊','🎯','📋','✅','📨'];

export const AG_S04_1_Boss: React.FC = () => {
  const f = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const sub = getSub(f);
  const bgGlow = Math.sin(f * 0.04) * 0.028 + 0.05;

  // 🧠 보스 등장 (f8~45) elastic
  const bossScale = interpolate(f, [8, 45], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.85)) });
  const bossOp    = ip(f, 8, 42);
  const bossPulse = bossOp > 0.9 ? 1 + Math.sin(f * 0.07) * 0.025 : 1;
  const bossGlow  = interpolate(Math.sin(f * 0.07) * 0.5 + 0.5, [0, 1], [20, 52]);

  // 라벨 (f30~55)
  const labelOp = ip(f, 30, 55);

  // "총괄" 텍스트 (f38~72) X슬라이드
  const t1X  = interpolate(f, [38, 72], [-120, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = ip(f, 38, 72);
  const t1Ls = interpolate(f, [38, 72], [14, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 직원 아이콘들 부채꼴 등장 (f96~190)
  const workerFan = (i: number) => {
    const s = 96 + i * 9;
    return ip(f, s, s + 25, 0, 1, Easing.out(Easing.elastic(1.0)));
  };

  // 연결선 신호 흐름 (f120~200)
  const flowProg = ip(f, 120, 210);

  // "저는 이 친구한테만" 강조 (f243~295)
  const only1Op    = ip(f, 243, 280);
  const only1Scale = interpolate(f, [243, 280], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.9)) });
  const only1Pulse = only1Op > 0.95 ? 1 + Math.sin(f * 0.1) * 0.025 : 1;

  // 분배 화살표 (f316~380)
  const arrowOp    = ip(f, 316, 360);
  const arrowScale = ip(f, 316, 360);

  // 동적 글로우
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  const BOSS_X = 960;
  const BOSS_Y = 200;
  const FAN_R  = 350;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-1.m4a')} volume={1} />

      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 35%, rgba(0,255,208,1) 0%, transparent 65%)', opacity: bgGlow, pointerEvents: 'none' }} />

      {/* 우상단 */}
      <div style={{ position: 'absolute', top: 28, right: 48, color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28) }}>SCENE 4-1 · 총괄</div>

      {/* SVG 연결선 (보스→직원) */}
      <svg style={{ position: 'absolute', inset: 0, width: 1920, height: 1080, pointerEvents: 'none' }}>
        {WORKERS.map((_, i) => {
          const angle = ((i - 4.5) / 9) * 140 * (Math.PI / 180);
          const wx = BOSS_X + Math.sin(angle) * FAN_R;
          const wy = BOSS_Y + 80 + Math.cos(angle) * 180 + 160;
          const r  = Math.min(1, flowProg * 1.2 - i * 0.08);
          if (r <= 0) return null;
          return (
            <line key={i}
              x1={BOSS_X} y1={BOSS_Y + 80}
              x2={BOSS_X + (wx - BOSS_X) * r} y2={BOSS_Y + 80 + (wy - BOSS_Y - 80) * r}
              stroke={`rgba(0,255,208,${0.15 * r})`}
              strokeWidth={1.5} strokeDasharray="8 5"
            />
          );
        })}
      </svg>

      {/* 🧠 보스 + 라벨 (중앙 상단) */}
      <div style={{ position: 'absolute', left: BOSS_X - 100, top: BOSS_Y - 100, width: 200, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <div style={{
          opacity: bossOp, transform: `scale(${bossScale * bossPulse})`, transformOrigin: 'center',
          fontSize: 140,
          filter: `drop-shadow(0 0 ${bossGlow}px rgba(0,255,208,0.8))`,
        }}>🧠</div>

        {/* "총괄" 텍스트 */}
        <div style={{ opacity: t1Op, transform: `translateX(${t1X}px)` }}>
          <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6, textAlign: 'center', marginBottom: 6, opacity: labelOp }}>ORCHESTRATOR</div>
          <div style={{ fontSize: 56, fontWeight: 900, color: C.main, textShadow: dynGlow, letterSpacing: t1Ls, textAlign: 'center' }}>총괄</div>
        </div>
      </div>

      {/* 직원 아이콘 부채꼴 */}
      {WORKERS.map((icon, i) => {
        const op    = workerFan(i);
        const angle = ((i - 4.5) / 9) * 140 * (Math.PI / 180);
        const wx    = BOSS_X + Math.sin(angle) * FAN_R - 36;
        const wy    = BOSS_Y + 80 + Math.cos(angle) * 180 + 120;
        return (
          <div key={i} style={{
            position: 'absolute', left: wx, top: wy,
            fontSize: 55, opacity: op,
            transform: `scale(${0.3 + op * 0.7})`,
            transformOrigin: 'center',
            textAlign: 'center',
          }}>{icon}</div>
        );
      })}

      {/* "저는 이 친구한테만 지시합니다" 강조 (f243~) */}
      {only1Op > 0.01 && (
        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 280,
          textAlign: 'center',
          opacity: only1Op,
          transform: `scale(${only1Scale * only1Pulse})`,
          transformOrigin: 'center',
        }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 20, padding: '16px 52px', background: `${C.main}10`, border: `2px solid ${C.main}35`, borderRadius: 20 }}>
            <span style={{ fontSize: 60 }}>☝️</span>
            <div style={{ fontSize: 52, fontWeight: 900, color: C.main, textShadow: dynGlow }}>저는 여기에만 지시</div>
          </div>
        </div>
      )}

      {/* 분배 화살표 아이콘 (f316~) */}
      {arrowOp > 0.01 && (
        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 210,
          textAlign: 'center',
          opacity: arrowOp * (1 - only1Op),
          transform: `scale(${arrowScale})`,
          transformOrigin: 'center',
        }}>
          <div style={{ fontSize: 40, color: '#6b7280', fontWeight: 600 }}>팀장이 알아서 나머지한테 분배 → 🔄</div>
        </div>
      )}

      {/* 자막바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80, background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)' }}>
        {sub && <div style={{ color: '#FFFFFF', fontSize: 40, fontWeight: 700, textAlign: 'center', opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};
