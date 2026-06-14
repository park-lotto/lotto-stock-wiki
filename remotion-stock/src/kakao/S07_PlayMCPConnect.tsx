/**
 * S07 — STEP 2: PlayMCP 연결 실연 (2400프레임 = 80초)
 *
 * Phase A f0~1300   : PlayMCP 사이트 + 서비스 카드 + TECHFEED
 * Phase B f1300~1600: Claude 코워크 → 커넥터 → 스위치 ON
 * Phase C f1600~2400: SPLIT 화면 (Claude 좌 + 카카오톡 우) + 테스트 메시지
 */

import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const S07_FRAMES = 2400;

const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const CL = {
  bg: '#111110', card: '#1E1E1C', border: '#2E2E2A',
  text: '#F5F4ED', sub: '#8C8C7E', orange: '#D97757',
};

// 카카오 브랜드
const KK = {
  bg:      '#1E1B17',
  yellow:  '#FAE100',
  msgBg:   '#2A2620',
  myBg:    '#FAE100',
  myText:  '#111111',
};

// 민트 하이라이트 박스
const HlBox: React.FC<{ op: number; pulse: number; radius?: number; inset?: number }> = ({
  op, pulse, radius = 12, inset = -5,
}) => (
  <div style={{
    position: 'absolute', inset,
    borderRadius: radius,
    border: `2px solid ${C.main}`,
    boxShadow: `0 0 ${14 * pulse}px rgba(0,255,208,${0.65 * pulse}), 0 0 ${30 * pulse}px rgba(0,255,208,${0.28 * pulse})`,
    opacity: op, pointerEvents: 'none',
  }} />
);

// PlayMCP 서비스 카드
const ServiceCard: React.FC<{
  icon: string; name: string; desc: string;
  added?: boolean; highlight?: boolean;
  hlOp?: number; pulse?: number;
  f: number; startF: number;
}> = ({ icon, name, desc, added, highlight, hlOp = 0, pulse = 0.5, f, startF }) => {
  const cardOp = clamp(f, startF, startF + 28);
  const cardY  = interpolate(f, [startF, startF + 28], [24, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.5)),
  });

  return (
    <div style={{
      opacity: cardOp, transform: `translateY(${cardY}px)`,
      position: 'relative',
      background: highlight ? 'rgba(0,255,208,0.05)' : CL.card,
      border: `1.5px solid ${highlight ? C.main : CL.border}`,
      borderRadius: 14, padding: '18px 20px',
      display: 'flex', flexDirection: 'column', gap: 10,
      boxShadow: highlight && hlOp > 0
        ? `0 0 ${18 * pulse}px rgba(0,255,208,${0.35 * pulse})`
        : '0 2px 12px rgba(0,0,0,0.4)',
    }}>
      <div style={{ fontSize: 36 }}>{icon}</div>
      <div style={{ color: highlight ? C.main : CL.text, fontSize: 16, fontWeight: 700 }}>{name}</div>
      <div style={{ color: CL.sub, fontSize: 13, lineHeight: 1.5 }}>{desc}</div>
      <div style={{
        background: added ? 'rgba(0,255,208,0.15)' : CL.bg,
        border: `1px solid ${added ? C.main : CL.border}`,
        borderRadius: 8, padding: '8px 0', textAlign: 'center',
        color: added ? C.main : CL.sub, fontSize: 13, fontWeight: 700,
      }}>{added ? '✓ 추가됨' : '+ 추가'}</div>

      {highlight && hlOp > 0 && <HlBox op={hlOp} pulse={pulse} radius={16} inset={-4} />}
    </div>
  );
};

