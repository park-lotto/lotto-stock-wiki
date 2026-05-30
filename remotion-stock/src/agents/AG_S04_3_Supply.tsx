// AG_S04_3 — 씬4-3 수급 직원 (725프레임 / 24.18초)
// [01] f0000~0246  "새벽 3시 출근. 500개 종목 분석"
// [02] f0266~0373  "의미있는 500개만 분석"
// [03] f0396~0513  "외인·기관 수급 빠진 종목 골라냄"
// [04] f0532~0725  "수급 빈집 — 다음 영상에서 설명"
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

const SUBS = [
  { s: 0,   e: 246, text: '수급 분석 직원. 이 친구는 새벽 3시 출근합니다.' },
  { s: 266, e: 373, text: '2500개 중 의미 있는 약 500개 종목만 분석해요.' },
  { s: 396, e: 513, text: '최근 외국인·기관 수급이 빠진 종목들을 골라냅니다.' },
  { s: 532, e: 725, text: '저는 이걸 수급 빈집이라고 해요. 다음 영상에서 따로 설명드릴게요.' },
];
function getSub(f: number) {
  const s = SUBS.find(x => f >= x.s && f <= x.e);
  if (!s) return null;
  return { text: s.text, op: Math.min((f - s.s) / 8, 1, (s.e - f) / 8) };
}

export const AG_S04_3_Supply: React.FC = () => {
  const f   = useCurrentFrame();
  const sub = getSub(f);
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // 🔍 등장 (f5~45)
  const magOp    = ip(f, 5, 42);
  const magScale = interpolate(f, [5, 45], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.9)) });
  const magPulse = magOp > 0.9 ? 1 + Math.sin(f * 0.07) * 0.022 : 1;

  // "새벽 3시 출근" (f15~60)
  const t1Op = ip(f, 15, 55);
  const t1X  = interpolate(f, [15, 55], [-120, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 500개 카운트업 (f266~340)
  const scanCount = Math.round(ip(f, 266, 340, 0, 500));
  const scanOp    = ip(f, 266, 300);
  const scanPulse = scanOp > 0.9 ? 1 + Math.sin(f * 0.1) * 0.025 : 1;

  // 스캔 진행 바 (f266~373)
  const barW = ip(f, 266, 373) * 100;

  // 결과 아이콘들 등장 — A/B등급 빈집 (f396~513)
  const gradeA_op = ip(f, 396, 430);
  const gradeB_op = ip(f, 440, 474);

  // "수급 빈집" 클라이맥스 (f532~640)
  const vacOp    = ip(f, 532, 575);
  const vacScale = interpolate(f, [532, 575], [0.3, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.8)) });
  const vacPulse = vacOp > 0.97 ? 1 + Math.sin(f * 0.09) * 0.03 : 1;

  // "다음 영상" 예고 (f640~725)
  const nextOp = ip(f, 640, 680);

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: ip(f, 0, 18), fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-3.m4a')} volume={1} />
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 42%, rgba(0,255,208,1) 0%, transparent 65%)', opacity: bgGlow, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 28, right: 48, color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28) }}>SCENE 4-3 · 수급 직원</div>

      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 28 }}>

        {/* 🔍 + "새벽 3시" */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 30 }}>
          <div style={{ opacity: magOp, transform: `scale(${magScale * magPulse})`, fontSize: 120, filter: `drop-shadow(0 0 20px rgba(0,255,208,0.5))` }}>🔍</div>
          <div style={{ opacity: t1Op, transform: `translateX(${t1X}px)` }}>
            <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6, marginBottom: 8 }}>SUPPLY AGENT</div>
            <div style={{ fontSize: 52, fontWeight: 900, color: '#9ca3af' }}>새벽 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>03:00</span> 출근</div>
          </div>
        </div>

        {/* 스캔 카운터 + 바 */}
        {scanOp > 0.01 && (
          <div style={{ width: 800, opacity: scanOp }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ color: '#6b7280', fontSize: 22, fontWeight: 600 }}>종목 스캔</div>
              <div style={{
                fontSize: 52, fontWeight: 900, fontFamily: '"Consolas","Menlo",monospace',
                color: C.main, textShadow: dynGlow,
                transform: `scale(${scanPulse})`,
              }}>{scanCount.toLocaleString()}<span style={{ fontSize: 28, color: '#6b7280' }}>개</span></div>
            </div>
            <div style={{ width: '100%', height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4 }}>
              <div style={{ width: `${barW}%`, height: '100%', background: `linear-gradient(90deg, ${C.main}88, ${C.main})`, borderRadius: 4, boxShadow: `0 0 8px ${C.main}66` }} />
            </div>
          </div>
        )}

        {/* A/B 등급 빈집 */}
        {gradeA_op > 0.01 && (
          <div style={{ display: 'flex', gap: 24 }}>
            {[
              { grade: 'A', label: '완전 빈집', count: '29개', col: C.main },
              { grade: 'B', label: '반 빈집',   count: '38개', col: '#FFA502', op: gradeB_op },
            ].map((g, i) => (
              <div key={i} style={{
                opacity: i === 0 ? gradeA_op : gradeB_op,
                transform: `translateY(${interpolate(i === 0 ? gradeA_op : gradeB_op, [0, 1], [25, 0])}px)`,
                padding: '18px 32px',
                background: `${g.col}10`,
                border: `1.5px solid ${g.col}40`,
                borderRadius: 18,
                textAlign: 'center', minWidth: 180,
              }}>
                <div style={{ fontSize: 36, fontWeight: 900, color: g.col, marginBottom: 6 }}>등급 {g.grade}</div>
                <div style={{ fontSize: 48, fontWeight: 900, fontFamily: '"Consolas","Menlo",monospace', color: g.col, textShadow: `0 0 12px ${g.col}66` }}>{g.count}</div>
                <div style={{ fontSize: 18, color: '#6b7280', marginTop: 4 }}>{g.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* "수급 빈집" 클라이맥스 */}
        {vacOp > 0.01 && (
          <div style={{ opacity: vacOp, transform: `scale(${vacScale * vacPulse})`, transformOrigin: 'center', textAlign: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, justifyContent: 'center' }}>
              <span style={{ fontSize: 80 }}>🏚️</span>
              <div style={{ fontSize: 88, fontWeight: 900, color: C.main, textShadow: dynGlow }}>수급 빈집</div>
              <span style={{ fontSize: 80 }}>🏚️</span>
            </div>
          </div>
        )}

        {/* 다음 영상 예고 */}
        {nextOp > 0.01 && (
          <div style={{ opacity: nextOp, display: 'flex', alignItems: 'center', gap: 14, padding: '12px 36px', background: `${C.main}0d`, border: `1px solid ${C.main}30`, borderRadius: 40 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: C.main, boxShadow: `0 0 8px ${C.main}` }} />
            <div style={{ fontSize: 26, color: C.main, fontWeight: 700, letterSpacing: 2 }}>다음 영상에서 자세히 설명</div>
          </div>
        )}
      </div>

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80, background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)' }}>
        {sub && <div style={{ color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center', opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};
