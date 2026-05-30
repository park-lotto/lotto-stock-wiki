// AG_S04_7 — 씬4-7 나머지 직원들 (686프레임 / 22.86초)
// [01] f0000~0311  "투경 모니터링, 언제 풀리는지 확인"
// [02] f0329~0686  "섹터별 캘린더, 지식 충돌 관리 직원"
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

const SUBS = [
  { s: 0,   e: 311, text: '나머지 직원들도 있어요. 투경 종목 모니터링 — 언제 풀리는지 확인해줘요.' },
  { s: 329, e: 686, text: '섹터별 캘린더 관리, 오래된·충돌 자료 찾아서 정리해주는 직원도 있어요.' },
];
function getSub(f: number) {
  const s = SUBS.find(x => f >= x.s && f <= x.e);
  if (!s) return null;
  return { text: s.text, op: Math.min((f - s.s) / 8, 1, (s.e - f) / 8) };
}

const OTHERS = [
  {
    icon: '⚠️', name: '투경 직원',   role: '투자경고 해제 조건 모니터링',
    detail: '언제 풀리는지 자동 계산',
    col: '#FFA502', startF: 48,
  },
  {
    icon: '📅', name: '캘린더 직원', role: '섹터별 이벤트 일정 관리',
    detail: 'D-Day 카운트다운 자동화',
    col: C.main, startF: 329,
  },
  {
    icon: '🧹', name: '지식 관리 직원', role: '오래된·충돌 자료 탐지·정리',
    detail: '위키 데이터 최신성 유지',
    col: '#9ca3af', startF: 480,
  },
];

export const AG_S04_7_Others: React.FC = () => {
  const f   = useCurrentFrame();
  const sub = getSub(f);
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 28]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // 라벨 (f10~35)
  const labelOp = ip(f, 10, 35);

  // 전체 완성 메시지 (f580~680)
  const finalOp    = ip(f, 580, 620);
  const finalScale = interpolate(f, [580, 620], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.75)) });

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: ip(f, 0, 18), fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-7.m4a')} volume={1} />
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)', opacity: bgGlow, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 28, right: 48, color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28) }}>SCENE 4-7 · 나머지 직원들</div>

      {/* 타이틀 */}
      <div style={{ position: 'absolute', top: 70, left: 0, right: 0, textAlign: 'center', opacity: labelOp }}>
        <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8, marginBottom: 8 }}>그 외</div>
        <div style={{ fontSize: 44, fontWeight: 900, color: '#e5e7eb' }}>
          소개 못한 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>나머지 직원들</span>
        </div>
      </div>

      {/* 직원 3명 카드 */}
      <div style={{ position: 'absolute', top: 200, left: 0, right: 0, display: 'flex', gap: 28, padding: '0 100px', justifyContent: 'center' }}>
        {OTHERS.map((w, i) => {
          const cardOp  = ip(f, w.startF, w.startF + 42);
          const cardTy  = interpolate(f, [w.startF, w.startF + 42], [45, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.5)) });
          const wobble  = cardOp > 0.9 ? Math.sin(f * (0.06 + i * 0.015) + i * 2) * 6 : 0;
          return (
            <div key={i} style={{
              flex: 1, opacity: cardOp,
              transform: `translateY(${cardTy + wobble}px)`,
              padding: '32px 28px',
              background: 'rgba(255,255,255,0.04)',
              border: `1.5px solid ${w.col}30`,
              borderRadius: 24,
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, textAlign: 'center',
            }}>
              <div style={{
                fontSize: 90,
                filter: `drop-shadow(0 2px 14px ${w.col}55)`,
                transform: `scale(${1 + Math.sin(f * 0.05 + i) * 0.018})`,
              }}>{w.icon}</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: w.col }}>{w.name}</div>
              <div style={{ fontSize: 19, color: '#6b7280', lineHeight: 1.5 }}>{w.role}</div>
              <div style={{
                padding: '6px 18px', background: `${w.col}12`, border: `1px solid ${w.col}25`, borderRadius: 20,
                fontSize: 16, color: w.col, fontWeight: 600,
              }}>{w.detail}</div>
            </div>
          );
        })}
      </div>

      {/* 전체 팀 완성 메시지 */}
      {finalOp > 0.01 && (
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 200, textAlign: 'center', opacity: finalOp, transform: `scale(${finalScale})`, transformOrigin: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 18, padding: '16px 52px', background: `${C.main}10`, border: `2px solid ${C.main}30`, borderRadius: 24 }}>
            <span style={{ fontSize: 56 }}>👥</span>
            <div style={{ fontSize: 52, fontWeight: 900, color: C.main, textShadow: dynGlow }}>AI 직원 팀 완성</div>
            <span style={{ fontSize: 56 }}>✅</span>
          </div>
        </div>
      )}

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80, background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)' }}>
        {sub && <div style={{ color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center', opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};
