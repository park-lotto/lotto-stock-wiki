// AG_S05 — 씬5 클라이맥스 (1110프레임 / 37초)
// ※ 녹음 후 Whisper 싱크로 타이밍 조정 필요
// [01] f0000~0090  "오프닝에서 봤던 이 메시지"
// [02] f0120~0200  "자는 동안만이 아닙니다"
// [03] f0210~0280  "낮에 리포트 나오면 즉시"
// [04] f0290~0340  "뉴스 뜨면 즉시"
// [05] f0350~0430  "밤에 미국 장 열리면 또 즉시"
// [06] f0450~0490  "24시간"
// [07] f0500~0570  "내가 뭘 하든 상관없이"
// [08] f0580~0660  "항상 돌아가고 있습니다"
// [09] f0730~0850  "저는 이제 주식 분석을 합니다가 아니라"
// [10] f0870~0980  "주식 분석 팀을 운영합니다"

import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

function ip(
  f: number, a: number, b: number,
  from = 0, to = 1,
  ease: (t: number) => number = Easing.out(Easing.cubic),
) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease,
  });
}

const SUBS = [
  { s: 0,   e: 90,  text: '오프닝에서 봤던 이 메시지.' },
  { s: 120, e: 200, text: '자는 동안만이 아닙니다.' },
  { s: 210, e: 280, text: '낮에 리포트 나오면 즉시.' },
  { s: 290, e: 340, text: '뉴스 뜨면 즉시.' },
  { s: 350, e: 430, text: '밤에 미국 장 열리면 또 즉시.' },
  { s: 450, e: 490, text: '24시간.' },
  { s: 500, e: 570, text: '내가 뭘 하든 상관없이' },
  { s: 580, e: 660, text: '항상 돌아가고 있습니다.' },
  { s: 730, e: 850, text: '저는 이제 주식 분석을 합니다가 아니라' },
  { s: 870, e: 980, text: '주식 분석 팀을 운영합니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// 24시간 타임라인 구간 데이터
const ZONES = [
  { label: '수집', sublabel: '뉴스·리포트·미국장', icon: '📡', from: 0.0, to: 0.72, col: '#FFA502', startF: 80  },
  { label: '분석', sublabel: '500종목 스캔·탑픽',  icon: '🔍', from: 0.33, to: 0.82, col: C.main,   startF: 200 },
  { label: '브리핑', sublabel: '아침 노트 생성',   icon: '📊', from: 0.67, to: 0.95, col: '#FF4757', startF: 330 },
];

// "즉시" 3회 타이밍
const JAMSILS = [
  { f: 218, label: '낮 — 리포트',   col: '#9ca3af' },
  { f: 298, label: '밤 — 뉴스',     col: '#FFA502' },
  { f: 358, label: '미국장 — 즉시', col: C.main    },
];

export const AG_S05_Climax: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const timeOp = ip(f, 10, 28);
  const sub    = getSub(f);

  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [12, 34]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;
  const bgGlow  = Math.sin(f * 0.04) * 0.025 + 0.04;

  // ── Phase 1 (f0~480): 타임라인 재등장 + 즉시×3 ──────────────────
  const ph1Op = 1 - ip(f, 460, 500);

  // 타이틀 "오프닝에서 봤던 이 메시지"
  const titleOp = ip(f, 5, 45);

  // 타임라인 바 draw-on
  const barW    = ip(f, 50, 300, 0, 1, Easing.inOut(Easing.cubic));
  const barOp   = ip(f, 40, 70);

  // 구간 라벨 등장
  const zone0Op = ip(f, 90,  130);
  const zone1Op = ip(f, 200, 240);
  const zone2Op = ip(f, 330, 370);

  // ── Phase 2 (f450~720): "24시간" + "항상 돌아가고 있습니다" ────────
  const ph2Op = f >= 440 ? ip(f, 440, 480) * (1 - ip(f, 700, 740)) : 0;

  const s24Op    = ip(f, 450, 490);
  const s24Scale = interpolate(f, [450, 490], [0.2, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.8)),
  });
  const s24Pulse = s24Op > 0.9 ? 1 + Math.sin(f * 0.1) * 0.02 : 1;

  const alwaysOp = ip(f, 500, 560);
  const alwaysTy = interpolate(f, [500, 560], [35, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  const doingOp = ip(f, 580, 640);
  const doingTy = interpolate(f, [580, 640], [35, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // ── Phase 3 (f720~1110): "주식 분석 팀을 운영합니다" 클라이맥스 ───
  const ph3Op = ip(f, 720, 760);

  const prefaceOp = ip(f, 730, 790);
  const prefaceTy = interpolate(f, [730, 790], [30, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  const teamOp    = ip(f, 870, 930);
  const teamScale = interpolate(f, [870, 930], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.75)),
  });
  const teamPulse = teamOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.022 : 1;

  // 스캔라인 (f870~910)
  const scanY  = interpolate(f, [870, 910], [-2, 104], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [870, 875, 905, 910], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 배경 강화 (phase 3)
  const bgBoost = ip(f, 720, 870, 0, 0.06);

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s05.m4a')} volume={1} />

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)`,
        opacity: bgGlow + bgBoost, pointerEvents: 'none',
      }} />

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 5 · 클라이맥스</div>

      {/* ── PHASE 1: 타임라인 재등장 ── */}
      {ph1Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph1Op }}>

          {/* 타이틀 */}
          <div style={{
            position: 'absolute', top: 68, left: 0, right: 0,
            textAlign: 'center', opacity: titleOp,
          }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8, marginBottom: 10 }}>
              RECAP
            </div>
            <div style={{ fontSize: 46, fontWeight: 900, color: '#e5e7eb' }}>
              오프닝에서 봤던 이 메시지
            </div>
          </div>

          {/* 수평 타임라인 바 */}
          <div style={{
            position: 'absolute', top: 220, left: 100, right: 100,
            opacity: barOp,
          }}>
            {/* 시간 레이블 */}
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              color: '#4b5563', fontSize: 14, fontWeight: 700, letterSpacing: 2, marginBottom: 12,
            }}>
              {['오후 9시', '밤 11시', '새벽 1시', '새벽 3시', '새벽 5시', '아침 7시', '아침 9시'].map((t, i) => (
                <span key={i}>{t}</span>
              ))}
            </div>

            {/* 베이스 바 */}
            <div style={{
              height: 8, background: '#1a2030', borderRadius: 4, position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', top: 0, left: 0, height: '100%',
                width: `${barW * 100}%`,
                background: `linear-gradient(90deg, rgba(0,255,208,0.2), rgba(0,255,208,0.1))`,
              }} />
            </div>

            {/* 구간 바들 */}
            {ZONES.map((z, i) => {
              const zOp = [zone0Op, zone1Op, zone2Op][i];
              return (
                <div key={i} style={{
                  position: 'absolute',
                  top: i * 70 + 55,
                  left: `${z.from * 100}%`,
                  width: `${(z.to - z.from) * 100}%`,
                  opacity: zOp,
                }}>
                  {/* 컬러 바 */}
                  <div style={{
                    height: 44,
                    background: `${z.col}22`,
                    border: `1.5px solid ${z.col}55`,
                    borderRadius: 8,
                    display: 'flex', alignItems: 'center', gap: 12, paddingInline: 16,
                  }}>
                    <span style={{ fontSize: 22 }}>{z.icon}</span>
                    <div>
                      <div style={{ color: z.col, fontSize: 18, fontWeight: 800 }}>{z.label}</div>
                      <div style={{ color: '#4b5563', fontSize: 13 }}>{z.sublabel}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* "즉시" 텍스트 3회 */}
          {JAMSILS.map((j, i) => {
            const jOp = ip(f, j.f, j.f + 32);
            const jScale = interpolate(f, [j.f, j.f + 32], [0.4, 1], {
              extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
              easing: Easing.out(Easing.elastic(0.9)),
            });
            return (
              <div key={i} style={{
                position: 'absolute',
                bottom: 200 + i * 70,
                right: 120,
                opacity: jOp,
                transform: `scale(${jScale})`,
                transformOrigin: 'right center',
                display: 'flex', alignItems: 'center', gap: 16,
              }}>
                <div style={{ color: '#4b5563', fontSize: 17, fontWeight: 600 }}>{j.label}</div>
                <div style={{
                  color: j.col, fontSize: 42, fontWeight: 900,
                  textShadow: `0 0 16px ${j.col}88`,
                }}>즉시</div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── PHASE 2: "24시간 · 항상 돌아가고 있습니다" ── */}
      {ph2Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph2Op, gap: 28,
        }}>
          {/* "24시간" */}
          <div style={{
            opacity: s24Op,
            transform: `scale(${s24Scale * s24Pulse})`,
            display: 'flex', alignItems: 'baseline', gap: 8,
          }}>
            <div style={{
              fontSize: 150, fontWeight: 900, lineHeight: 1,
              fontFamily: '"Consolas","Menlo",monospace',
              color: C.main, textShadow: dynGlow,
            }}>24</div>
            <div style={{ fontSize: 70, fontWeight: 700, color: '#9ca3af' }}>시간</div>
          </div>

          {/* "내가 뭘 하든 상관없이" */}
          <div style={{
            opacity: alwaysOp,
            transform: `translateY(${alwaysTy}px)`,
            fontSize: 48, fontWeight: 700, color: '#9ca3af', textAlign: 'center',
          }}>내가 뭘 하든 상관없이</div>

          {/* "항상 돌아가고 있습니다" */}
          <div style={{
            opacity: doingOp,
            transform: `translateY(${doingTy}px)`,
            fontSize: 56, fontWeight: 900, color: '#e5e7eb', textAlign: 'center',
            textShadow: '0 2px 16px rgba(0,0,0,0.5)',
          }}>항상 돌아가고 있습니다.</div>
        </div>
      )}

      {/* ── PHASE 3: "주식 분석 팀을 운영합니다" 클라이맥스 ── */}
      {ph3Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph3Op, gap: 22,
        }}>
          {/* 스캔라인 */}
          <div style={{
            position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2,
            background: `linear-gradient(90deg, transparent 0%, ${C.main} 20%, #80FFE8 50%, ${C.main} 80%, transparent 100%)`,
            boxShadow: `0 0 10px rgba(0,255,208,0.9)`,
            opacity: scanOp, zIndex: 10, pointerEvents: 'none',
          }} />

          {/* "저는 이제 주식 분석을 합니다가 아니라" */}
          <div style={{
            opacity: prefaceOp,
            transform: `translateY(${prefaceTy}px)`,
            fontSize: 38, fontWeight: 700, color: '#6b7280', textAlign: 'center',
          }}>저는 이제 주식 분석을 합니다가 아니라</div>

          {/* "주식 분석 팀을 운영합니다" */}
          <div style={{
            opacity: teamOp,
            transform: `scale(${teamScale * teamPulse})`,
            transformOrigin: 'center',
            textAlign: 'center',
            fontSize: 90, fontWeight: 900,
            color: C.main, textShadow: dynGlow,
            lineHeight: 1.2,
          }}>주식 분석 팀을<br />운영합니다.</div>

          {/* 하단 배지 */}
          {teamOp > 0.7 && (
            <div style={{
              opacity: ip(f, 940, 980),
              transform: `scale(${ip(f, 940, 980, 0.7, 1, Easing.out(Easing.back(1.5)))})`,
              display: 'flex', alignItems: 'center', gap: 20,
              padding: '12px 36px',
              background: `${C.main}0d`,
              border: `1px solid ${C.main}30`,
              borderRadius: 24,
              marginTop: 12,
            }}>
              <span style={{ fontSize: 36 }}>👥</span>
              <div style={{ color: '#9ca3af', fontSize: 22, fontWeight: 600 }}>AI 직원 10명 · 월급 ₩0</div>
              <span style={{ fontSize: 36 }}>✅</span>
            </div>
          )}
        </div>
      )}

      {/* 자막바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        paddingInline: 80,
        background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)',
      }}>
        {sub && (
          <div style={{
            color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center',
            opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)',
          }}>{sub.text}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};
