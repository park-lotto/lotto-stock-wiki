// AG_S04_6 — 씬4-6 배포 직원 (587프레임 / 19.58초)
// [01] f0000~0223  "텔레그램·카톡·웹페이지 배포·전송 담당"
// [02] f0242~0419  "7시 일어나는 시간에 이미 다 배포 완료"
// [03] f0439~0587  "커피 한 잔하면서 여유롭게 보면 돼요"
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

const SUBS = [
  { s: 0,   e: 223, text: '마지막 직원이 텔레그램·카톡·웹페이지에 배포·전송해요.' },
  { s: 242, e: 419, text: '제가 7시에 일어나는 시간에 이미 모두 배포 완료되어 있어요.' },
  { s: 439, e: 587, text: '일어나서 커피 한 잔하면서 여유롭게 보면 됩니다.' },
];
function getSub(f: number) {
  const s = SUBS.find(x => f >= x.s && f <= x.e);
  if (!s) return null;
  return { text: s.text, op: Math.min((f - s.s) / 8, 1, (s.e - f) / 8) };
}

const CHANNELS = [
  { icon: '📱', label: '텔레그램', col: '#2AABEE', startF: 48 },
  { icon: '💬', label: '카카오톡', col: '#FEE500', startF: 88 },
  { icon: '🖥️', label: '웹페이지',  col: C.main,    startF: 128 },
];

export const AG_S04_6_Deploy: React.FC = () => {
  const f   = useCurrentFrame();
  const sub = getSub(f);
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // 📨 이모지 (f5~42)
  const sendOp    = ip(f, 5, 40);
  const sendScale = interpolate(f, [5, 42], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.85)) });
  const sendPulse = sendOp > 0.9 ? 1 + Math.sin(f * 0.07) * 0.02 : 1;

  // 라벨 (f25~55)
  const t1Op = ip(f, 25, 55);

  // 채널 아이콘 날아오는 파이프라인 (f48~170)
  // 📨에서 각 채널로 화살표 + 체크

  // "07:00 완료" 시계 (f242~350)
  const clockOp    = ip(f, 242, 288);
  const clockScale = interpolate(f, [242, 288], [0.3, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.8)) });

  // "배포 완료" 체크 (f300~380)
  const doneOp    = ip(f, 300, 345);
  const doneScale = interpolate(f, [300, 345], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.75)) });
  const donePulse = doneOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.025 : 1;

  // "커피 + 여유" 클라이맥스 (f439~545)
  const coffeeOp    = ip(f, 439, 478);
  const coffeeScale = interpolate(f, [439, 478], [0.3, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.8)) });

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: ip(f, 0, 18), fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-6.m4a')} volume={1} />
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)', opacity: bgGlow, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 28, right: 48, color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28) }}>SCENE 4-6 · 배포 직원</div>

      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 32 }}>

        {/* 📨 + 타이틀 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ opacity: sendOp, transform: `scale(${sendScale * sendPulse})`, fontSize: 110, filter: `drop-shadow(0 0 20px rgba(0,255,208,0.5))` }}>📨</div>
          <div style={{ opacity: t1Op }}>
            <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6, marginBottom: 6 }}>DELIVERY AGENT</div>
            <div style={{ fontSize: 44, fontWeight: 900, color: '#e5e7eb' }}>배포 · 전송 담당</div>
          </div>
        </div>

        {/* 채널 3개 (파이프라인) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          {CHANNELS.map((ch, i) => {
            const op  = ip(f, ch.startF, ch.startF + 30);
            const chk = ip(f, ch.startF + 35, ch.startF + 55, 0, 1, Easing.out(Easing.elastic(1.2)));
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {i > 0 && (
                  <div style={{ opacity: ip(f, CHANNELS[i-1].startF + 30, CHANNELS[i-1].startF + 50), fontSize: 28, color: '#444' }}>→</div>
                )}
                <div style={{
                  opacity: op, transform: `scale(${0.3 + op * 0.7})`, transformOrigin: 'center',
                  padding: '14px 24px',
                  background: `${ch.col}12`,
                  border: `1.5px solid ${ch.col}40`,
                  borderRadius: 18,
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, minWidth: 160,
                }}>
                  <span style={{ fontSize: 56 }}>{ch.icon}</span>
                  <div style={{ fontSize: 22, fontWeight: 700, color: ch.col }}>{ch.label}</div>
                  {chk > 0.5 && <div style={{ opacity: chk, transform: `scale(${chk})`, fontSize: 20, color: '#22c55e', fontWeight: 700 }}>✓ 전송 완료</div>}
                </div>
              </div>
            );
          })}
        </div>

        {/* 07:00 시계 */}
        {clockOp > 0.01 && (
          <div style={{ opacity: clockOp, transform: `scale(${clockScale})`, transformOrigin: 'center', textAlign: 'center' }}>
            <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 5, marginBottom: 6 }}>DELIVERED AT</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center' }}>
              <span style={{ fontSize: 60 }}>☀️</span>
              <div style={{ fontSize: 88, fontWeight: 900, fontFamily: '"Consolas","Menlo",monospace', color: '#22c55e', textShadow: '0 0 20px rgba(34,197,94,0.6)', lineHeight: 1 }}>07:00</div>
            </div>
          </div>
        )}

        {/* "배포 완료" */}
        {doneOp > 0.01 && (
          <div style={{ opacity: doneOp, transform: `scale(${doneScale * donePulse})`, transformOrigin: 'center', display: 'flex', alignItems: 'center', gap: 16, padding: '14px 44px', background: 'rgba(34,197,94,0.08)', border: '1.5px solid rgba(34,197,94,0.35)', borderRadius: 20 }}>
            <span style={{ fontSize: 52 }}>✅</span>
            <div style={{ fontSize: 52, fontWeight: 900, color: '#22c55e' }}>배포 완료</div>
          </div>
        )}

        {/* 커피 + 여유 클라이맥스 */}
        {coffeeOp > 0.01 && (
          <div style={{ opacity: coffeeOp, transform: `scale(${coffeeScale})`, transformOrigin: 'center', textAlign: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, justifyContent: 'center' }}>
              <span style={{ fontSize: 80 }}>☕</span>
              <div style={{ fontSize: 60, fontWeight: 900, color: C.main, textShadow: dynGlow }}>여유롭게</div>
              <span style={{ fontSize: 80 }}>😌</span>
            </div>
          </div>
        )}
      </div>

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80, background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)' }}>
        {sub && <div style={{ color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center', opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};
