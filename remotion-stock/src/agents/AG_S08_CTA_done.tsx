// AG_S08 — 씬8 CTA (562프레임 / 18.7초) — Whisper 싱크 완료
// [01] f0000~0093  "댓글로 응원 많이 남겨주시고"
// [02] f0093~0187  "다음 영상에서 댓글 남겨주신 분들에게"
// [03] f0187~0283  "이 시스템 구성 정리본 보내드릴게요."
// [04] f0303~0382  "그리고 이 분석, 저만 보기 아깝거든요."
// [05] f0403~0446  "조만간 빨리 오픈해 드릴게요."
// [06] f0446~0532  "STOCK BRAIN 알림 신청해주세요."

import React from 'react';
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
  { s: 0,   e: 93,  text: '댓글로 응원 많이 남겨주시고' },
  { s: 93,  e: 187, text: '다음 영상에서 댓글 남겨주신 분들에게' },
  { s: 187, e: 283, text: '이 시스템 구성 정리본 보내드릴게요.' },
  { s: 303, e: 382, text: '그리고 이 분석, 저만 보기 아깝거든요.' },
  { s: 403, e: 446, text: '조만간 빨리 오픈해 드릴게요.' },
  { s: 446, e: 532, text: 'STOCK BRAIN 알림 신청해주세요.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

const RESOURCE_ITEMS = [
  { icon: '📐', text: '시스템 설계 다이어그램' },
  { icon: '✅', text: '직원 역할 체크리스트' },
  { icon: '⚙️', text: 'Claude Code 설정 예시' },
  { icon: '🔄', text: '자동화 스크립트 구조' },
];

export const AG_S08_CTA: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 18);
  const timeOp = ip(f, 10, 28);
  const sub    = getSub(f);

  const bgGlow  = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [12, 34]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // ── Phase 1 (f0~295): 응원 댓글 CTA + 정리본 증정 ──────────────
  const ph1Op = ip(f, 0, 18) * (1 - ip(f, 280, 305));

  const titleOp = ip(f, 8, 40);
  const commentOp = ip(f, 20, 55);
  const commentTy = interpolate(f, [20, 55], [40, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.5)),
  });

  // 하트/응원 이모지 (f0~93)
  const heartOp = ip(f, 10, 45);

  // "다음 영상 댓글 남겨주신 분들에게" 텍스트 (f93~)
  const nextCommentOp = ip(f, 93, 130);

  // 정리본 카드 (f187~)
  const giftOp    = ip(f, 187, 225);
  const giftScale = interpolate(f, [187, 225], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.85)),
  });
  const itemStarts = [220, 238, 254, 268];

  // ── Phase 2 (f295~455): 아깝더라고요 + 오픈 ────────────────────
  const ph2Op = f >= 295
    ? ip(f, 295, 320) * (1 - ip(f, 435, 455))
    : 0;

  const regretOp = ip(f, 303, 340);
  const regretTy = interpolate(f, [303, 340], [35, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const openOp = ip(f, 410, 445);
  const openTy = interpolate(f, [410, 445], [35, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // ── Phase 3 (f446~562): STOCK BRAIN ────────────────────────────
  const ph3Op = ip(f, 446, 475);

  const logoOp    = ip(f, 450, 490);
  const logoScale = interpolate(f, [450, 490], [0.2, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.75)),
  });
  const logoPulse = logoOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.022 : 1;

  const bellOp    = ip(f, 490, 520);
  const bellScale = interpolate(f, [490, 520], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.8)),
  });
  const bellShake = f >= 520 && f < 548 ? Math.sin(f * 0.2) * (f - 520) * 0.15 : 0;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s08.m4a')} volume={1} />

      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 8 · CTA</div>

      {/* ── PHASE 1: 응원 댓글 + 정리본 증정 ── */}
      {ph1Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph1Op }}>
          {/* 타이틀 */}
          <div style={{
            position: 'absolute', top: 65, left: 0, right: 0,
            textAlign: 'center', opacity: titleOp,
          }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8, marginBottom: 10 }}>FOR YOU</div>
            <div style={{ fontSize: 46, fontWeight: 900, color: '#e5e7eb' }}>댓글로 응원 남겨주시면</div>
          </div>

          {/* 댓글창 */}
          <div style={{
            position: 'absolute', top: 225, left: '50%',
            transform: `translate(-50%, ${commentTy}px)`,
            width: 860, opacity: commentOp,
          }}>
            <div style={{
              padding: '24px 32px',
              background: 'rgba(255,255,255,0.04)',
              border: `2px solid ${C.main}45`, borderRadius: 20,
              display: 'flex', alignItems: 'center', gap: 20,
            }}>
              <div style={{
                width: 52, height: 52, borderRadius: '50%',
                background: `${C.main}22`, border: `2px solid ${C.main}40`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 24, flexShrink: 0,
              }}>👤</div>
              <div style={{ flex: 1 }}>
                {/* 응원 이모지들 */}
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', opacity: heartOp }}>
                  {['👍', '❤️', '🔥', '💪'].map((e, i) => (
                    <span key={i} style={{
                      fontSize: 36,
                      transform: `scale(${1 + Math.sin(f * 0.1 + i * 0.8) * 0.08})`,
                      filter: `drop-shadow(0 2px 8px rgba(0,255,208,0.3))`,
                    }}>{e}</span>
                  ))}
                  <span style={{ color: C.main, fontSize: 28, fontWeight: 800, textShadow: GLOW.weak.text, marginLeft: 8 }}>
                    좋은 영상 감사합니다!
                  </span>
                </div>
              </div>
            </div>

            {/* "다음 영상에서 댓글 남겨주신 분들에게" */}
            {nextCommentOp > 0.01 && (
              <div style={{
                marginTop: 20, opacity: nextCommentOp,
                textAlign: 'center',
                color: '#9ca3af', fontSize: 24, fontWeight: 600,
              }}>
                👉 다음 영상에서 댓글 남겨주신 분들에게
              </div>
            )}
          </div>

          {/* 정리본 증정 카드 */}
          {giftOp > 0.01 && (
            <div style={{
              position: 'absolute', bottom: 155, left: '50%',
              transform: `translateX(-50%) scale(${giftScale})`,
              width: 900, opacity: giftOp,
            }}>
              <div style={{
                padding: '16px 28px',
                background: `${C.main}0d`, border: `1.5px solid ${C.main}35`, borderRadius: 20,
                marginBottom: 14,
                display: 'flex', alignItems: 'center', gap: 16,
              }}>
                <span style={{ fontSize: 32 }}>🎁</span>
                <div style={{ color: C.main, fontSize: 26, fontWeight: 800, textShadow: dynGlow }}>
                  이 시스템 구성 정리본 드릴게요
                </div>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                {RESOURCE_ITEMS.map((item, i) => {
                  const s = itemStarts[i];
                  const iOp = ip(f, s, s + 22);
                  const iTy = interpolate(f, [s, s + 22], [18, 0], {
                    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                    easing: Easing.out(Easing.cubic),
                  });
                  return (
                    <div key={i} style={{
                      flex: 1, opacity: iOp, transform: `translateY(${iTy}px)`,
                      padding: '10px 14px',
                      background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 14, color: '#9ca3af', fontSize: 14, fontWeight: 600, textAlign: 'center',
                    }}>
                      <div style={{ fontSize: 24, marginBottom: 6 }}>{item.icon}</div>
                      {item.text}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── PHASE 2: 저만 보기 아깝다 + 오픈 예고 ── */}
      {ph2Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: ph2Op,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 32,
        }}>
          <div style={{ opacity: regretOp, transform: `translateY(${regretTy}px)`, textAlign: 'center' }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 6, marginBottom: 14 }}>NOTICE</div>
            <div style={{ fontSize: 52, fontWeight: 900, color: '#e5e7eb' }}>
              이 분석, 저만 보기 <span style={{ color: '#FF4757' }}>아깝더라고요.</span>
            </div>
          </div>
          {openOp > 0.01 && (
            <div style={{
              opacity: openOp, transform: `translateY(${openTy}px)`,
              display: 'flex', alignItems: 'center', gap: 20,
              padding: '18px 52px',
              background: `${C.main}0d`, border: `1.5px solid ${C.main}38`, borderRadius: 28,
            }}>
              <span style={{ fontSize: 36 }}>🚀</span>
              <div style={{ fontSize: 42, fontWeight: 900, color: C.main, textShadow: dynGlow }}>
                조만간 오픈합니다.
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── PHASE 3: STOCK BRAIN ── */}
      {ph3Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: ph3Op,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 28,
        }}>
          <div style={{
            opacity: logoOp,
            transform: `scale(${logoScale * logoPulse})`,
            display: 'flex', alignItems: 'center', gap: 24,
          }}>
            <div style={{
              width: 100, height: 100, borderRadius: 24,
              background: `${C.main}20`, border: `2.5px solid ${C.main}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 50,
              boxShadow: `0 0 ${24 + Math.sin(f * 0.08) * 10}px ${C.main}66`,
            }}>🧠</div>
            <div>
              <div style={{
                fontSize: 74, fontWeight: 900, lineHeight: 1,
                color: C.main, textShadow: dynGlow, letterSpacing: 4,
              }}>STOCK BRAIN</div>
              <div style={{ color: '#4b5563', fontSize: 17, fontWeight: 700, letterSpacing: 5, marginTop: 6 }}>
                BY 로또의 주식인사이트
              </div>
            </div>
          </div>

          {bellOp > 0.01 && (
            <div style={{
              opacity: bellOp,
              transform: `scale(${bellScale}) rotate(${bellShake}deg)`,
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 18,
                padding: '18px 52px', background: C.main, borderRadius: 36,
                boxShadow: `0 4px 30px ${C.main}66`,
              }}>
                <span style={{ fontSize: 36 }}>🔔</span>
                <div style={{ fontSize: 34, fontWeight: 900, color: '#080c14', letterSpacing: 2 }}>알림 신청하기</div>
              </div>
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
