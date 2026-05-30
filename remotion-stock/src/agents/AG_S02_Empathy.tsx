// AG_S02 — 씬2 공감 (979프레임 / 32.62초)
// 스타일: Remotion 가이드 타이포그래피 + 이모지 비주얼 균형
// 자막바 필수 (Whisper 싱크)
//
// Whisper 세그먼트:
// [01] f0000~0094  "주식하시는 분들 매일 아침이 어떠세요?"
// [02] f0116~0187  "탈레방 한 10개 정도 돌아다니고"
// [03] f0187~0284  "증권사, 네이버, 뉴스 찾으러 다니고"
// [04] f0284~0361  "유튜브 시황 찾아다니면서"
// [05] f0388~0412  "다 보시죠?"
// [06] f0428~0520  "이거 다 하고 나면 진짜 9시가 다 되는데"
// [07] f0542~0557  "어휴"
// [08] f0578~0650  "중요한 건 정작 뭘 사야 될지를"
// [09] f0650~0681  "더 모르겠다는 거예요"
// [10] f0715~0754  "저 10년 동안 그랬습니다"
// [11] f0780~0848  "매일 아침, 매일 같은 루틴으로"
// [12] f0848~0979  "근데 결론은 항상 확신이 없고 흐릿했어요"

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

// ── 자막 세그먼트 ─────────────────────────────────────────────────
const SUBS = [
  { s: 0,   e: 94,  text: '주식하시는 분들 매일 아침이 어떠세요?' },
  { s: 116, e: 187, text: '텔레방 10개 정도 돌아다니고' },
  { s: 187, e: 284, text: '증권사, 네이버, 뉴스 찾으러 다니고' },
  { s: 284, e: 361, text: '유튜브 시황 찾아다니면서' },
  { s: 388, e: 412, text: '다 보시죠?' },
  { s: 428, e: 520, text: '이거 다 하고 나면 진짜 9시가 다 되는데' },
  { s: 542, e: 557, text: '어휴…' },
  { s: 578, e: 650, text: '중요한 건 정작 뭘 사야 될지를' },
  { s: 650, e: 681, text: '더 모르겠다는 거예요' },
  { s: 715, e: 754, text: '저 10년 동안 그랬습니다' },
  { s: 780, e: 848, text: '매일 아침, 매일 같은 루틴으로' },
  { s: 848, e: 979, text: '근데 결론은 항상 확신이 없고 흐릿했어요' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return {
    text: seg.text,
    op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8),
  };
}

// ── 배경 파티클 — 작은 이모지들 흘러다님 ─────────────────────────
const BG_PTCL = [
  { icon: '📊', x: 6,  y: 15, sz: 26, spd: 0.020, amp: 16, ph: 0.0 },
  { icon: '📈', x: 90, y: 30, sz: 22, spd: 0.017, amp: 12, ph: 1.4 },
  { icon: '💹', x: 12, y: 70, sz: 28, spd: 0.024, amp: 18, ph: 2.2 },
  { icon: '🔔', x: 85, y: 72, sz: 20, spd: 0.019, amp: 14, ph: 0.7 },
  { icon: '💰', x: 48, y: 8,  sz: 22, spd: 0.015, amp: 10, ph: 3.1 },
];

// ── 루틴 3개 카드 데이터 ─────────────────────────────────────────
const APPS = [
  { icon: '📱', title: '텔레방',     sub: '10개 탭탭탭',      col: '#FFA502', startF: 116 },
  { icon: '📰', title: '증권사·뉴스', sub: '스크롤 스크롤',    col: '#9ca3af', startF: 210 },
  { icon: '▶️', title: '유튜브 시황', sub: '영상 켜기',        col: '#FF4757', startF: 300 },
];