export const S07_PlayMCPConnect: React.FC = () => {
  const f = useCurrentFrame();
  const fadeIn  = clamp(f, 0, 15);
  const bgGlow  = Math.sin(f * 0.04) * 0.025 + 0.035;
  const hlPulse = 0.55 + Math.sin(f * 0.14) * 0.45;

  // ── Phase 타이밍 ──────────────────────────────────────
  const phase = f < 1300 ? 'A' : f < 1620 ? 'B' : 'C';
  const phaseAOp = f < 1260 ? 1 : clamp(f, 1260, 1320, 1, 0);
  const phaseBOp = clamp(f, 1310, 1380) * (f < 1580 ? 1 : clamp(f, 1580, 1630, 1, 0));
  const phaseCOp = clamp(f, 1610, 1680);

  // Phase A
  const uiOp   = clamp(f, 28, 58);
  const tf1Op  = clamp(f, 90, 118);
  const hl1Op  = clamp(f, 160, 190);   // 카카오 추가 버튼
  const tf2Op  = clamp(f, 520, 548);
  const tf3Op  = clamp(f, 950, 978);

  // Phase B
  const switchOp  = clamp(f, 1360, 1420); // 스위치 ON
  const switchOn  = f >= 1480;
  const switchAnim = clamp(f, 1460, 1500);

  // Phase C (SPLIT)
  const chatTypeProg = clamp(f, 1720, 1920); // Claude 타이핑 진행도
  const CHAT_MSG = '카카오톡 나에게\n"테스트"라고 보내줘';
  const visibleLen   = Math.floor(chatTypeProg * CHAT_MSG.length);
  const thinkingDot  = (i: number) => (0.5 + 0.5 * Math.sin(f * 0.18 + i * 1.2));

  const kakaoMsgOp  = clamp(f, 1980, 2030);  // 카카오 메시지 도착
  const kakaoNotify = clamp(f, 2020, 2060);  // 알림 팝업
  const doneOp      = clamp(f, 2060, 2100);  // "됐죠?" 완료 표시

  const subOp  = clamp(f, 58, 88);

  // 자막 텍스트 (페이즈별)
  const captionText = phase === 'C'
    ? 'PlayMCP → 카카오톡 연결 완료 ✅'
    : 'PlayMCP — 한국 서비스 전용 MCP 허브';

  const TECHFEED_ITEMS = [
    { label: '카카오톡 나채팅방', desc: 'Claude가 내 카카오톡으로 메시지 전송', op: tf1Op },
    { label: '네이버 검색',       desc: '실시간 뉴스 검색 자동화',               op: tf2Op },
    { label: '미국 주식',         desc: '주가·뉴스 자동 수집',                   op: tf3Op },
  ];

  return (
    <AbsoluteFill style={{ background: '#000', opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* STEP 카운터 */}
      <div style={{ position: 'absolute', top: 36, left: 52, zIndex: 100, opacity: uiOp }}>
        <div style={{ color: C.textSub, fontSize: 13, fontWeight: 600, letterSpacing: 4, marginBottom: 2 }}>진행상황</div>
        <div style={{
          color: C.main, fontSize: 58, fontWeight: 900,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: GLOW.mid.text, lineHeight: 1,
        }}>STEP <span style={{ fontSize: 80 }}>2</span><span style={{ color: C.textSub, fontSize: 32 }}>/5</span></div>
      </div>

      {/* 우상단 씬 라벨 */}
      <div style={{
        position: 'absolute', top: 30, right: 48,
        color: '#4b5563', fontSize: 15, fontWeight: 600, letterSpacing: 3, opacity: uiOp,
      }}>S07 · PlayMCP 연결</div>

      {/* ══ 콘텐츠 영역 ══ */}
      <div style={{ position: 'absolute', top: 130, left: 0, right: 0, bottom: '18%' }}>

        {/* ── Phase A: PlayMCP 사이트 ── */}
        <div style={{
          position: 'absolute', top: 0, left: 60, right: 60, bottom: 100,
          opacity: phaseAOp,
        }}>
          {/* 사이트 헤더 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            marginBottom: 24, opacity: uiOp,
          }}>
            <div style={{
              background: C.main, color: '#000',
              fontSize: 16, fontWeight: 900, padding: '6px 16px', borderRadius: 8,
              textShadow: 'none',
            }}>PLAY<br />MCP</div>
            <div>
              <div style={{ color: C.main, fontSize: 20, fontWeight: 800, textShadow: GLOW.weak.text }}>
                PlayMCP
              </div>
              <div style={{ color: CL.sub, fontSize: 14 }}>한국 서비스 전용 AI 커넥터 허브</div>
            </div>
          </div>

          {/* 서비스 카드 그리드 */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 18,
            opacity: uiOp,
          }}>
            <ServiceCard
              icon="💬" name="카카오톡 나채팅방"
              desc="Claude가 내 카카오로 메시지 전송"
              added={f >= 1100} highlight={f >= 80 && f < 500}
              hlOp={hl1Op} pulse={hlPulse}
              f={f} startF={60}
            />
            <ServiceCard
              icon="🔍" name="네이버 검색"
              desc="실시간 뉴스 · 종목 검색"
              f={f} startF={130}
            />
            <ServiceCard
              icon="📈" name="미국 주식"
              desc="주가 · 뉴스 자동 수집"
              f={f} startF={200}
            />
            <ServiceCard
              icon="📰" name="네이버 뉴스"
              desc="섹터 · 종목 뉴스 크롤링"
              f={f} startF={270}
            />
          </div>

          {/* TECHFEED 오버레이 */}
          <div style={{
            position: 'absolute', bottom: -20, left: 0,
            display: 'flex', flexDirection: 'column', gap: 11,
          }}>
            {TECHFEED_ITEMS.map((item, i) => (
              <div key={i} style={{
                opacity: item.op,
                transform: `translateX(${interpolate(item.op, [0, 1], [-32, 0])}px)`,
                display: 'flex', alignItems: 'center', gap: 14,
              }}>
                <div style={{
                  color: C.main, fontSize: 18, fontWeight: 700, letterSpacing: 1,
                  minWidth: 140, textAlign: 'right', textShadow: GLOW.weak.text,
                }}>{item.label}</div>
                <div style={{ width: 1, height: 24, background: 'rgba(0,255,208,0.35)' }} />
                <div style={{ color: C.textPrimary, fontSize: 18, fontWeight: 400 }}>{item.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Phase B: Claude 코워크 → 스위치 ON ── */}
        <div style={{
          position: 'absolute', top: 0, left: 60, right: 60, bottom: 100,
          opacity: phaseBOp,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: CL.bg, borderRadius: 16, padding: '32px 40px',
            border: `1px solid ${CL.border}`, width: 800,
            boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
          }}>
            <div style={{ color: CL.sub, fontSize: 13, letterSpacing: 3, marginBottom: 8 }}>Claude 코워크</div>
            <div style={{ color: CL.text, fontSize: 20, fontWeight: 700, marginBottom: 24 }}>
              커넥터 → + 추가 → PlayMCP
            </div>

            {/* 커넥터 항목 + 스위치 */}
            {[
              { name: 'PlayMCP', toggleable: true },
              { name: '웹 검색 (기본)', toggleable: false },
            ].map((conn, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 16,
                background: CL.card, borderRadius: 10,
                padding: '14px 18px', marginBottom: 12,
                border: `1px solid ${i === 0 && switchOn ? C.main : CL.border}`,
                boxShadow: i === 0 && switchOn ? `0 0 14px rgba(0,255,208,0.25)` : undefined,
                position: 'relative',
              }}>
                <div style={{
                  width: 10, height: 10, borderRadius: '50%',
                  background: (i === 0 && switchOn) ? C.main : '#444',
                  boxShadow: (i === 0 && switchOn) ? `0 0 6px ${C.main}` : undefined,
                }} />
                <div style={{ color: (i === 0 && switchOn) ? C.main : CL.text, fontSize: 15, flex: 1 }}>
                  {conn.name}
                </div>

                {/* 토글 스위치 */}
                {conn.toggleable && (
                  <div style={{ position: 'relative' }}>
                    <div style={{
                      width: 52, height: 28, borderRadius: 14,
                      background: switchOn ? C.main : '#333',
                      transition: 'background 0.3s',
                      boxShadow: switchOn ? `0 0 10px rgba(0,255,208,0.5)` : undefined,
                    }}>
                      <div style={{
                        position: 'absolute', top: 4,
                        left: switchOn ? 28 : 4,
                        width: 20, height: 20, borderRadius: '50%',
                        background: switchOn ? '#000' : '#888',
                        transition: 'left 0.3s',
                      }} />
                    </div>
                    {!switchOn && switchOp > 0 && (
                      <div style={{
                        position: 'absolute', top: -32, left: '50%', transform: 'translateX(-50%)',
                        background: C.main, color: '#000', fontSize: 11, fontWeight: 900,
                        padding: '3px 10px', borderRadius: 6, whiteSpace: 'nowrap',
                        opacity: switchOp,
                      }}>← ON으로!</div>
                    )}
                  </div>
                )}

                {i === 0 && switchOp > 0 && (
                  <HlBox op={switchOp * (switchOn ? 0 : 1)} pulse={hlPulse} radius={12} />
                )}
              </div>
            ))}

            {switchOn && (
              <div style={{
                textAlign: 'center', marginTop: 16, opacity: switchAnim,
                color: C.main, fontSize: 20, fontWeight: 700, textShadow: GLOW.weak.text,
              }}>
                ✅ PlayMCP 연결 완료 — 테스트해볼게요
              </div>
            )}
          </div>
        </div>

        {/* ── Phase C: SPLIT 화면 ── */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          opacity: phaseCOp,
          display: 'flex', gap: 3,
        }}>
          {/* 좌: Claude 채팅창 */}
          <div style={{
            flex: 1, background: CL.bg,
            border: `1px solid ${CL.border}`, borderRadius: 12,
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
            margin: '0 2px 0 60px',
          }}>
            {/* 헤더 */}
            <div style={{
              padding: '14px 20px', borderBottom: `1px solid ${CL.border}`,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <div style={{ width: 22, height: 22, borderRadius: 5, background: CL.orange, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 900 }}>✦</div>
              <span style={{ color: CL.text, fontSize: 15, fontWeight: 700 }}>Claude</span>
              <div style={{ marginLeft: 8, color: CL.sub, fontSize: 12, border: `1px solid ${CL.border}`, padding: '2px 8px', borderRadius: 5 }}>Opus 4.7</div>
            </div>

            {/* 메시지 영역 */}
            <div style={{ flex: 1, padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14, justifyContent: 'flex-end' }}>
              {/* 유저 메시지 */}
              {chatTypeProg > 0.05 && (
                <div style={{
                  alignSelf: 'flex-end', maxWidth: '75%',
                  background: '#2A2926', borderRadius: 14, padding: '12px 16px',
                  color: CL.text, fontSize: 15, lineHeight: 1.6, whiteSpace: 'pre-wrap',
                }}>
                  {CHAT_MSG.substring(0, visibleLen)}
                  {chatTypeProg < 1 && (
                    <span style={{
                      display: 'inline-block', width: 2, height: 18,
                      background: CL.text, marginLeft: 2,
                      opacity: f % 20 < 10 ? 1 : 0, verticalAlign: 'middle',
                    }} />
                  )}
                </div>
              )}

              {/* Claude 타이핑 인디케이터 */}
              {chatTypeProg >= 1 && kakaoMsgOp < 0.5 && (
                <div style={{ alignSelf: 'flex-start', display: 'flex', gap: 8, padding: '8px 0' }}>
                  <div style={{ width: 22, height: 22, borderRadius: 5, background: CL.orange, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 900, flexShrink: 0 }}>✦</div>
                  <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                    {[0,1,2].map(i => (
                      <div key={i} style={{
                        width: 8, height: 8, borderRadius: '50%', background: CL.sub,
                        opacity: 0.3 + thinkingDot(i) * 0.7,
                        transform: `translateY(${-thinkingDot(i) * 4}px)`,
                      }} />
                    ))}
                  </div>
                </div>
              )}

              {/* Claude 응답 */}
              {kakaoMsgOp > 0.3 && (
                <div style={{
                  alignSelf: 'flex-start', maxWidth: '80%',
                  display: 'flex', gap: 10, opacity: kakaoMsgOp,
                }}>
                  <div style={{ width: 22, height: 22, borderRadius: 5, background: CL.orange, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 900, flexShrink: 0, marginTop: 2 }}>✦</div>
                  <div style={{ color: CL.text, fontSize: 15, lineHeight: 1.6 }}>
                    카카오톡 나에게 "테스트" 메시지를 보냈습니다. ✅
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 우: 카카오톡 나채팅방 */}
          <div style={{
            flex: 1, background: KK.bg,
            border: `1px solid rgba(250,225,0,0.15)`, borderRadius: 12,
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
            margin: '0 60px 0 2px',
          }}>
            {/* 헤더 */}
            <div style={{
              background: '#242018', padding: '14px 20px',
              display: 'flex', alignItems: 'center', gap: 10,
              borderBottom: '1px solid rgba(250,225,0,0.12)',
            }}>
              <div style={{
                width: 38, height: 38, borderRadius: '50%',
                background: KK.yellow,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 20,
              }}>😊</div>
              <div>
                <div style={{ color: '#F5F4ED', fontSize: 15, fontWeight: 700 }}>나</div>
                <div style={{ color: '#8C8C7E', fontSize: 12 }}>나와의 채팅</div>
              </div>
            </div>

            {/* 채팅 영역 */}
            <div style={{ flex: 1, padding: '20px 18px', position: 'relative' }}>
              {/* 날짜 구분선 */}
              <div style={{ textAlign: 'center', marginBottom: 20 }}>
                <span style={{
                  color: '#6B6458', fontSize: 12,
                  background: 'rgba(255,255,255,0.04)', padding: '4px 12px', borderRadius: 10,
                }}>오늘</span>
              </div>

              {/* 기존 메시지들 */}
              {[
                '주식 브리핑 시작할게요',
                '📊 코스피 -0.3% 약보합',
              ].map((msg, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'flex-end', marginBottom: 10,
                }}>
                  <div style={{
                    background: KK.yellow, color: KK.myText,
                    fontSize: 14, fontWeight: 500, padding: '10px 14px', borderRadius: '14px 14px 4px 14px',
                    maxWidth: '70%',
                  }}>{msg}</div>
                </div>
              ))}

              {/* 테스트 메시지 도착 */}
              {kakaoMsgOp > 0 && (
                <div style={{
                  display: 'flex', justifyContent: 'flex-end', marginBottom: 10,
                  opacity: kakaoMsgOp,
                  transform: `translateY(${interpolate(kakaoMsgOp, [0, 1], [20, 0])}px)`,
                }}>
                  <div style={{
                    background: KK.yellow, color: KK.myText,
                    fontSize: 16, fontWeight: 700, padding: '12px 18px',
                    borderRadius: '14px 14px 4px 14px',
                    boxShadow: `0 0 16px rgba(250,225,0,0.4)`,
                  }}>테스트</div>
                </div>
              )}

              {/* 알림 팝업 */}
              {kakaoNotify > 0.3 && (
                <div style={{
                  position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)',
                  background: 'rgba(0,0,0,0.85)', borderRadius: 10,
                  padding: '10px 20px', opacity: kakaoNotify * (doneOp < 0.3 ? 1 : clamp(doneOp, 0, 0.5, 1, 0)),
                  display: 'flex', alignItems: 'center', gap: 8,
                  border: `1px solid rgba(250,225,0,0.2)`,
                  whiteSpace: 'nowrap',
                }}>
                  <span style={{ fontSize: 18 }}>🔔</span>
                  <span style={{ color: KK.yellow, fontSize: 13, fontWeight: 700 }}>나 · 방금</span>
                  <span style={{ color: '#F5F4ED', fontSize: 13 }}>테스트</span>
                </div>
              )}

              {/* 완료 확인 */}
              {doneOp > 0 && (
                <div style={{
                  position: 'absolute', bottom: 20, left: 0, right: 0,
                  textAlign: 'center', opacity: doneOp,
                }}>
                  <div style={{
                    display: 'inline-block',
                    background: C.main, color: '#000',
                    fontSize: 16, fontWeight: 900, padding: '10px 28px', borderRadius: 30,
                    boxShadow: `0 0 20px rgba(0,255,208,0.55)`,
                  }}>됐죠? ✅</div>
                </div>
              )}
            </div>
          </div>
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
          transition: 'opacity 0.3s',
        }}>
          {captionText}
        </div>
      </div>
    </AbsoluteFill>
  );
};
