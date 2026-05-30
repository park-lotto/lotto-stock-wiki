// AG_S04_2 — 씬4-2 수집 직원 (1660프레임 / 55.34초)
// [01] f0000~0167  "24시간 대기. 리포트·텔레그램·뉴스·유튜브"
// [02] f0181~0356  "리포트·텔레그램 바로받기"
// [03] f0376~0520  "뉴스 키워드 설정"
// [04] f0537~0658  "유튜브 인사이트"
// [05] f0677~0776  "자는 동안 미국장"
// [06] f0776~1008  "섹터 움직임·미국 실적 긁어와요"
// [07] f1008~1120  "지식베이스에 계속 쌓입니다"
// [08] f1149~1328  "14:xx 23:xx 1:xx 타임스탬프"
// [09] f1354~1400  "자는 동안만이 아닙니다"
// [10] f1426~1611  "밥먹고 운동하는 동안에도"
// [11] f1611~1660  "끊기는 게 없어요"
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

const SUBS = [
  { s: 0,    e: 167,  text: '자료 수집 직원. 이 친구는 24시간 대기 중입니다.' },
  { s: 181,  e: 356,  text: '증권사 리포트, 텔레그램 채널 내용 — 올라오면 바로 받아요.' },
  { s: 376,  e: 520,  text: '키워드 설정 넣으면 네이버 뉴스에서도 바로 가져와요.' },
  { s: 537,  e: 658,  text: '유튜브 채널 인사이트도 뜨자마자 바로 가져와요.' },
  { s: 677,  e: 776,  text: '제가 자는 동안엔 미국장을 추적합니다.' },
  { s: 776,  e: 1008, text: '섹터 움직임 추적하고 미국 실적 발표 나오면 바로 긁어와요.' },
  { s: 1008, e: 1120, text: '이게 제 서버 지식베이스에 계속 쌓입니다.' },
  { s: 1149, e: 1328, text: '낮 2시에도, 밤 11시에도, 새벽 1시에도 — 다 찍혀있어요.' },
  { s: 1354, e: 1400, text: '제가 자는 동안만이 아닙니다.' },
  { s: 1426, e: 1611, text: '밥 먹고 운동하는 시간에도 새 정보 들어오면 바로 처리해요.' },
  { s: 1611, e: 1660, text: '끊기는 게 없어요.' },
];
function getSub(f: number) {
  const s = SUBS.find(x => f >= x.s && f <= x.e);
  if (!s) return null;
  return { text: s.text, op: Math.min((f - s.s) / 8, 1, (s.e - f) / 8) };
}

// 소스 아이콘 — 📡에 날아와 흡수됨
const SOURCES = [
  { icon: '📄', label: '리포트',     startF: 181, fromX: -300, fromY: -120, col: '#9ca3af' },
  { icon: '📱', label: '텔레그램',   startF: 240, fromX:  300, fromY: -80,  col: '#FFA502' },
  { icon: '📰', label: '뉴스',       startF: 376, fromX: -280, fromY:  80,  col: '#9ca3af' },
  { icon: '▶️', label: '유튜브',     startF: 537, fromX:  280, fromY:  100, col: '#FF4757' },
  { icon: '🇺🇸', label: '미국장',    startF: 677, fromX:    0, fromY: -250, col: '#FFA502' },
];

// 타임스탬프 목록
const TIMESTAMPS = [
  { time: '14:23', label: '리포트 수집',   col: '#9ca3af' },
  { time: '15:04', label: '텔레그램',      col: '#FFA502' },
  { time: '16:31', label: '뉴스 8건',      col: '#9ca3af' },
  { time: '23:03', label: '유튜브 인사이트', col: '#FF4757' },
  { time: '01:14', label: '미국실적 발표', col: '#FFA502' },
  { time: '03:00', label: '수급 스캔',     col: C.main    },
];

