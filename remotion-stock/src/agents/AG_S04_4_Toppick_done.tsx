// AG_S04_4 — 씬4-4 탑픽 직원 (550프레임 / 18.32초)
// [01] f0000~0090  "가장 머리 좋은 직원"
// [02] f0108~0186  "수출 데이터, 증권사 TP"
// [03] f0202~0331  "리레이팅, 수급 빈집 등등"
// [04] f0347~0487  "8가지 기준 교차분석 스코어"
// [05] f0487~0550  "탑픽 결정"
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

const SUBS = [
  { s: 0,   e: 90,  text: '이 직원이 가장 머리 좋은 직원이에요.' },
  { s: 108, e: 186, text: '수출 데이터, 증권사 TP 현황,' },
  { s: 202, e: 331, text: '리레이팅 방향, 수급 빈집 등등에서' },
  { s: 347, e: 487, text: '8가지 기준으로 교차분석해서 스코어를 냅니다.' },
  { s: 487, e: 550, text: '탑픽을 결정해주는 직원입니다.' },
];
function getSub(f: number) {
  const s = SUBS.find(x => f >= x.s && f <= x.e);
  if (!s) return null;
  return { text: s.text, op: Math.min((f - s.s) / 8, 1, (s.e - f) / 8) };
}

const CRITERIA = [
  { icon: '🏚️', label: '수급 빈집',      col: C.main,    startF: 108 },
  { icon: '📦', label: '수출 데이터',     col: '#FFA502', startF: 135 },
  { icon: '💰', label: '증권사 TP',        col: '#9ca3af', startF: 162 },
  { icon: '📈', label: '리레이팅 방향',   col: C.main,    startF: 202 },
  { icon: '🚀', label: '어닝 서프라이즈', col: '#FF4757', startF: 229 },
  { icon: '🇺🇸', label: '미국 커플링',   col: '#FFA502', startF: 256 },
  { icon: '🏛️', label: '정책 이슈',       col: C.main,    startF: 283 },
  { icon: '📅', label: 'D-30 일정',       col: '#9ca3af', startF: 310 },
];

export const AG_S04_4_Toppick: React.FC = () => {
  const f   = useCurrentFrame();
  const sub = getSub(f);
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 32]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // 🧠✨ 이모지 (f5~42)
  const brainOp    = ip(f, 5, 40);
  const brainScale = interpolate(f, [5, 42], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.85)) });
  const brainPulse = brainOp > 0.9 ? 1 + Math.sin(f * 0.07) * 0.022 : 1;

  // "가장 머리 좋은" (f20~60)
  const t1Op = ip(f, 20, 58);
  const t1Y  = interpolate(f, [20, 58], [35, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 기준 8개 체크리스트 순차
  const critAnim = (i: number) => {
    const s = CRITERIA[i].startF;
    return ip(f, s, s + 28);
  };
  // 체크 마크 등장
  const checkAnim = (i: number) => {
    const s = CRITERIA[i].startF + 30;
    return ip(f, s, s + 20, 0, 1, Easing.out(Easing.elastic(1.2)));
  };

  // 스코어 카운트업 (f360~430) 7/9
  const scoreVal = Math.round(ip(f, 360, 430, 0, 7));
  const scoreOp  = ip(f, 355, 395);
  const scorePulse = scoreOp > 0.9 ? 1 + Math.sin(f * 0.1) * 0.028 : 1;

  // 🎯 클라이맥스 (f487~545)
  const targetOp    = ip(f, 487, 525);
  const targetScale = interpolate(f, [487, 525], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.75)) });
  const targetPulse = targetOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.025 : 1;

  // 체크리스트 레이아웃 (2열)
  const CARD_W = 420;
  const startX = (1920 - CARD_W * 2 - 32) / 2;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: ip(f, 0, 18), fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-4.m4a')} volume={1} />
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 35%, rgba(0,255,208,1) 0%, transparent 65%)', opacity: bgGlow, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 28, right: 48, color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28) }}>SCENE 4-4 · 탑픽 직원</div>

      {/* 상단: 🧠 + 타이틀 */}
      <div style={{ position: 'absolute', top: 60, left: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
        <div style={{ opacity: brainOp, transform: `scale(${brainScale * brainPulse})`, fontSize: 90, filter: `drop-shadow(0 0 20px rgba(0,255,208,0.6))` }}>🧠</div>
        <div style={{ opacity: t1Op, transform: `translateY(${t1Y}px)` }}>
          <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6, marginBottom: 6 }}>PICK AGENT</div>
          <div style={{ fontSize: 48, fontWeight: 900, color: '#e5e7eb' }}>가장 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>머리 좋은</span> 직원</div>
        </div>
      </div>

      {/* 기준 8개 체크리스트 (2열) */}
      {CRITERIA.map((c, i) => {
        const op   = critAnim(i);
        const chk  = checkAnim(i);
        const col  = i % 2;
        const row  = Math.floor(i / 2);
        const x    = startX + col * (CARD_W + 32);
        const y    = 200 + row * 88;
        return (
          <div key={i} style={{
            position: 'absolute', left: x, top: y, width: CARD_W, height: 72,
            opacity: op,
            transform: `translateX(${interpolate(op, [0, 1], [col === 0 ? -60 : 60, 0])}px)`,
            display: 'flex', alignItems: 'center', gap: 16,
            padding: '0 22px',
            background: 'rgba(255,255,255,0.03)',
            border: `1px solid rgba(255,255,255,0.07)`,
            borderRadius: 14,
          }}>
            <span style={{ fontSize: 34, flexShrink: 0 }}>{c.icon}</span>
            <div style={{ flex: 1, fontSize: 22, fontWeight: 600, color: '#e5e7eb' }}>{c.label}</div>
            {/* 체크 마크 */}
            <div style={{ opacity: chk, transform: `scale(${chk})`, transformOrigin: 'center', width: 28, height: 28, borderRadius: '50%', background: c.col, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: `0 0 8px ${c.col}66` }}>
              <div style={{ color: '#000', fontSize: 14, fontWeight: 900 }}>✓</div>
            </div>
          </div>
        );
      })}

      {/* 스코어 7/9 */}
      {scoreOp > 0.01 && (
        <div style={{ position: 'absolute', right: 80, top: 220, opacity: scoreOp, transform: `scale(${scorePulse})`, textAlign: 'center' }}>
          <div style={{ color: '#4b5563', fontSize: 14, fontWeight: 700, letterSpacing: 5, marginBottom: 8 }}>SCORE</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <div style={{ fontSize: 120, fontWeight: 900, fontFamily: '"Consolas","Menlo",monospace', color: C.main, textShadow: dynGlow, lineHeight: 1 }}>{scoreVal}</div>
            <div style={{ fontSize: 42, color: '#6b7280' }}>/9</div>
          </div>
        </div>
      )}

      {/* 🎯 탑픽 결정 */}
      {targetOp > 0.01 && (
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 200, textAlign: 'center', opacity: targetOp, transform: `scale(${targetScale * targetPulse})`, transformOrigin: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 20, padding: '18px 56px', background: `${C.main}10`, border: `2px solid ${C.main}35`, borderRadius: 24 }}>
            <span style={{ fontSize: 72 }}>🎯</span>
            <div style={{ fontSize: 72, fontWeight: 900, color: C.main, textShadow: dynGlow }}>탑픽 선정</div>
          </div>
        </div>
      )}

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80, background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)' }}>
        {sub && <div style={{ color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center', opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};
