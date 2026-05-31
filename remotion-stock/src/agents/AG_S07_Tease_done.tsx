// AG_S07 — 씬7 여운 (548프레임 / 18.3초) — Whisper 싱크 완료 + 리디자인
// [01] f0000~0039  "이 시스템."
// [02] f0039~0096  "어떻게 설계됐는지 궁금하시죠?"
// [03] f0121~0218  "총괄이 직원들한테 어떻게 메시지를 내리는지."
// [04] f0236~0357  "직원들이 서로 어떻게 정보를 넘기는지."
// [05] f0357~0417  "실제 설계 구조."
// [06] f0417~0518  "다음 영상에서 전부 보여드리겠습니다."

import React from 'react';
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
  { s: 0,   e: 39,  text: '이 시스템.' },
  { s: 39,  e: 96,  text: '어떻게 설계됐는지 궁금하시죠?' },
  { s: 121, e: 218, text: '총괄이 직원들한테 어떻게 메시지를 내리는지.' },
  { s: 236, e: 357, text: '직원들이 서로 어떻게 정보를 넘기는지.' },
  { s: 357, e: 417, text: '실제 설계 구조.' },
  { s: 417, e: 518, text: '다음 영상에서 전부 보여드리겠습니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// 잠금 예고 카드 2개
const LOCK_CARDS = [
  {
    icon: '🧠→👥',
    title: '총괄이 직원들에게',
    sub: '어떻게 지시를 내리는가',
    startF: 121,
    col: '#FFA502',
  },
  {
    icon: '👥↔️👥',
    title: '직원들이 서로',
    sub: '어떻게 정보를 넘기는가',
    startF: 236,
    col: C.main,
  },
];

export const AG_S07_Tease: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const timeOp = ip(f, 10, 28);
  const sub    = getSub(f);

  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.035;
  const pulse  = Math.sin(f * 0.06) * 0.5 + 0.5;
  const gSz    = interpolate(pulse, [0, 1], [8, 24]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.4)`;

  // ── Phase 1 (f0~120): "이 시스템. 어떻게 설계됐는지 궁금하시죠?" ──
  const ph1Op = 1 - ip(f, 105, 130);

  const qMarkOp    = ip(f, 5, 35);
  const qMarkScale = interpolate(f, [5, 35], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.85)),
  });
  const qMarkFloat = Math.sin(f * 0.08) * 8;

  const titleOp = ip(f, 30, 60);
  const titleTy = interpolate(f, [30, 60], [30, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // ── Phase 2 (f121~360): 잠금 카드 2개 ────────────────────────────
  const ph2Op = f >= 110 ? ip(f, 110, 140) * (1 - ip(f, 345, 375)) : 0;

  // ── Phase 3 (f357~548): 실제 설계 구조 + 다음 영상 예고 ──────────
  const ph3Op = ip(f, 350, 385);

  const designOp    = ip(f, 357, 400);
  const designScale = interpolate(f, [357, 400], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.8)),
  });

  const nextOp = ip(f, 417, 455);
  const nextTy = interpolate(f, [417, 455], [30, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  const badgeOp    = ip(f, 455, 490);
  const badgeScale = interpolate(f, [455, 490], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.75)),
  });
  const badgePulse = badgeOp > 0.95 ? 1 + Math.sin(f * 0.12) * 0.025 : 1;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s07.m4a')} volume={1} />

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
      }}>SCENE 7 · 여운</div>

      {/* ── PHASE 1: 이 시스템. 궁금하시죠? ── */}
      {ph1Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: ph1Op,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 36,
        }}>
          {/* 물음표 이모지 */}
          <div style={{
            fontSize: 120,
            opacity: qMarkOp,
            transform: `scale(${qMarkScale}) translateY(${qMarkFloat}px)`,
            filter: `drop-shadow(0 0 24px ${C.main}66)`,
          }}>🤔</div>

          {/* "이 시스템, 어떻게 설계됐을까요?" */}
          <div style={{
            textAlign: 'center',
            opacity: titleOp,
            transform: `translateY(${titleTy}px)`,
          }}>
            <div style={{ color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 6, marginBottom: 16 }}>
              궁금하시죠?
            </div>
            <div style={{ fontSize: 52, fontWeight: 900, color: '#e5e7eb' }}>
              이 시스템,{' '}
              <span style={{ color: C.main, textShadow: dynGlow }}>어떻게</span>
              {' '}설계됐는지.
            </div>
          </div>
        </div>
      )}

      {/* ── PHASE 2: 잠금 예고 카드 2개 ── */}
      {ph2Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: ph2Op,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 40,
        }}>
          <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8 }}>
            NEXT EPISODE PREVIEW
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 28, width: 900 }}>
            {LOCK_CARDS.map((card, i) => {
              const cardOp = ip(f, card.startF, card.startF + 35);
              const cardTx = interpolate(f, [card.startF, card.startF + 35], [-60, 0], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                easing: Easing.out(Easing.back(1.2)),
              });
              return (
                <div key={i} style={{
                  opacity: cardOp,
                  transform: `translateX(${cardTx}px)`,
                  padding: '28px 40px',
                  background: 'rgba(255,255,255,0.04)',
                  border: `1.5px solid ${card.col}30`,
                  borderRadius: 20,
                  display: 'flex', alignItems: 'center', gap: 32,
                }}>
                  {/* 잠금 아이콘 */}
                  <div style={{
                    width: 72, height: 72, borderRadius: '50%',
                    background: `${card.col}15`,
                    border: `2px solid ${card.col}40`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 30, flexShrink: 0,
                    boxShadow: `0 0 20px ${card.col}30`,
                  }}>🔒</div>

                  <div style={{ flex: 1 }}>
                    <div style={{ color: card.col, fontSize: 14, fontWeight: 700, letterSpacing: 4, marginBottom: 8 }}>
                      Q{i + 1}
                    </div>
                    <div style={{ color: '#e5e7eb', fontSize: 30, fontWeight: 800 }}>{card.title}</div>
                    <div style={{ color: '#6b7280', fontSize: 20, marginTop: 6 }}>{card.sub}</div>
                  </div>

                  {/* 블러 처리된 힌트 */}
                  <div style={{
                    color: '#4b5563', fontSize: 18, fontWeight: 600,
                    filter: 'blur(6px)', userSelect: 'none',
                  }}>다음 편에서 공개</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── PHASE 3: 실제 설계 구조 + 다음 영상 예고 ── */}
      {ph3Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: ph3Op,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 48,
        }}>
          {/* "실제 설계 구조" */}
          {designOp > 0.01 && (
            <div style={{
              textAlign: 'center',
              opacity: designOp,
              transform: `scale(${designScale})`,
            }}>
              <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8, marginBottom: 14 }}>
                COMING NEXT
              </div>
              <div style={{ fontSize: 62, fontWeight: 900, color: '#e5e7eb' }}>
                실제{' '}
                <span style={{ color: C.main, textShadow: dynGlow }}>설계 구조</span>
                .
              </div>
            </div>
          )}

          {/* "다음 영상에서 전부 보여드리겠습니다" */}
          {nextOp > 0.01 && (
            <div style={{
              opacity: nextOp,
              transform: `translateY(${nextTy}px)`,
              color: '#9ca3af', fontSize: 32, fontWeight: 700, textAlign: 'center',
            }}>
              다음 영상에서 전부 보여드리겠습니다.
            </div>
          )}

          {/* 예고 뱃지 */}
          {badgeOp > 0.01 && (
            <div style={{
              opacity: badgeOp,
              transform: `scale(${badgeScale * badgePulse})`,
              display: 'inline-flex', alignItems: 'center', gap: 20,
              padding: '14px 48px',
              background: `${C.main}0d`,
              border: `1.5px solid ${C.main}38`,
              borderRadius: 36,
            }}>
              <span style={{ fontSize: 36 }}>🔓</span>
              <div style={{
                color: C.main, fontSize: 30, fontWeight: 900,
                textShadow: dynGlow, letterSpacing: 2,
              }}>다음 편 : 실제 설계 공개</div>
              <span style={{ fontSize: 36 }}>→</span>
            </div>
          )}
        </div>
      )}

      {/* 자막바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80,
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