export const AG_S04_2_Collect: React.FC = () => {
  const f   = useCurrentFrame();
  const sub = getSub(f);
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;

  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // 📡 중앙 등장 (f5~40)
  const antOp    = ip(f, 5, 38);
  const antScale = interpolate(f, [5, 40], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.85)) });
  const antPulse = antOp > 0.9 ? 1 + Math.sin(f * 0.08) * 0.02 : 1;

  // 라벨 (f25~50)
  const labelOp = ip(f, 25, 50);

  // "24시간 대기" 텍스트 (f40~85)
  const t1Op = ip(f, 40, 80);
  const t1Y  = interpolate(f, [40, 80], [35, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 소스 아이콘 날아와서 📡에 흡수
  const sourceAnim = (i: number) => {
    const s       = SOURCES[i];
    const elapsed = f - s.startF;
    if (elapsed < 0) return { op: 0, x: s.fromX, y: s.fromY, scale: 0.3 };
    const t       = Math.min(1, elapsed / 55);
    const absorb  = t > 0.85 ? (t - 0.85) / 0.15 : 0;
    return {
      op:    absorb > 0.5 ? 1 - absorb : ip(f, s.startF, s.startF + 20),
      x:     s.fromX * (1 - t),
      y:     s.fromY * (1 - t),
      scale: 0.3 + t * 0.9 - absorb * 0.9,
    };
  };

  // 수집 카운터 (f0~1400)
  const countVal = Math.round(ip(f, 40, 1400, 0, 47));
  const countOp  = ip(f, 35, 60);

  // 타임스탬프 (f1149~1400 구간에서 순차 등장)
  const tsStart = (i: number) => 1149 + i * 30;

  // "끊기는 게 없어요" 클라이맥스 (f1615~1660)
  const finalOp    = ip(f, 1615, 1650);
  const finalScale = interpolate(f, [1615, 1650], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.75)) });

  // LIVE 점멸
  const livePulse = Math.sin(f * 0.15) > 0 ? 1 : 0.3;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: ip(f, 0, 18), fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-2.m4a')} volume={1} />

      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 42%, rgba(0,255,208,1) 0%, transparent 65%)', opacity: bgGlow, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 28, right: 48, color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28) }}>SCENE 4-2 · 수집 직원</div>

      {/* 📡 중앙 */}
      <div style={{ position: 'absolute', left: 960 - 90, top: 340, width: 180, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
        <div style={{
          opacity: antOp, transform: `scale(${antScale * antPulse})`, transformOrigin: 'center',
          fontSize: 150,
          filter: `drop-shadow(0 0 ${20 + pulse * 15}px rgba(0,255,208,0.6))`,
        }}>📡</div>

        {/* LIVE 배지 */}
        <div style={{ opacity: labelOp, display: 'flex', alignItems: 'center', gap: 8, padding: '5px 18px', background: 'rgba(255,0,0,0.12)', border: '1px solid rgba(255,0,0,0.35)', borderRadius: 20 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff4444', opacity: livePulse, boxShadow: '0 0 6px #ff4444' }} />
          <span style={{ color: '#ff6666', fontSize: 18, fontWeight: 700, letterSpacing: 3 }}>LIVE</span>
        </div>

        <div style={{ opacity: t1Op, transform: `translateY(${t1Y}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 44, fontWeight: 900, color: C.main, textShadow: dynGlow }}>24시간 대기</div>
        </div>
      </div>

      {/* 수집 카운터 (우하단) */}
      <div style={{ position: 'absolute', right: 60, bottom: 200, opacity: countOp, textAlign: 'right' }}>
        <div style={{ color: '#4b5563', fontSize: 13, fontWeight: 700, letterSpacing: 4, marginBottom: 6 }}>NOW COLLECTED</div>
        <div style={{ fontSize: 90, fontWeight: 900, fontFamily: '"Consolas","Menlo",monospace', color: C.main, textShadow: GLOW.weak.text, lineHeight: 1 }}>
          {String(countVal).padStart(2, '0')}
        </div>
        <div style={{ color: '#555', fontSize: 16, marginTop: 4 }}>건</div>
      </div>

      {/* 소스 아이콘들 (날아와 흡수) */}
      {SOURCES.map((src, i) => {
        const { op, x, y, scale } = sourceAnim(i);
        if (op <= 0) return null;
        return (
          <div key={i} style={{
            position: 'absolute', left: 960 - 50 + x, top: 410 + y,
            opacity: op, transform: `scale(${scale})`, transformOrigin: 'center',
            textAlign: 'center', width: 100,
          }}>
            <div style={{ fontSize: 64 }}>{src.icon}</div>
            <div style={{ fontSize: 16, color: src.col, fontWeight: 700, marginTop: 6 }}>{src.label}</div>
          </div>
        );
      })}

      {/* 타임스탬프 목록 (f1149~) */}
      {f >= 1140 && (
        <div style={{ position: 'absolute', left: 100, top: 160, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {TIMESTAMPS.map((ts, i) => {
            const tOp = ip(f, tsStart(i), tsStart(i) + 25);
            return (
              <div key={i} style={{
                opacity: tOp,
                transform: `translateX(${interpolate(f, [tsStart(i), tsStart(i)+25], [-50, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })}px)`,
                display: 'flex', alignItems: 'center', gap: 18,
                padding: '10px 24px',
                background: 'rgba(255,255,255,0.035)',
                border: `1px solid ${ts.col}25`,
                borderRadius: 12,
              }}>
                <div style={{ fontSize: 24, fontWeight: 700, fontFamily: '"Consolas","Menlo",monospace', color: ts.col, minWidth: 72 }}>{ts.time}</div>
                <div style={{ fontSize: 20, color: '#6b7280' }}>{ts.label}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* "끊기는 게 없어요" 클라이맥스 */}
      {finalOp > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: finalOp }}>
          <div style={{ transform: `scale(${finalScale})`, transformOrigin: 'center', textAlign: 'center' }}>
            <div style={{ fontSize: 36, color: '#6b7280', marginBottom: 12 }}>🔄</div>
            <div style={{ fontSize: 90, fontWeight: 900, color: C.main, textShadow: dynGlow }}>끊기는 게 없어요.</div>
          </div>
        </div>
      )}

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80, background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)' }}>
        {sub && <div style={{ color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center', opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};
