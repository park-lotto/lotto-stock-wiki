/**
 * S05 — STEP 1: Claude 코워크 설치 (1650프레임 = 55초)
 *
 * Phase A f0~850    : claude.ai 웹사이트 mock (다운로드 버튼 → Pro 요금제 강조)
 * Phase B f850~1650 : Claude 앱 내부 (코워크 탭 위치 강조)
 *
 * 가이드 준수: fadeIn / bgGlow / bottom:'18%' 콘텐츠 / 자막바 16% 40px 700
 */

import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const S05_FRAMES = 1650;

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

// Claude 다크 팔레트
const CL = {
  bg: '#111110', card: '#1E1E1C', border: '#2E2E2A',
  text: '#F5F4ED', sub: '#8C8C7E', orange: '#D97757',
};

// 공통: 민트 하이라이트 박스
const HlBox: React.FC<{ op: number; pulse: number; radius?: number }> = ({ op, pulse, radius = 14 }) => (
  <div style={{
    position: 'absolute', inset: -6, borderRadius: radius,
    border: `2px solid ${C.main}`,
    boxShadow: `0 0 ${14 * pulse}px rgba(0,255,208,${0.65 * pulse}), 0 0 ${32 * pulse}px rgba(0,255,208,${0.3 * pulse})`,
    opacity: op, pointerEvents: 'none',
  }} />
);

