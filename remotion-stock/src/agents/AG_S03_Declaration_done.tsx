// AG_S03 — 씬3 선언 (532프레임 / 17.74초)
// 스타일: 이모지(40%) + 텍스트(60%) 혼합 / 자막바 필수
//
// Whisper 세그먼트:
// [01] f0000~0069  "그래서 저는 직원을 고용했습니다."
// [02] f0095~0134  "AI 직원 10명인데요."
// [03] f0158~0220  "이게 각자 역할이 딱딱 정해져 있어요."
// [04] f0241~0418  "자료수집과 분석, 수급 체크, 탑픽 선정, 브리핑, 배포까지."
// [05] f0435~0532  "저는 7시에 일어나서 결과만 봅니다."

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
  { s: 0,   e: 69,  text: '그래서 저는 직원을 고용했습니다.' },
  { s: 95,  e: 134, text: 'AI 직원 10명인데요.' },
  { s: 158, e: 220, text: '이게 각자 역할이 딱딱 정해져 있어요.' },
  { s: 241, e: 418, text: '수집·분석·수급 체크·탑픽 선정·브리핑·배포까지.' },
  { s: 435, e: 532, text: '저는 7시에 일어나서 결과만 봅니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// ── 직원 10명 데이터 ──────────────────────────────────────────────
const WORKERS = [
  { icon: '📡', name: '수집',   role: '24시간 뉴스·리포트',    col: C.main    },
  { icon: '🇺🇸', name: '미국장', role: '나스닥·SOX 추적',       col: '#FFA502' },
  { icon: '📄', name: '리포트', role: '증권사 자동 분류',       col: '#9ca3af' },
  { icon: '🔍', name: '수급',   role: '500종목 빈집 스캔',      col: C.main    },
  { icon: '⚠️', name: '투경',   role: '투자경고 모니터링',      col: '#FFA502' },
  { icon: '📊', name: '분석',   role: '8개 기준 교차',          col: C.main    },
  { icon: '🎯', name: '탑픽',   role: '탑픽 자동 선정',         col: '#FF4757' },
  { icon: '📋', name: '브리핑', role: '아침 노트 생성',          col: C.main    },
  { icon: '✅', name: '검증',   role: '팩트체크',               col: '#9ca3af' },
  { icon: '📨', name: '배포',   role: '텔레그램 전송',           col: C.main    },
];

// 직원 등장 — f241~418 사이에 10명 균등 배분 (17.8프레임 간격)
const WORKER_START = WORKERS.map((_, i) => Math.round(241 + i * 17.8));

// 카드 레이아웃 (2열 × 5행)
const PAD_X  = 80;
const COLS   = 2;
const ROWS   = 5;
const COL_GAP = 36;
const BOSS_H  = 100;
const BOSS_Y  = 52;
const BOSS_W  = 640;
const GRID_Y  = BOSS_Y + BOSS_H + 28;
const GRID_H  = 1080 - GRID_Y - 165;  // 하단 자막바 + 여백
const CARD_W  = (1920 - PAD_X * 2 - COL_GAP) / COLS;
const CARD_H  = (GRID_H - (ROWS - 1) * 10) / ROWS;
const ROW_GAP = 10;

export const AG_S03_Declaration: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const timeOp = ip(f, 10, 28);
  const sub    = getSub(f);

  const bgGlow  = Math.sin(f * 0.04) * 0.028 + 0.05;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // ━━━━ Phase 1  f0~94  "직원을 고용했습니다" ━━━━━━━━━━━━━━━━━━

  // 스캔라인 (f0~38)
  const scanY  = interpolate(f, [0, 38], [-2, 104], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 💼 이모지 elastic (f8~40)
  const em1Scale = interpolate(f, [8, 40], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.0)) });
  const em1Op    = ip(f, 8, 38);
  const em1Float = Math.sin(f * 0.09) * 7;

  // "그래서 저는" 라벨 (f20~48)
  const labelOp = ip(f, 20, 48);

  // "직원을 고용했습니다" — X슬라이드 (f30~68)
  const t1X  = interpolate(f, [30, 68], [-140, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = ip(f, 30, 68);
  const t1Ls = interpolate(f, [30, 68], [16, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Phase1 페이드아웃 (f72~95)
  const ph1Out = 1 - ip(f, 72, 95);

  // ━━━━ Phase 2  f95~240  "AI 직원 10명 + 각자 역할" ━━━━━━━━━━

  // "AI 직원" 라벨 (f100~128)
  const aiLabelOp = ip(f, 100, 128);

  // "10명" 숫자 카운트업 elastic (f108~145)
  const tenOp    = ip(f, 108, 140);
  const tenScale = interpolate(f, [108, 145], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.8)) });
  const tenPulse = tenOp > 0.9 ? 1 + Math.sin(f * 0.1) * 0.025 : 1;

  // 👥 이모지 (f120~155)
  const em2Scale = interpolate(f, [120, 155], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.0)) });
  const em2Op    = ip(f, 120, 152);

  // "각자 역할이 딱딱 정해져 있어요" — Y슬라이드 (f162~210)
  const t3Y  = interpolate(f, [162, 210], [45, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t3Op = ip(f, 162, 210);

  // Phase2 페이드아웃 (f228~241)
  const ph2Out = 1 - ip(f, 228, 241);

  // ━━━━ Phase 3  f241~430  직원 10명 순차 등장 (org chart) ━━━━━

  // 보스 카드 등장 (f158~195) — phase2와 겹쳐서 자연스럽게
  const bossOp    = ip(f, 158, 195);
  const bossScale = interpolate(f, [158, 195], [0.3, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2.2)) });
  const bossPulse = Math.sin(f * 0.07) * 0.5 + 0.5;

  // 연결선 draw-on (f205~241)
  const lineProg = ip(f, 205, 245);

  // ━━━━ Phase 4  f435~532  "결과만 봅니다" 클라이맥스 ━━━━━━━━━

  // ☀️ 이모지 elastic (f438~470)
  const emSunScale = interpolate(f, [438, 470], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.9)) });
  const emSunOp    = ip(f, 438, 468);

  // "7시에 일어나서" (f442~480)
  const p4aOp = ip(f, 442, 478);
  const p4aY  = interpolate(f, [442, 478], [35, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // "결과만 봅니다" — 클라이맥스 민트 (f470~515)
  const resultOp    = ip(f, 470, 510);
  const resultScale = interpolate(f, [470, 510], [0.4, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.75)) });
  const resultPulse = resultOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.025 : 1;

  // ₩0 클라이맥스 (f490~532)
  const wOp    = ip(f, 490, 525);
  const wScale = interpolate(f, [490, 525], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.65)) });
  const wPulse = wOp > 0.97 ? 1 + Math.sin(f * 0.1) * 0.03 : 1;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 오디오 */}
      <Html5Audio src={staticFile('voice/ag_s03.m4a')} volume={1} />

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
      }}>SCENE 3 · 선언</div>

      {/* ━━━━ PHASE 1: "직원을 고용했습니다" ━━━━ */}
      {ph1Out > 0.01 && f < 96 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph1Out, gap: 20,
        }}>
          {/* 스캔라인 */}
          <div style={{
            position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2,
            background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
            boxShadow: '0 0 10px rgba(0,255,208,0.9)',
            opacity: scanOp, zIndex: 10, pointerEvents: 'none',
          }} />

          {/* 라벨 */}
          <div style={{ opacity: labelOp, color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 8 }}>
            SOLUTION
          </div>

          {/* 💼 + 텍스트 나란히 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 36 }}>
            <div style={{
              opacity: em1Op,
              transform: `scale(${em1Scale}) translateY(${em1Float}px)`,
              fontSize: 100,
            }}>💼</div>

            <div style={{
              opacity: t1Op,
              transform: `translateX(${t1X}px)`,
              fontSize: 88, fontWeight: 900, color: '#e5e7eb',
              letterSpacing: t1Ls,
            }}>직원을 고용했습니다.</div>
          </div>
        </div>
      )}

      {/* ━━━━ PHASE 2: "AI 직원 10명 + 각자 역할" ━━━━ */}
      {f >= 90 && ph2Out > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: ph2Out, gap: 24,
        }}>
          {/* 라벨 */}
          <div style={{
            opacity: aiLabelOp,
            color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 8,
          }}>INTRODUCING</div>

          {/* 👥 + "AI 직원" + "10명" */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
            <div style={{
              opacity: em2Op,
              transform: `scale(${em2Scale})`,
              fontSize: 88,
              filter: `drop-shadow(0 4px 20px rgba(0,255,208,0.5))`,
            }}>👥</div>

            <div>
              <div style={{
                opacity: aiLabelOp,
                fontSize: 40, fontWeight: 700, color: '#9ca3af', marginBottom: 8,
              }}>AI 직원</div>
              <div style={{
                opacity: tenOp,
                transform: `scale(${tenScale * tenPulse})`,
                transformOrigin: 'left center',
                display: 'flex', alignItems: 'baseline', gap: 12,
              }}>
                <span style={{
                  fontSize: 130, fontWeight: 900, lineHeight: 1,
                  fontFamily: '"Consolas","Menlo",monospace',
                  color: C.main, textShadow: dynGlow,
                }}>10</span>
                <span style={{ fontSize: 56, fontWeight: 700, color: '#9ca3af' }}>명</span>
              </div>
            </div>
          </div>

          {/* "각자 역할이 딱딱 정해져 있어요" */}
          <div style={{
            opacity: t3Op,
            transform: `translateY(${t3Y}px)`,
            fontSize: 48, fontWeight: 700, color: '#9ca3af', textAlign: 'center',
          }}>이게 각자 역할이 딱딱 정해져 있어요.</div>
        </div>
      )}

      {/* ━━━━ PHASE 3: Org Chart (f158~430) ━━━━ */}
      {f >= 152 && f < 436 && (
        <div style={{ position: 'absolute', inset: 0 }}>

          {/* SVG 연결선 */}
          <svg style={{ position: 'absolute', inset: 0, width: 1920, height: 1080, pointerEvents: 'none' }}>
            {WORKERS.map((_, i) => {
              const col = i % COLS;
              const row = Math.floor(i / COLS);
              const wx  = PAD_X + col * (CARD_W + COL_GAP) + CARD_W / 2;
              const wy  = GRID_Y + row * (CARD_H + ROW_GAP) + CARD_H / 2;
              const r   = Math.min(1, lineProg);
              return (
                <line key={i}
                  x1={960} y1={BOSS_Y + BOSS_H}
                  x2={960 + (wx - 960) * r} y2={(BOSS_Y + BOSS_H) + (wy - (BOSS_Y + BOSS_H)) * r}
                  stroke="rgba(0,255,208,0.12)"
                  strokeWidth={1.5}
                  strokeDasharray="9 6"
                />
              );
            })}
          </svg>

          {/* 보스 카드 */}
          <div style={{
            position: 'absolute',
            left: 960 - BOSS_W / 2, top: BOSS_Y,
            width: BOSS_W, height: BOSS_H,
            opacity: bossOp,
            transform: `scale(${bossScale})`,
            transformOrigin: 'center center',
          }}>
            <div style={{
              width: '100%', height: '100%',
              background: `rgba(0,255,208,${0.07 + bossPulse * 0.04})`,
              border: `2px solid ${C.main}`,
              borderRadius: 20,
              display: 'flex', alignItems: 'center', gap: 20, padding: '0 28px',
              boxShadow: `0 0 ${28 + bossPulse * 22}px rgba(0,255,208,${0.4 + bossPulse * 0.18})`,
            }}>
              <div style={{
                width: 54, height: 54, borderRadius: 14,
                background: C.main,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 28, flexShrink: 0,
              }}>🧠</div>
              <div style={{ flex: 1 }}>
                <div style={{
                  color: C.main, fontSize: 30, fontWeight: 900, letterSpacing: 5,
                  textShadow: GLOW.mid.text,
                }}>총괄</div>
                <div style={{ color: '#6b7280', fontSize: 15, marginTop: 3 }}>
                  지시 · 취합 · 조율
                </div>
              </div>
              <div style={{
                color: '#4b5563', fontSize: 12, fontWeight: 700, letterSpacing: 2,
                padding: '5px 14px', borderRadius: 8,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
              }}>ORCHESTRATOR</div>
            </div>
          </div>

          {/* 직원 카드 10개 (f241~418 순차 등장) */}
          {WORKERS.map((w, i) => {
            const s        = WORKER_START[i];
            const workerOp = ip(f, s, s + 20);
            const workerTy = interpolate(f, [s, s + 20], [28, 0], {
              extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
              easing: Easing.out(Easing.back(1.4)),
            });
            const col = i % COLS;
            const row = Math.floor(i / COLS);
            const x   = PAD_X + col * (CARD_W + COL_GAP);
            const y   = GRID_Y + row * (CARD_H + ROW_GAP);

            return (
              <div key={i} style={{
                position: 'absolute',
                left: x, top: y, width: CARD_W, height: CARD_H,
                opacity: workerOp,
                transform: `translateY(${workerTy}px)`,
              }}>
                <div style={{
                  width: '100%', height: '100%',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 16,
                  display: 'flex', alignItems: 'center', gap: 18, padding: '0 24px',
                }}>
                  {/* 이모지 아이콘 박스 */}
                  <div style={{
                    width: 52, height: 52, borderRadius: 12,
                    background: `${w.col}18`,
                    border: `1px solid ${w.col}30`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 26, flexShrink: 0,
                  }}>{w.icon}</div>

                  {/* 텍스트 */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#e5e7eb', marginBottom: 4 }}>
                      {w.name} 직원
                    </div>
                    <div style={{ fontSize: 15, color: '#4b5563' }}>{w.role}</div>
                  </div>

                  {/* 상태 점 */}
                  <div style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: w.col, flexShrink: 0,
                    boxShadow: `0 0 6px ${w.col}88`,
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ━━━━ PHASE 4: "결과만 봅니다" 클라이맥스 ━━━━ */}
      {f >= 432 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 28,
        }}>
          {/* ☀️ + "7시에 일어나서" */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
            <div style={{
              opacity: emSunOp,
              transform: `scale(${emSunScale})`,
              fontSize: 90,
              filter: `drop-shadow(0 0 ${20 * emSunOp}px rgba(255,200,0,0.7))`,
            }}>☀️</div>
            <div style={{
              opacity: p4aOp,
              transform: `translateY(${p4aY}px)`,
              fontSize: 52, fontWeight: 700, color: '#9ca3af',
            }}>7시에 일어나서</div>
          </div>

          {/* "결과만 봅니다" — 클라이맥스 민트 */}
          <div style={{
            opacity: resultOp,
            transform: `scale(${resultScale * resultPulse})`,
            transformOrigin: 'center',
            fontSize: 100, fontWeight: 900,
            color: C.main, textShadow: dynGlow,
          }}>결과만 봅니다.</div>

          {/* ₩0 클라이맥스 */}
          <div style={{
            opacity: wOp,
            transform: `scale(${wScale * wPulse})`,
            transformOrigin: 'center bottom',
            textAlign: 'center', marginTop: 8,
          }}>
            <div style={{
              color: '#6b7280', fontSize: 22, fontWeight: 600,
              letterSpacing: 8, marginBottom: 6,
            }}>퇴근 없음 · 불평 없음 · 인건비</div>
            <div style={{
              fontSize: 120, fontWeight: 900, lineHeight: 1,
              fontFamily: '"Consolas","Menlo",monospace',
              color: C.main, textShadow: GLOW.strong.text,
              letterSpacing: 4,
            }}>₩0</div>
          </div>
        </div>
      )}

      {/* ━━━━ 자막바 ━━━━ */}
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
