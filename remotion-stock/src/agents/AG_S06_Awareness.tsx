// AG_S06 — 씬6 자각 (1230프레임 / 41초)
// ※ 녹음 후 Whisper 싱크로 타이밍 조정 필요
// [01] f0000~0090  "매일 아침 텔레방 확인하고"
// [02] f0100~0160  "유튜브 시황 보고"
// [03] f0170~0270  "리포트 읽는 데 얼마나 쓰세요?"
// [04] f0320~0430  "저는 이제 그 시간을 안 씁니다"
// [05] f0440~0530  "직원들이 다 해놨거든요"
// [06] f0560~0680  "그 시간에 저는 커피 한 잔 마시면서"
// [07] f0700~0800  "한 장짜리 브리핑만 봐요"

import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

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
  { s: 0,   e: 90,  text: '매일 아침 텔레방 확인하고' },
  { s: 100, e: 160, text: '유튜브 시황 보고' },
  { s: 170, e: 270, text: '리포트 읽는 데 얼마나 쓰세요?' },
  { s: 320, e: 430, text: '저는 이제 그 시간을 안 씁니다.' },
  { s: 440, e: 530, text: '직원들이 다 해놨거든요.' },
  { s: 560, e: 680, text: '그 시간에 저는 커피 한 잔 마시면서' },
  { s: 700, e: 800, text: '한 장짜리 브리핑만 봐요.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// Phase 1: 기존 루틴 3가지
const OLD_HABITS = [
  { icon: '📱', label: '텔레방', sub: '3~5개 채널 확인', time: '30분', col: '#FF4757' },
  { icon: '📺', label: '유튜브', sub: '시황 영상 2~3개',  time: '20분', col: '#FFA502' },
  { icon: '📄', label: '리포트', sub: '증권사 뉴스 스크롤', time: '40분', col: '#9ca3af' },
];

// Phase 3: 아침 노트 4항목
const BRIEF_ITEMS = [
  { icon: '🌡️', label: '섹터 온도', val: '반도체 🔴',  col: '#FF4757' },
  { icon: '🎯', label: '탑픽',     val: '삼성전기 7/9', col: C.main    },
  { icon: '🌍', label: '매크로',   val: 'VIX 18.2 ↓',  col: '#FFA502' },
  { icon: '📅', label: '오늘 일정', val: 'HLB D-54',    col: '#9ca3af' },
];

export const AG_S06_Awareness: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const timeOp = ip(f, 10, 28);
  const sub    = getSub(f);

  const bgGlow  = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 28]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // ── Phase 1 (f0~300): 기존 루틴 3칸 ────────────────────────────
  const ph1Out = 1 - ip(f, 280, 320);

  // 구 루틴 카드 등장
  const habit0Op = ip(f, 10,  52);
  const habit1Op = ip(f, 100, 142);
  const habit2Op = ip(f, 170, 212);

  // 시간 누적 카운터: 0 → 90분
  const totalMin = Math.round(ip(f, 10, 275, 0, 90));
  const counterOp = ip(f, 10, 50);

  // "❌ 이 루틴이 문제입니다" 등장 (f260~)
  const badgeOp    = ip(f, 255, 285);
  const badgeScale = interpolate(f, [255, 285], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.8)),
  });

  // ── Phase 2 (f280~560): "직원들이 다 해놨거든요" ────────────────
  const ph2Op = f >= 280 ? ip(f, 280, 320) * (1 - ip(f, 530, 570)) : 0;

  const noTimeOp = ip(f, 330, 390);
  const noTimeTy = interpolate(f, [330, 390], [40, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  const doneOp    = ip(f, 450, 510);
  const doneScale = interpolate(f, [450, 510], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.8)),
  });

  // ── Phase 3 (f530~1230): 커피 + 브리핑 ─────────────────────────
  const ph3Op = ip(f, 530, 570);

  const coffeeOp    = ip(f, 560, 610);
  const coffeeScale = interpolate(f, [560, 610], [0.2, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.9)),
  });
  const coffeeFloat = Math.sin(f * 0.06) * 6;

  const briefTitleOp = ip(f, 600, 640);

  // 브리핑 카드 4개 순차 등장
  const briefItemStart = [630, 680, 730, 780];

  // "3분" 텍스트 (f800~)
  const minOp    = ip(f, 800, 850);
  const minScale = interpolate(f, [800, 850], [0.2, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.75)),
  });

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s06.m4a')} volume={1} />

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 6 · 자각</div>

      {/* ── PHASE 1: 기존 루틴 3칸 ── */}
      {ph1Out > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph1Out }}>

          {/* 타이틀 */}
          <div style={{
            position: 'absolute', top: 65, left: 0, right: 0,
            textAlign: 'center', opacity: ip(f, 8, 40),
          }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8, marginBottom: 10 }}>
              BEFORE
            </div>
            <div style={{ fontSize: 42, fontWeight: 900, color: '#e5e7eb' }}>
              매일 아침 이 루틴
            </div>
          </div>

          {/* 루틴 카드 3개 */}
          <div style={{
            position: 'absolute', top: 210, left: 100, right: 100,
            display: 'flex', gap: 32,
          }}>
            {OLD_HABITS.map((h, i) => {
              const opArr = [habit0Op, habit1Op, habit2Op];
              const cardOp = opArr[i];
              const cardTy = interpolate(f, [10 + i * 90, 52 + i * 90], [50, 0], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                easing: Easing.out(Easing.back(1.3)),
              });
              return (
                <div key={i} style={{
                  flex: 1, opacity: cardOp,
                  transform: `translateY(${cardTy}px)`,
                }}>
                  <div style={{
                    padding: '32px 28px',
                    background: 'rgba(255,255,255,0.04)',
                    border: `1.5px solid ${h.col}35`,
                    borderRadius: 20,
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, textAlign: 'center',
                  }}>
                    <span style={{ fontSize: 72, filter: `drop-shadow(0 2px 12px ${h.col}44)` }}>{h.icon}</span>
                    <div style={{ fontSize: 28, fontWeight: 800, color: '#e5e7eb' }}>{h.label}</div>
                    <div style={{ fontSize: 17, color: '#6b7280', lineHeight: 1.5 }}>{h.sub}</div>
                    <div style={{
                      padding: '8px 24px',
                      background: `${h.col}18`, border: `1px solid ${h.col}30`, borderRadius: 16,
                      color: h.col, fontSize: 26, fontWeight: 900,
                    }}>{h.time}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 누적 시간 카운터 */}
          <div style={{
            position: 'absolute', bottom: 210, left: 0, right: 0,
            textAlign: 'center', opacity: counterOp,
          }}>
            <div style={{ color: '#4b5563', fontSize: 17, fontWeight: 600, letterSpacing: 4, marginBottom: 8 }}>
              총 소요 시간
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, justifyContent: 'center' }}>
              <div style={{
                fontSize: 100, fontWeight: 900, lineHeight: 1,
                fontFamily: '"Consolas","Menlo",monospace',
                color: '#FF4757', textShadow: '0 0 20px rgba(255,71,87,0.5)',
              }}>{String(totalMin).padStart(2, '0')}</div>
              <div style={{ fontSize: 46, fontWeight: 700, color: '#9ca3af' }}>분</div>
            </div>
          </div>

          {/* "이게 문제입니다" 뱃지 */}
          {badgeOp > 0.01 && (
            <div style={{
              position: 'absolute', bottom: 155, left: 0, right: 0,
              textAlign: 'center', opacity: badgeOp,
              transform: `scale(${badgeScale})`,
            }}>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 14,
                padding: '8px 32px',
                background: 'rgba(255,71,87,0.12)', border: '1.5px solid rgba(255,71,87,0.35)',
                borderRadius: 32, color: '#FF4757', fontSize: 22, fontWeight: 700,
              }}>
                <span>❌</span> 정작 뭘 사야 할지 더 모르겠어요
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── PHASE 2: "저는 이제 그 시간을 안 씁니다" ── */}
      {ph2Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph2Op, gap: 36,
        }}>
          {/* "저는 이제 그 시간을 안 씁니다" */}
          <div style={{
            opacity: noTimeOp,
            transform: `translateY(${noTimeTy}px)`,
            textAlign: 'center',
          }}>
            <div style={{ color: '#4b5563', fontSize: 22, fontWeight: 700, letterSpacing: 6, marginBottom: 14 }}>
              NOW
            </div>
            <div style={{ fontSize: 58, fontWeight: 900, color: '#e5e7eb' }}>
              저는 이제 그 시간을 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>안 씁니다.</span>
            </div>
          </div>

          {/* "직원들이 다 해놨거든요" */}
          {doneOp > 0.01 && (
            <div style={{
              opacity: doneOp,
              transform: `scale(${doneScale})`,
              transformOrigin: 'center',
              display: 'flex', alignItems: 'center', gap: 24,
              padding: '18px 52px',
              background: `${C.main}0d`,
              border: `1.5px solid ${C.main}38`,
              borderRadius: 28,
            }}>
              <span style={{
                fontSize: 60,
                filter: `drop-shadow(0 2px 14px ${C.main}55)`,
              }}>✅</span>
              <div style={{
                fontSize: 48, fontWeight: 900,
                color: C.main, textShadow: dynGlow,
              }}>직원들이 다 해놨거든요.</div>
            </div>
          )}
        </div>
      )}

      {/* ── PHASE 3: 커피 + 브리핑 ── */}
      {ph3Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph3Op }}>

          {/* 왼쪽: 커피 */}
          <div style={{
            position: 'absolute', left: 100, top: 0, bottom: 0,
            width: 400,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            opacity: coffeeOp,
            transform: `scale(${coffeeScale}) translateY(${coffeeFloat}px)`,
          }}>
            <div style={{ fontSize: 130, filter: 'drop-shadow(0 4px 24px rgba(100,200,255,0.3))' }}>☕</div>
            <div style={{
              marginTop: 20, color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 4, textAlign: 'center',
            }}>커피 한 잔</div>
            <div style={{ color: C.main, fontSize: 36, fontWeight: 900, textShadow: GLOW.weak.text, marginTop: 6 }}>3분</div>
          </div>

          {/* 오른쪽: 브리핑 카드 */}
          <div style={{
            position: 'absolute', right: 100, top: 0, bottom: 0,
            width: 780,
            display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 18,
          }}>
            {/* 브리핑 타이틀 */}
            <div style={{
              opacity: briefTitleOp,
              display: 'flex', alignItems: 'center', gap: 16, marginBottom: 6,
            }}>
              <div style={{ color: '#4b5563', fontSize: 15, fontWeight: 700, letterSpacing: 6 }}>
                MORNING BRIEF
              </div>
              <div style={{
                padding: '3px 14px',
                background: `${C.main}18`, border: `1px solid ${C.main}30`, borderRadius: 12,
                color: C.main, fontSize: 14, fontWeight: 700,
              }}>한 장짜리</div>
            </div>

            {/* 브리핑 4항목 */}
            {BRIEF_ITEMS.map((item, i) => {
              const s = briefItemStart[i];
              const itemOp = ip(f, s, s + 35);
              const itemTx = interpolate(f, [s, s + 35], [40, 0], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                easing: Easing.out(Easing.back(1.3)),
              });
              return (
                <div key={i} style={{
                  opacity: itemOp,
                  transform: `translateX(${itemTx}px)`,
                  padding: '16px 24px',
                  background: 'rgba(255,255,255,0.04)',
                  border: `1.5px solid ${item.col}28`,
                  borderRadius: 16,
                  display: 'flex', alignItems: 'center', gap: 20,
                }}>
                  <span style={{ fontSize: 32 }}>{item.icon}</span>
                  <div style={{ color: '#9ca3af', fontSize: 17, fontWeight: 600, flex: 1 }}>{item.label}</div>
                  <div style={{
                    color: item.col, fontSize: 22, fontWeight: 800,
                    textShadow: `0 0 10px ${item.col}66`,
                  }}>{item.val}</div>
                </div>
              );
            })}

            {/* "3분이면 됩니다" */}
            {minOp > 0.01 && (
              <div style={{
                marginTop: 8,
                opacity: minOp,
                transform: `scale(${minScale})`,
                transformOrigin: 'left center',
                display: 'flex', alignItems: 'center', gap: 16,
                padding: '12px 28px',
                background: `${C.main}0a`,
                border: `1.5px solid ${C.main}30`,
                borderRadius: 20,
              }}>
                <span style={{ fontSize: 28 }}>⏱️</span>
                <div style={{
                  color: C.main, fontSize: 28, fontWeight: 900,
                  textShadow: dynGlow,
                }}>이 시간이면 됩니다.</div>
              </div>
            )}
          </div>
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