export const AG_S02_Empathy: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const timeOp = ip(f, 10, 28);
  const sub    = getSub(f);

  const bgGlow  = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // ── 페이즈 페이드 ─────────────────────────────────────────────
  const ph1Out = 1 - ip(f, 96,  116);
  const ph2Out = 1 - ip(f, 415, 435);
  const ph3Out = 1 - ip(f, 556, 578);
  const ph4Out = 1 - ip(f, 706, 720);

  // ━━━━ PHASE 1  f0~115  임팩트형 질문 ━━━━━━━━━━━━━━━━━━━━━━━━
  // 스캔라인 (f0~38)
  const scanY  = interpolate(f, [0, 38], [-2, 104], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 라벨 (f18~40)
  const labelOp = ip(f, 18, 40);

  // "주식하시는 분들" — 좌에서 슬라이드 (f22~62)
  const t1X  = interpolate(f, [22, 62], [-160, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = ip(f, 22, 62);
  const t1Ls = interpolate(f, [22, 62], [20, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 🤔 이모지 — 우측에서 elastic 등장 (f30~62)
  const emQ1Scale = interpolate(f, [30, 62], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.0)) });
  const emQ1Op    = ip(f, 30, 60);
  const emQ1Float = Math.sin(f * 0.09) * 8;

  // "매일 아침이 어떠세요?" — 아래서 Y슬라이드 + 민트 (f52~90)
  const t2Y  = interpolate(f, [52, 90], [50, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = ip(f, 52, 90);
  const t2Breathe = t2Op > 0.9 ? Math.sin(f * 0.08) * 0.02 + 1 : 1;

  // ━━━━ PHASE 2  f116~420  루틴 3개 카드 ━━━━━━━━━━━━━━━━━━━━━
  // "다 보시죠?" (f388~412) — 카드 3개 동시 점프
  const jumpAmt = f >= 388 && f <= 416
    ? Math.abs(Math.sin(ip(f, 388, 416) * Math.PI)) * 22
    : 0;

  // ━━━━ PHASE 3  f428~560  "9시" 클라이맥스 ━━━━━━━━━━━━━━━━━━
  const p3TextOp = ip(f, 428, 468);
  const p3TextY  = interpolate(f, [428, 468], [40, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 🕘 이모지 elastic 등장 (f450~490)
  const emClockScale = interpolate(f, [450, 490], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.8)) });
  const emClockOp    = ip(f, 450, 488);
  // 9시 임박 — 진동 강도 증가
  const clockShake = f >= 480
    ? Math.sin(f * 0.3) * interpolate(f, [480, 520], [0, 8], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : 0;
  const clockPulse = f >= 480 ? 1 + Math.sin(f * 0.18) * 0.04 : 1;

  // "9시" 숫자 카운트업 느낌 (f470~520)
  const nineOp    = ip(f, 470, 510);
  const nineScale = interpolate(f, [470, 510], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.75)) });
  const ninePulse = nineOp > 0.95 ? 1 + Math.sin(f * 0.1) * 0.025 : 1;

  // 😮‍💨 어휴 이모지 (f542~557) — 우상단 팡 등장
  const sighOp    = ip(f, 542, 554) * (1 - ip(f, 558, 570));
  const sighScale = interpolate(f, [542, 555], [0.1, 1.2], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.3)) });

  // ━━━━ PHASE 4  f578~710  "뭘 사야 될지" ━━━━━━━━━━━━━━━━━━━━
  // "중요한 건 정작" (f578~615)
  const p4aOp = ip(f, 578, 612);
  const p4aY  = interpolate(f, [578, 612], [35, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ❓ 이모지 — 좌에서 slide (f610~645)
  const emQScale = interpolate(f, [610, 645], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.0)) });
  const emQOp    = ip(f, 610, 645);
  const emQFloat = Math.sin(f * 0.1) * 10;

  // "뭘 사야 될지를" 민트 강조 (f625~665)
  const buyOp    = ip(f, 625, 662);
  const buyScale = interpolate(f, [625, 662], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.9)) });
  const buyPulse = buyOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.022 : 1;

  // "더 모르겠다는 거예요" (f650~685) — 우에서
  const p4bOp = ip(f, 650, 685);
  const p4bX  = interpolate(f, [650, 685], [80, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ━━━━ PHASE 5  f715~979  "10년 / 루틴 / 흐릿" ━━━━━━━━━━━━━
  // 📅 이모지 (f715~750)
  const emCalScale = interpolate(f, [715, 750], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.8)) });
  const emCalOp    = ip(f, 715, 748);
  const emCalFloat = Math.sin(f * 0.07) * 6;

  // "저 10년 동안 그랬습니다" (f720~755) — 위에서 내려옴
  const p5aOp = ip(f, 720, 755);
  const p5aY  = interpolate(f, [720, 755], [-40, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "매일 아침" + "매일 같은 루틴" (f780, f815) — 순차
  const p5b1Op = ip(f, 780, 814);
  const p5b1X  = interpolate(f, [780, 814], [-60, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const p5b2Op = ip(f, 815, 848);
  const p5b2X  = interpolate(f, [815, 848], [60, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "근데 결론은 항상 흐릿했어요" — letterSpacing 넓어지며 흐릿 표현 (f848~979)
  const blurOp = ip(f, 848, 888);
  const blurLs = interpolate(blurOp, [0, 1], [0, 10], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  // 🌫️ 이모지 페이드인 (f875~)
  const fogOp  = ip(f, 875, 920, 0, 0.5);

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 오디오 */}
      <Html5Audio src={staticFile('voice/ag_s02.m4a')} volume={1} />

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 배경 파티클 이모지 — 희미하게 흘러다님 */}
      {BG_PTCL.map((p, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: `${p.x}%`, top: `${p.y}%`,
          fontSize: p.sz, opacity: 0.08,
          transform: `translateY(${Math.sin(f * p.spd + p.ph) * p.amp}px)`,
          pointerEvents: 'none',
        }}>{p.icon}</div>
      ))}

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 2 · 공감</div>

      {/* ━━━━ PHASE 1: 임팩트형 질문 ━━━━ */}
      {ph1Out > 0.01 && f < 120 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph1Out,
        }}>
          {/* 스캔라인 */}
          <div style={{
            position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2,
            background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
            boxShadow: '0 0 10px rgba(0,255,208,0.9)',
            opacity: scanOp, zIndex: 10, pointerEvents: 'none',
          }} />

          {/* 라벨 */}
          <div style={{ opacity: labelOp, color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 8, marginBottom: 20 }}>
            EVERY MORNING
          </div>

          {/* "주식하시는 분들" + 🤔 이모지 나란히 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 32, marginBottom: 16 }}>
            <div style={{
              opacity: t1Op, transform: `translateX(${t1X}px)`,
              fontSize: 96, fontWeight: 900, color: '#e5e7eb',
              letterSpacing: t1Ls,
            }}>주식하시는 분들</div>

            {/* 🤔 — 우측 elastic 등장 */}
            <div style={{
              opacity: emQ1Op,
              transform: `scale(${emQ1Scale}) translateY(${emQ1Float}px)`,
              transformOrigin: 'center',
              fontSize: 90,
            }}>🤔</div>
          </div>

          {/* "매일 아침이 어떠세요?" — 민트, 아래서 */}
          <div style={{
            opacity: t2Op,
            transform: `translateY(${t2Y}px) scale(${t2Breathe})`,
            fontSize: 72, fontWeight: 900,
            color: C.main, textShadow: dynGlow,
          }}>매일 아침이 어떠세요?</div>
        </div>
      )}

      {/* ━━━━ PHASE 2: 루틴 3개 카드 ━━━━ */}
      {f >= 110 && ph2Out > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph2Out }}>

          {/* 상단 작은 라벨 */}
          <div style={{
            position: 'absolute', top: 120, left: 0, right: 0, textAlign: 'center',
            opacity: ip(f, 116, 140) * (1 - ip(f, 370, 400)) * 0.5,
            color: '#6b7280', fontSize: 28, fontWeight: 600,
          }}>매일 아침 루틴</div>

          {/* 카드 3개 */}
          {APPS.map((app, i) => {
            const s       = app.startF;
            const cardOp  = ip(f, s, s + 32);
            const cardTx  = interpolate(f, [s, s + 32], [i % 2 === 0 ? -100 : 100, 0], {
              extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
              easing: Easing.out(Easing.back(1.5)),
            });
            const wobble  = cardOp > 0.9 ? Math.sin(f * (0.065 + i * 0.018) + i * 1.8) * 6 : 0;

            const totalW  = 420 * 3 + 48 * 2;
            const cx      = (1920 - totalW) / 2 + i * (420 + 48);

            // "다 보시죠?" 글로우
            const ringGlow = ip(f, 388, 405) * ip(f, 405, 416);

            return (
              <div key={i} style={{
                position: 'absolute',
                left: cx, top: 260,
                width: 420, height: 380,
                opacity: cardOp,
                transform: `translateX(${cardTx}px) translateY(${wobble - jumpAmt}px)`,
                transformOrigin: 'center bottom',
              }}>
                <div style={{
                  width: '100%', height: '100%',
                  background: 'rgba(255,255,255,0.04)',
                  border: `1.5px solid ${ringGlow > 0.2 ? app.col : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: 28,
                  boxShadow: ringGlow > 0.2 ? `0 0 ${20 * ringGlow}px ${app.col}55` : undefined,
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center', gap: 20,
                  padding: '28px 24px',
                }}>
                  {/* 이모지 — 메인 비주얼 */}
                  <div style={{
                    fontSize: 110,
                    filter: `drop-shadow(0 4px 16px ${app.col}44)`,
                    transform: `scale(${1 + Math.sin(f * 0.05 + i) * 0.018})`,
                  }}>{app.icon}</div>

                  {/* 제목 */}
                  <div style={{
                    fontSize: 32, fontWeight: 800,
                    color: app.col, letterSpacing: 2,
                    textShadow: `0 0 10px ${app.col}66`,
                  }}>{app.title}</div>

                  {/* 서브 */}
                  <div style={{ fontSize: 22, color: '#6b7280' }}>{app.sub}</div>
                </div>
              </div>
            );
          })}

          {/* "다 보시죠?" 하단 텍스트 (f388~416) */}
          {f >= 384 && f <= 420 && (
            <div style={{
              position: 'absolute', bottom: 220, left: 0, right: 0,
              textAlign: 'center',
              opacity: ip(f, 388, 402) * (1 - ip(f, 410, 420)),
              fontSize: 52, fontWeight: 700, color: '#9ca3af',
            }}>다 보시죠?  👇</div>
          )}
        </div>
      )}

      {/* ━━━━ PHASE 3: "9시" 클라이맥스 ━━━━ */}
      {f >= 422 && ph3Out > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph3Out, gap: 28,
        }}>
          {/* "이거 다 하고 나면" */}
          <div style={{
            opacity: p3TextOp,
            transform: `translateY(${p3TextY}px)`,
            fontSize: 50, fontWeight: 700, color: '#9ca3af',
          }}>이거 다 하고 나면</div>

          {/* 🕘 + "9시" 나란히 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 36 }}>
            {/* 🕘 이모지 */}
            <div style={{
              opacity: emClockOp,
              transform: `scale(${emClockScale * clockPulse}) translateX(${clockShake}px)`,
              transformOrigin: 'center',
              fontSize: 110,
              filter: f >= 490 ? `drop-shadow(0 0 ${interpolate(f, [490, 520], [0, 20], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })}px rgba(255,165,0,0.7))` : undefined,
            }}>🕘</div>

            {/* "9시" 대형 숫자 */}
            <div style={{
              opacity: nineOp,
              transform: `scale(${nineScale * ninePulse})`,
              transformOrigin: 'center',
              display: 'flex', alignItems: 'baseline', gap: 10,
            }}>
              <div style={{
                fontSize: 160, fontWeight: 900, lineHeight: 1,
                fontFamily: '"Consolas","Menlo",monospace',
                color: C.main, textShadow: dynGlow,
              }}>9시</div>
              <div style={{ fontSize: 48, fontWeight: 700, color: '#6b7280' }}>가 다 돼요</div>
            </div>
          </div>

          {/* 😮‍💨 "어휴" — 우상단 팡 */}
          {sighOp > 0.01 && (
            <div style={{
              position: 'absolute', right: 180, top: 160,
              opacity: sighOp,
              transform: `scale(${sighScale})`,
              transformOrigin: 'center',
              fontSize: 100,
            }}>😮‍💨</div>
          )}
        </div>
      )}

      {/* ━━━━ PHASE 4: "뭘 사야 될지를 모르겠다" ━━━━ */}
      {f >= 572 && ph4Out > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph4Out, gap: 24,
        }}>
          {/* "중요한 건 정작" */}
          <div style={{
            opacity: p4aOp, transform: `translateY(${p4aY}px)`,
            fontSize: 48, fontWeight: 700, color: '#9ca3af',
          }}>중요한 건 정작...</div>

          {/* ❓ + "뭘 사야 될지를" 나란히 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
            <div style={{
              opacity: emQOp,
              transform: `scale(${emQScale}) translateY(${emQFloat}px)`,
              transformOrigin: 'center',
              fontSize: 100,
            }}>❓</div>

            <div style={{
              opacity: buyOp,
              transform: `scale(${buyScale * buyPulse})`,
              transformOrigin: 'center left',
              padding: '18px 48px',
              background: `${C.main}10`,
              border: `2px solid ${C.main}30`,
              borderRadius: 20,
            }}>
              <div style={{
                fontSize: 72, fontWeight: 900,
                color: C.main, textShadow: dynGlow,
              }}>뭘 사야 될지를</div>
            </div>
          </div>

          {/* "더 모르겠다는 거예요" — 우에서 */}
          <div style={{
            opacity: p4bOp, transform: `translateX(${p4bX}px)`,
            fontSize: 56, fontWeight: 700, color: '#e5e7eb',
          }}>더 모르겠다는 거예요.</div>
        </div>
      )}

      {/* ━━━━ PHASE 5: "10년 / 루틴 / 흐릿했어요" ━━━━ */}
      {f >= 710 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 24,
        }}>
          {/* 📅 + "저 10년 동안 그랬습니다" */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 30 }}>
            <div style={{
              opacity: emCalOp,
              transform: `scale(${emCalScale}) translateY(${emCalFloat}px)`,
              transformOrigin: 'center',
              fontSize: 90,
            }}>📅</div>

            <div style={{
              opacity: p5aOp, transform: `translateY(${p5aY}px)`,
              fontSize: 68, fontWeight: 900, color: '#e5e7eb',
            }}>
              저{' '}
              <span style={{ color: C.main, textShadow: GLOW.mid.text }}>10년</span>
              {' '}동안 그랬습니다.
            </div>
          </div>

          {/* "매일 아침." 좌에서 */}
          <div style={{
            opacity: p5b1Op, transform: `translateX(${p5b1X}px)`,
            fontSize: 52, fontWeight: 700, color: '#9ca3af',
          }}>📆  매일 아침.</div>

          {/* "매일 같은 루틴으로." 우에서 */}
          <div style={{
            opacity: p5b2Op, transform: `translateX(${p5b2X}px)`,
            fontSize: 52, fontWeight: 700, color: '#9ca3af',
          }}>🔄  매일 같은 루틴으로.</div>

          {/* "결론은 항상 흐릿했어요" — letterSpacing 넓어짐 + opacity 낮음 */}
          <div style={{
            opacity: blurOp * 0.6,
            transform: `translateY(${interpolate(f, [848, 880], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })}px)`,
            textAlign: 'center', marginTop: 8,
          }}>
            <div style={{
              fontSize: 56, fontWeight: 900, color: '#e5e7eb',
              letterSpacing: blurLs,
            }}>근데 결론은 항상</div>
            <div style={{
              fontSize: 72, fontWeight: 900, color: '#6b7280',
              letterSpacing: blurLs * 1.5, marginTop: 8,
            }}>흐릿했어요.  🌫️</div>

            {/* 🌫️ 이모지들 양쪽 */}
            {fogOp > 0 && (
              <>
                <div style={{
                  position: 'absolute', left: 160, top: '50%',
                  fontSize: 70, opacity: fogOp,
                  transform: `translateY(${Math.sin(f * 0.04) * 10}px)`,
                }}>🌫️</div>
                <div style={{
                  position: 'absolute', right: 160, top: '50%',
                  fontSize: 70, opacity: fogOp,
                  transform: `translateY(${Math.sin(f * 0.04 + 1.5) * 10}px)`,
                }}>🌫️</div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ━━━━ 자막바 — 항상 하단 16% ━━━━ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        paddingInline: 80,
        background: 'linear-gradient(to top, rgba(8,12,20,0.88) 0%, transparent 100%)',
      }}>
        {sub && (
          <div style={{
            color: '#FFFFFF', fontSize: 40, fontWeight: 700,
            textAlign: 'center', lineHeight: 1.4,
            opacity: sub.op,
            textShadow: '0 2px 8px rgba(0,0,0,0.9)',
          }}>{sub.text}</div>
        )}
      </div>

    </AbsoluteFill>
  );
};