export const S05_ClaudeSetup: React.FC = () => {
  const f = useCurrentFrame();
  const fadeIn   = clamp(f, 0, 15);
  const bgGlow   = Math.sin(f * 0.04) * 0.025 + 0.035;
  const hlPulse  = 0.55 + Math.sin(f * 0.14) * 0.45;

  // 타임라인
  const uiOp    = clamp(f, 25, 55);       // UI 등장
  const tf1Op   = clamp(f, 80, 108);      // TECHFEED 1 (다운로드)
  const hl1Op   = clamp(f, 130, 160);     // 다운로드 버튼 하이라이트
  const tf2Op   = clamp(f, 440, 468);     // TECHFEED 2 (Pro 플랜)
  const hl2Op   = clamp(f, 490, 520);     // Pro 카드 하이라이트
  const appOp   = clamp(f, 860, 920);     // Claude 앱 전환
  const tf3Op   = clamp(f, 940, 968);     // TECHFEED 3 (코워크 탭)
  const hl3Op   = clamp(f, 990, 1020);    // 코워크 탭 하이라이트
  const subOp   = clamp(f, 55, 85);

  const showApp = f >= 860;

  const TECHFEED_ITEMS = [
    { label: '데스크톱 앱', desc: 'claude.ai → 다운로드 → 설치', op: tf1Op },
    { label: '필수 플랜',   desc: 'Pro ($20/월) — 무료는 코워크 없음', op: tf2Op },
    { label: '코워크 탭',   desc: '설치 후 왼쪽 메뉴에 바로 표시', op: tf3Op },
  ];

  return (
    <AbsoluteFill style={{ background: '#000', opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* STEP 카운터 (좌상단) */}
      <div style={{ position: 'absolute', top: 36, left: 52, zIndex: 100, opacity: uiOp }}>
        <div style={{ color: C.textSub, fontSize: 13, fontWeight: 600, letterSpacing: 4, marginBottom: 2 }}>진행상황</div>
        <div style={{
          color: C.main, fontSize: 58, fontWeight: 900,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: GLOW.mid.text, lineHeight: 1,
        }}>STEP <span style={{ fontSize: 80 }}>1</span><span style={{ color: C.textSub, fontSize: 32 }}>/5</span></div>
      </div>

      {/* 우상단 씬 라벨 */}
      <div style={{
        position: 'absolute', top: 30, right: 48,
        color: '#4b5563', fontSize: 15, fontWeight: 600, letterSpacing: 3, opacity: uiOp,
      }}>S05 · CLAUDE 설치</div>

      {/* ══ 콘텐츠 영역 (bottom 18%) ══ */}
      <div style={{ position: 'absolute', top: 130, left: 0, right: 0, bottom: '18%' }}>

        {/* ── Phase A: claude.ai 웹사이트 ── */}
        {!showApp && (
          <div style={{
            position: 'absolute', top: 10, left: 120, right: 120, bottom: 120,
            opacity: uiOp * (1 - clamp(f, 840, 890)),
          }}>
            {/* 브라우저 크롬 */}
            <div style={{
              background: '#1C1C1E', borderRadius: '10px 10px 0 0',
              padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8,
            }}>
              {['#FF5F56','#FFBD2E','#27C93F'].map((c, i) => (
                <div key={i} style={{ width: 11, height: 11, borderRadius: '50%', background: c }} />
              ))}
              <div style={{
                flex: 1, background: '#2C2C2E', borderRadius: 6,
                padding: '5px 14px', textAlign: 'center',
                color: '#888', fontSize: 14, letterSpacing: 1,
              }}>claude.ai</div>
            </div>

            {/* 페이지 본체 */}
            <div style={{
              background: CL.bg, borderRadius: '0 0 12px 12px',
              border: `1px solid ${CL.border}`, borderTop: 'none',
              padding: '28px 48px', overflow: 'hidden',
            }}>
              {/* 사이트 헤더 */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                borderBottom: `1px solid ${CL.border}`, paddingBottom: 18, marginBottom: 28,
              }}>
                <div style={{
                  width: 26, height: 26, borderRadius: 6, background: CL.orange,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontWeight: 900, fontSize: 14,
                }}>✦</div>
                <span style={{ color: CL.text, fontSize: 17, fontWeight: 700 }}>Claude</span>
                <div style={{ flex: 1 }} />
                <div style={{ color: CL.sub, fontSize: 13 }}>로그인</div>
                <div style={{
                  background: CL.orange, color: '#fff', fontSize: 13, fontWeight: 700,
                  padding: '7px 18px', borderRadius: 8,
                }}>시작하기</div>
              </div>

              {/* 히어로 + 다운로드 버튼 */}
              <div style={{ textAlign: 'center', marginBottom: 36 }}>
                <div style={{ color: CL.text, fontSize: 38, fontWeight: 800, lineHeight: 1.2, marginBottom: 10 }}>
                  Claude를<br />다운로드하세요
                </div>
                <div style={{ color: CL.sub, fontSize: 15, marginBottom: 24 }}>Mac · Windows · Linux</div>
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <div style={{
                    background: CL.orange, color: '#fff',
                    fontSize: 17, fontWeight: 700, padding: '14px 52px', borderRadius: 12,
                  }}>⬇ 다운로드</div>
                  {hl1Op > 0 && <HlBox op={hl1Op} pulse={hlPulse} radius={16} />}
                </div>
              </div>

              {/* 요금제 카드 3개 */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                {[
                  { name: 'Free', price: '₩0', note: '', isPro: false },
                  { name: 'Pro',  price: '$20', note: '/월 · 코워크 포함', isPro: true },
                  { name: 'Max',  price: '$100', note: '/월', isPro: false },
                ].map((plan, i) => (
                  <div key={i} style={{ position: 'relative' }}>
                    <div style={{
                      background: plan.isPro ? 'rgba(0,255,208,0.06)' : CL.card,
                      border: `1.5px solid ${plan.isPro ? C.main : CL.border}`,
                      borderRadius: 12, padding: '18px 20px',
                      boxShadow: plan.isPro && hl2Op > 0
                        ? `0 0 ${20 * hlPulse}px rgba(0,255,208,${0.35 * hlPulse})`
                        : undefined,
                    }}>
                      <div style={{ color: plan.isPro ? C.main : CL.text, fontSize: 15, fontWeight: 700, marginBottom: 6 }}>
                        {plan.name}
                        {i === 0 && hl2Op > 0 && (
                          <span style={{
                            marginLeft: 8, fontSize: 11, background: 'rgba(255,80,80,0.2)',
                            color: 'rgba(255,130,130,0.9)', padding: '2px 6px', borderRadius: 4,
                          }}>코워크 없음</span>
                        )}
                      </div>
                      <div style={{ color: CL.text, fontSize: 26, fontWeight: 900 }}>{plan.price}</div>
                      <div style={{ color: CL.sub, fontSize: 13, marginTop: 4 }}>{plan.note}</div>
                    </div>
                    {plan.isPro && hl2Op > 0 && <HlBox op={hl2Op} pulse={hlPulse} radius={14} />}
                    {plan.isPro && hl2Op > 0 && (
                      <div style={{
                        position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)',
                        background: C.main, color: '#000', fontSize: 11, fontWeight: 900,
                        padding: '3px 12px', borderRadius: 6, whiteSpace: 'nowrap', opacity: hl2Op,
                      }}>✓ 추천</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Phase B: Claude 앱 내부 (코워크 탭) ── */}
        {showApp && (
          <div style={{
            position: 'absolute', top: 10, left: 120, right: 120, bottom: 120,
            opacity: appOp,
          }}>
            <div style={{
              background: '#1B1B19', borderRadius: 12, overflow: 'hidden',
              border: `1px solid ${CL.border}`,
              display: 'flex', height: '100%',
            }}>
              {/* 사이드바 */}
              <div style={{
                width: 210, background: '#161614',
                borderRight: `1px solid ${CL.border}`,
                display: 'flex', flexDirection: 'column',
                position: 'relative',
              }}>
                <div style={{
                  padding: '16px 14px', display: 'flex', alignItems: 'center', gap: 8,
                  borderBottom: `1px solid ${CL.border}`,
                }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: 6, background: CL.orange,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#fff', fontSize: 12, fontWeight: 900,
                  }}>✦</div>
                  <span style={{ color: CL.text, fontSize: 15, fontWeight: 700 }}>Claude</span>
                </div>

                {[
                  { icon: '💬', label: '채팅',    active: false },
                  { icon: '🔌', label: '코워크',  active: true  },
                  { icon: '⚙️', label: '설정',    active: false },
                ].map((item, i) => (
                  <div key={i} style={{
                    padding: '13px 16px', display: 'flex', alignItems: 'center', gap: 10,
                    background: item.active ? 'rgba(0,255,208,0.07)' : 'transparent',
                    borderLeft: `3px solid ${item.active ? C.main : 'transparent'}`,
                    position: 'relative',
                  }}>
                    <span style={{ fontSize: 18 }}>{item.icon}</span>
                    <span style={{
                      fontSize: 14, fontWeight: item.active ? 700 : 400,
                      color: item.active ? C.main : CL.sub,
                      textShadow: item.active ? GLOW.weak.text : undefined,
                    }}>{item.label}</span>

                    {item.active && hl3Op > 0 && (
                      <div style={{
                        position: 'absolute', inset: 0,
                        border: `2px solid ${C.main}`,
                        boxShadow: `0 0 ${10 * hlPulse}px rgba(0,255,208,${0.55 * hlPulse})`,
                        opacity: hl3Op, pointerEvents: 'none',
                      }} />
                    )}
                  </div>
                ))}

                {/* 화살표 레이블 */}
                {hl3Op > 0 && (
                  <div style={{
                    position: 'absolute', left: 218, top: 108,
                    display: 'flex', alignItems: 'center', gap: 6, opacity: hl3Op,
                  }}>
                    <div style={{ color: C.main, fontSize: 26, textShadow: GLOW.weak.text }}>←</div>
                    <div style={{
                      background: C.main, color: '#000', fontSize: 12, fontWeight: 900,
                      padding: '5px 12px', borderRadius: 8, whiteSpace: 'nowrap',
                    }}>바로 여기!</div>
                  </div>
                )}
              </div>

              {/* 코워크 메인 영역 */}
              <div style={{ flex: 1, padding: '28px 36px' }}>
                <div style={{ color: CL.text, fontSize: 22, fontWeight: 700, marginBottom: 6 }}>코워크</div>
                <div style={{ color: CL.sub, fontSize: 15, marginBottom: 28 }}>AI 에이전트로 반복 작업을 자동화하세요</div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {[
                    { name: 'PlayMCP', status: '연결됨', active: true },
                    { name: '웹 검색', status: '기본 제공', active: false },
                    { name: '파일 처리', status: '기본 제공', active: false },
                  ].map((conn, i) => (
                    <div key={i} style={{
                      background: CL.card,
                      border: `1px solid ${i === 0 ? 'rgba(0,255,208,0.35)' : CL.border}`,
                      borderRadius: 10, padding: '14px 18px',
                      display: 'flex', alignItems: 'center', gap: 12,
                    }}>
                      <div style={{
                        width: 10, height: 10, borderRadius: '50%',
                        background: i === 0 ? C.main : '#444',
                        boxShadow: i === 0 ? `0 0 6px ${C.main}` : undefined,
                      }} />
                      <span style={{ color: i === 0 ? C.main : CL.sub, fontSize: 15, fontWeight: i === 0 ? 700 : 400 }}>
                        {conn.name}
                      </span>
                      <div style={{ flex: 1 }} />
                      <span style={{ color: CL.sub, fontSize: 13 }}>{conn.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ══ TECHFEED 오버레이 (하단 좌측) ══ */}
        <div style={{
          position: 'absolute', bottom: 24, left: 64,
          display: 'flex', flexDirection: 'column', gap: 11,
        }}>
          {TECHFEED_ITEMS.map((item, i) => (
            <div key={i} style={{
              opacity: item.op,
              transform: `translateX(${interpolate(item.op, [0, 1], [-32, 0])}px)`,
              display: 'flex', alignItems: 'center', gap: 14,
            }}>
              <div style={{
                color: C.main, fontSize: 19, fontWeight: 700, letterSpacing: 1,
                minWidth: 106, textAlign: 'right', textShadow: GLOW.weak.text,
              }}>{item.label}</div>
              <div style={{ width: 1, height: 26, background: 'rgba(0,255,208,0.35)' }} />
              <div style={{ color: C.textPrimary, fontSize: 19, fontWeight: 400 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 자막 바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        background: 'rgba(0,0,0,0.88)',
        borderTop: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: subOp,
      }}>
        <div style={{
          fontSize: 40, fontWeight: 700, color: C.textPrimary,
          textAlign: 'center', paddingInline: 80,
        }}>
          Claude 앱 + Pro 플랜 ($20/월)
        </div>
      </div>
    </AbsoluteFill>
  );
};
