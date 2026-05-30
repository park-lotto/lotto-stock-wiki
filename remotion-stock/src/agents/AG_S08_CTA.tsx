// AG_S08 — 씬8 CTA (930프레임 / 31초)
// ※ 녹음 후 Whisper 싱크로 타이밍 조정 필요
// [01] f0000~0100  "댓글에 '직원'이라고 남겨주시면"
// [02] f0110~0220  "이 시스템 구성 정리본 보내드릴게요"
// [03] f0250~0320  "그리고 이 분석"
// [04] f0330~0420  "저만 보기 아깝더라고요"
// [05] f0440~0510  "조만간 오픈합니다"
// [06] f0540~0660  "[STOCK BRAIN] 알림 신청해두세요"

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
  { s: 0,   e: 100, text: "댓글에 '직원'이라고 남겨주시면" },
  { s: 110, e: 220, text: '이 시스템 구성 정리본 보내드릴게요.' },
  { s: 250, e: 320, text: '그리고 이 분석.' },
  { s: 330, e: 420, text: '저만 보기 아깝더라고요.' },
  { s: 440, e: 510, text: '조만간 오픈합니다.' },
  { s: 540, e: 660, text: '[STOCK BRAIN] 알림 신청해두세요.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

const RESOURCE_ITEMS = [
  '시스템 설계 다이어그램',
  '직원 역할 체크리스트',
  'Claude Code 설정 예시',
  '자동화 스크립트 구조',
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

  const fadeInOut = (inA: number, inB: number, outA: number, outB: number) =>
    ip(f, inA, inB) * (1 - ip(f, outA, outB));

  // Phase 1 (f0~250): 댓글 CTA
  const ph1Op = fadeInOut(0, 18, 232, 252);

  const commentBoxOp = ip(f, 10, 55);
  const commentBoxTy = interpolate(f, [10, 55], [40, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.5)),
  });

  // 타이핑 애니메이션 (f60~110)
  const KEYWORD = '직원';
  const typedLen   = Math.round(ip(f, 60, 110, 0, KEYWORD.length));
  const typedText  = KEYWORD.slice(0, typedLen);
  const cursorBlink = Math.sin(f * 0.35) > 0 && f >= 60 && f <= 220;

  const dmBadgeOp    = ip(f, 120, 165);
  const dmBadgeScale = interpolate(f, [120, 165], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.8)),
  });

  const itemStarts = [140, 160, 180, 200];

  // Phase 2 (f240~540): 아깝더라고요 → 오픈 예고
  const ph2Op = fadeInOut(240, 280, 522, 542);

  const regretOp = ip(f, 260, 320);
  const regretTy = interpolate(f, [260, 320], [35, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const openOp = ip(f, 450, 510);
  const openTy = interpolate(f, [450, 510], [35, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // Phase 3 (f520~930): STOCK BRAIN
  const ph3Op = ip(f, 520, 560);

  const logoOp    = ip(f, 550, 610);
  const logoScale = interpolate(f, [550, 610], [0.2, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.75)),
  });
  const logoPulse = logoOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.022 : 1;

  const sloganOp = ip(f, 620, 670);

  const bellOp    = ip(f, 680, 730);
  const bellScale = interpolate(f, [680, 730], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.8)),
  });
  const bellShake = f >= 730 && f < 760 ? Math.sin(f * 0.2) * (f - 730) * 0.2 : 0;

  const scanY  = interpolate(f, [550, 590], [-2, 104], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [550, 555, 585, 590], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

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

      {/* ── PHASE 1: 댓글 "직원" ── */}
      {ph1Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph1Op }}>
          <div style={{
            position: 'absolute', top: 65, left: 0, right: 0,
            textAlign: 'center', opacity: ip(f, 8, 40),
          }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8, marginBottom: 10 }}>COMMENT</div>
            <div style={{ fontSize: 46, fontWeight: 900, color: '#e5e7eb' }}>댓글에 이 단어 하나만</div>
          </div>

          {/* 댓글창 */}
          <div style={{
            position: 'absolute', top: 220, left: '50%',
            transform: `translate(-50%, ${commentBoxTy}px)`,
            width: 800, opacity: commentBoxOp,
          }}>
            <div style={{
              padding: '28px 32px',
              background: 'rgba(255,255,255,0.04)',
              border: `2px solid ${C.main}50`, borderRadius: 20,
              display: 'flex', alignItems: 'center', gap: 18,
            }}>
              <div style={{
                width: 52, height: 52, borderRadius: '50%',
                background: `${C.main}22`, border: `2px solid ${C.main}40`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 24, flexShrink: 0,
              }}>👤</div>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                <span style={{ fontSize: 52, fontWeight: 900, color: C.main, textShadow: GLOW.mid.text, letterSpacing: 4 }}>
                  {typedText || (f >= 110 ? KEYWORD : '')}
                </span>
                {cursorBlink && (
                  <span style={{
                    display: 'inline-block', width: 3, height: 52,
                    background: C.main, marginLeft: 4,
                    boxShadow: `0 0 8px ${C.main}`,
                  }} />
                )}
              </div>
              <div style={{
                padding: '10px 28px',
                background: `${C.main}22`, border: `1.5px solid ${C.main}50`, borderRadius: 14,
                color: C.main, fontSize: 18, fontWeight: 700, flexShrink: 0,
                opacity: ip(f, 100, 130),
              }}>댓글 달기</div>
            </div>

            {dmBadgeOp > 0.01 && (
              <div style={{
                marginTop: 18, opacity: dmBadgeOp,
                transform: `scale(${dmBadgeScale})`, transformOrigin: 'center top',
                display: 'flex', justifyContent: 'center',
              }}>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 14,
                  padding: '12px 32px',
                  background: `${C.main}0d`, border: `1.5px solid ${C.main}35`, borderRadius: 28,
                }}>
                  <span style={{ fontSize: 28 }}>💌</span>
                  <div style={{ color: C.main, fontSize: 22, fontWeight: 700 }}>정리본 자동 DM 발송</div>
                </div>
              </div>
            )}
          </div>

          {/* 자료 목록 */}
          <div style={{
            position: 'absolute', bottom: 165, left: '50%', transform: 'translateX(-50%)',
            display: 'flex', gap: 14,
          }}>
            {RESOURCE_ITEMS.map((item, i) => {
              const s = itemStarts[i];
              const iOp = ip(f, s, s + 28);
              const iTy = interpolate(f, [s, s + 28], [20, 0], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                easing: Easing.out(Easing.cubic),
              });
              return (
                <div key={i} style={{
                  opacity: iOp, transform: `translateY(${iTy}px)`,
                  padding: '8px 18px',
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 14, color: '#9ca3af', fontSize: 15, fontWeight: 600, whiteSpace: 'nowrap',
                }}>📎 {item}</div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── PHASE 2: "저만 보기 아깝다" ── */}
      {ph2Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: ph2Op,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 30,
        }}>
          <div style={{ opacity: regretOp, transform: `translateY(${regretTy}px)`, textAlign: 'center' }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 6, marginBottom: 14 }}>NOTICE</div>
            <div style={{ fontSize: 54, fontWeight: 900, color: '#e5e7eb' }}>
              이 분석, 저만 보기 아깝더라고요.
            </div>
          </div>
          {openOp > 0.01 && (
            <div style={{
              opacity: openOp, transform: `translateY(${openTy}px)`,
              display: 'flex', alignItems: 'center', gap: 20,
              padding: '16px 48px',
              background: `${C.main}0d`, border: `1.5px solid ${C.main}38`, borderRadius: 28,
            }}>
              <span style={{ fontSize: 36 }}>🔔</span>
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
          alignItems: 'center', justifyContent: 'center', gap: 24,
        }}>
          {/* 스캔라인 */}
          <div style={{
            position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2,
            background: `linear-gradient(90deg, transparent 0%, ${C.main} 20%, #80FFE8 50%, ${C.main} 80%, transparent 100%)`,
            boxShadow: `0 0 10px rgba(0,255,208,0.9)`,
            opacity: scanOp, zIndex: 10, pointerEvents: 'none',
          }} />

          <div style={{
            opacity: logoOp,
            transform: `scale(${logoScale * logoPulse})`,
            display: 'flex', alignItems: 'center', gap: 28,
          }}>
            <div style={{
              width: 110, height: 110, borderRadius: 28,
              background: `${C.main}20`, border: `2.5px solid ${C.main}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 56,
              boxShadow: `0 0 ${24 + Math.sin(f * 0.08) * 10}px ${C.main}66`,
            }}>🧠</div>
            <div>
              <div style={{
                fontSize: 80, fontWeight: 900, lineHeight: 1,
                color: C.main, textShadow: dynGlow, letterSpacing: 4,
              }}>STOCK BRAIN</div>
              <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 6, marginTop: 6 }}>
                BY 로또의 주식인사이트
              </div>
            </div>
          </div>

          <div style={{ opacity: sloganOp, color: '#6b7280', fontSize: 24, fontWeight: 600 }}>
            300개 정보 중 오늘 써먹을 3가지만
          </div>

          {bellOp > 0.01 && (
            <div style={{
              opacity: bellOp,
              transform: `scale(${bellScale}) rotate(${bellShake}deg)`,
              marginTop: 8,
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 18,
                padding: '18px 52px', background: C.main, borderRadius: 36,
                boxShadow: `0 4px 30px ${C.main}66, 0 0 60px ${C.main}22`,
              }}>
                <span style={{ fontSize: 36 }}>🔔</span>
                <div style={{ fontSize: 36, fontWeight: 900, color: '#080c14', letterSpacing: 2 }}>알림 신청하기</div>
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
