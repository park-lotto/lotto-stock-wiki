// AG_S04_5 — 씬4-5 브리핑 직원 (637프레임 / 21.24초)
// [01] f0000~0194  "브리핑 자료만 만들어요. 아침에 일어나서 보는 게 이겁니다."
// [02] f0215~0355  "섹터온도, 탑픽, 새벽시황, 오늘일정"
// [03] f0371~0443  "한 장만 보면 돼요"
// [04] f0461~0637  "대시보드 웹페이지도 만들고 있어요"
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

const SUBS = [
  { s: 0,   e: 194, text: '이 직원은 브리핑 자료만 만들어요. 아침에 일어나서 보는 게 이겁니다.' },
  { s: 215, e: 355, text: '섹터 온도, 오늘의 탑픽, 새벽 시황, 오늘의 일정 등.' },
  { s: 371, e: 443, text: '이 친구가 만들어주는 한 장만 보면 돼요.' },
  { s: 461, e: 637, text: '대시보드 웹페이지도 준비 중입니다.' },
];
function getSub(f: number) {
  const s = SUBS.find(x => f >= x.s && f <= x.e);
  if (!s) return null;
  return { text: s.text, op: Math.min((f - s.s) / 8, 1, (s.e - f) / 8) };
}

const BRIEF_ITEMS = [
  { icon: '🌡️', label: '섹터 온도',  sub: '반도체🔴 방산🔴 조선🟠', col: C.main,    startF: 215 },
  { icon: '🎯', label: '오늘의 탑픽', sub: '삼성전기 7/9점',          col: '#FF4757', startF: 258 },
  { icon: '🌐', label: '새벽 시황',   sub: 'VIX 16↓ 나스닥 +0.8%',   col: '#FFA502', startF: 295 },
  { icon: '📅', label: '오늘의 일정', sub: 'ASCO · FOMC D-16',        col: '#9ca3af', startF: 332 },
];

export const AG_S04_5_Brief: React.FC = () => {
  const f   = useCurrentFrame();
  const sub = getSub(f);
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // 📋 이모지 (f5~42)
  const briefOp    = ip(f, 5, 40);
  const briefScale = interpolate(f, [5, 42], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.85)) });
  const briefPulse = briefOp > 0.9 ? 1 + Math.sin(f * 0.07) * 0.02 : 1;

  // 라벨 (f25~55)
  const t1Op = ip(f, 25, 55);
  const t1Y  = interpolate(f, [25, 55], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "한 장만 보면 돼요" 클라이맥스 (f371~440)
  const oneOp    = ip(f, 371, 410);
  const oneScale = interpolate(f, [371, 410], [0.4, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.8)) });
  const onePulse = oneOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.022 : 1;

  // 대시보드 예고 (f461~580)
  const dashOp = ip(f, 461, 505);
  const dashY  = interpolate(f, [461, 505], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: ip(f, 0, 18), fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-5.m4a')} volume={1} />
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)', opacity: bgGlow, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 28, right: 48, color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28) }}>SCENE 4-5 · 브리핑 직원</div>

      {/* 📋 + 타이틀 */}
      <div style={{ position: 'absolute', top: 68, left: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
        <div style={{ opacity: briefOp, transform: `scale(${briefScale * briefPulse})`, fontSize: 100, filter: `drop-shadow(0 0 20px rgba(0,255,208,0.5))` }}>📋</div>
        <div style={{ opacity: t1Op, transform: `translateY(${t1Y}px)` }}>
          <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6, marginBottom: 6 }}>BRIEFING AGENT</div>
          <div style={{ fontSize: 44, fontWeight: 900, color: '#e5e7eb' }}>아침에 보는 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>그 자료</span></div>
        </div>
      </div>

      {/* 브리핑 4개 항목 (2×2 그리드) */}
      <div style={{ position: 'absolute', top: 220, left: 0, right: 0, display: 'flex', flexWrap: 'wrap', gap: 20, padding: '0 120px', justifyContent: 'center' }}>
        {BRIEF_ITEMS.map((item, i) => {
          const itemOp  = ip(f, item.startF, item.startF + 32);
          const itemTy  = interpolate(f, [item.startF, item.startF + 32], [35, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.4)) });
          return (
            <div key={i} style={{
              width: 'calc(50% - 10px)', opacity: itemOp, transform: `translateY(${itemTy}px)`,
              padding: '22px 28px',
              background: 'rgba(255,255,255,0.04)',
              border: `1.5px solid ${item.col}25`,
              borderRadius: 20,
              display: 'flex', alignItems: 'center', gap: 20,
            }}>
              <span style={{ fontSize: 64, flexShrink: 0, filter: `drop-shadow(0 2px 8px ${item.col}44)` }}>{item.icon}</span>
              <div>
                <div style={{ fontSize: 26, fontWeight: 800, color: item.col, marginBottom: 6 }}>{item.label}</div>
                <div style={{ fontSize: 18, color: '#6b7280' }}>{item.sub}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* "한 장만 보면 돼요" */}
      {oneOp > 0.01 && (
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 218, textAlign: 'center', opacity: oneOp, transform: `scale(${oneScale * onePulse})`, transformOrigin: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 16, padding: '14px 48px', background: `${C.main}10`, border: `2px solid ${C.main}35`, borderRadius: 20 }}>
            <span style={{ fontSize: 52 }}>☕</span>
            <div style={{ fontSize: 56, fontWeight: 900, color: C.main, textShadow: dynGlow }}>한 장만 보면 돼요</div>
          </div>
        </div>
      )}

      {/* 대시보드 예고 */}
      {dashOp > 0.01 && (
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 218, textAlign: 'center', opacity: dashOp * (1 - oneOp), transform: `translateY(${dashY}px)` }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 14, padding: '12px 36px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 40 }}>
            <span style={{ fontSize: 36 }}>🖥️</span>
            <div style={{ fontSize: 28, color: '#9ca3af', fontWeight: 600 }}>대시보드 웹페이지 준비 중</div>
          </div>
        </div>
      )}

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80, background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)' }}>
        {sub && <div style={{ color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center', opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};
