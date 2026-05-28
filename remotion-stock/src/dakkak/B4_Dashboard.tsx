// B4 — 08:00 STOCK BRAIN 대시보드 풀스크린
// 영상 전체에서 가장 중요한 컷
// 마우스 한 번 클릭 → 대시보드가 풀스크린으로 펼쳐짐 → "딸깍" 회수
// 실제 트레이더가 보는 대시보드처럼: 탑픽 3종목 + 섹터온도 + 수급빈집 + 일정
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 360;

// 탑픽 3종목 — 실제 위키 데이터 기반
const TOP_PICKS = [
  {
    rank: 1, name: 'SK하이닉스', code: '000660', score: 8,
    price: '258,000', change: '+1.94%', changeUp: true,
    sector: '반도체', subsector: 'HBM',
    badges: ['수급빈집A', '수출🔴', '어닝서프', '리포트신고가'],
    why: 'HBM4 Vera Rubin 독점 95% · NVDA 어제 +1.9% 커플',
  },
  {
    rank: 2, name: '한화에어로스페이스', code: '012450', score: 6,
    price: '418,500', change: '+3.21%', changeUp: true,
    sector: '방산', subsector: 'K9·천무',
    badges: ['수주역대최고', '리포트TP↑', '일정D-12'],
    why: 'K9 폴란드 2차계약 D-12 · 다올 TP 204만',
  },
  {
    rank: 3, name: '대한조선', code: '067160', score: 6,
    price: '142,300', change: '+5.81%', changeUp: true,
    sector: '조선', subsector: '탱커',
    badges: ['PER9.8', '순현금1조', '수출신호'],
    why: 'SCC 수에즈막스 Pure Play · 나무라조선 절반 PER',
  },
];

// 섹터 온도 (5개)
const SECTORS = [
  { name: '반도체',  temp: '🔴', score: 87 },
  { name: '방산',    temp: '🟠', score: 72 },
  { name: '조선',    temp: '🔴', score: 81 },
  { name: 'AI소프트', temp: '🟠', score: 68 },
  { name: '바이오',  temp: '🟡', score: 54 },
];

// 임박 이벤트
const EVENTS = [
  { date: 'D-2',  text: '한은 금통위',          tag: '매크로' },
  { date: 'D-12', text: 'K9 폴란드 2차',        tag: '방산' },
  { date: 'D-17', text: 'NVDA 1Q 실적',         tag: '반도체' },
  { date: 'D-33', text: 'EU 철강관세 50% 발효', tag: '⚠️' },
];

export const B4_Dashboard = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [15, DUR - 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const timeOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // ── 페이즈 1: 대기 (마우스 커서 화면 진입) — 0~0.18
  const cursorMoveProg = interpolate(prog, [0.00, 0.15], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const cursorX = interpolate(cursorMoveProg, [0, 1], [1850, 960]);
  const cursorY = interpolate(cursorMoveProg, [0, 1], [1000, 540]);
  const cursorOp = interpolate(prog, [0.00, 0.04, 0.20, 0.24], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // ── 페이즈 2: 클릭 임팩트 (0.16) — 짧고 강하게
  const CLICK_AT = 0.16;
  const clickPulse = interpolate(prog, [CLICK_AT, CLICK_AT + 0.04, CLICK_AT + 0.10], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // ── 페이즈 3: 대시보드 등장 (0.18~0.32)
  const dashOp = interpolate(prog, [0.18, 0.32], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const dashScale = interpolate(prog, [0.18, 0.32], [0.92, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── 페이즈 4: 카드 stagger 등장 (0.30~0.50)
  const cardAnim = (i: number) => {
    const start = 0.30 + i * 0.05;
    return {
      op: interpolate(prog, [start, start + 0.08], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
      ty: interpolate(prog, [start, start + 0.08], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
    };
  };

  // ── 페이즈 5: 사이드 섹션 (0.45~0.60)
  const sideOp = interpolate(prog, [0.45, 0.58], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // ── 페이즈 6: "딸깍" 자막 (0.70~0.85)
  const ddakOp = interpolate(prog, [0.70, 0.80], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const ddakScale = interpolate(prog, [0.70, 0.85], [0.7, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(0.6)) });
  const ddakPulse = ddakOp > 0.9 ? Math.sin(f * 0.08) * 0.05 + 1 : 1;

  // 가이드 자막
  const guideOp = interpolate(prog, [0.55, 0.65], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: '#000000', opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: Math.sin(f * 0.04) * 0.025 + 0.04, pointerEvents: 'none',
      }} />

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 30, right: 50,
        color: C.textSub, fontSize: 18, fontWeight: 600, letterSpacing: 3,
        opacity: timeOp, zIndex: 100,
      }}>SAMPLE B4 · 08:00 DASHBOARD</div>

      {/* 좌상단 시간 */}
      <div style={{
        position: 'absolute', top: 40, left: 60,
        opacity: timeOp, zIndex: 100,
      }}>
        <div style={{ color: C.textSub, fontSize: 16, fontWeight: 500, letterSpacing: 4, marginBottom: 4 }}>NOW</div>
        <div style={{
          color: C.main, fontSize: 72, fontWeight: 900,
          fontFamily: '"Consolas", "Menlo", monospace',
          textShadow: GLOW.mid.text, letterSpacing: 2, lineHeight: 1,
        }}>08:00</div>
      </div>

      {/* 마우스 커서 */}
      {cursorOp > 0.01 && (
        <div style={{
          position: 'absolute', left: cursorX, top: cursorY,
          width: 32, height: 32, opacity: cursorOp,
          pointerEvents: 'none', zIndex: 200,
        }}>
          <svg width={32} height={32} viewBox="0 0 24 24">
            <path d="M2 2 L2 18 L7 14 L10 22 L13 21 L10 13 L17 13 Z"
              fill="#FFFFFF" stroke="#000000" strokeWidth={1.2} />
          </svg>
        </div>
      )}

      {/* 클릭 임팩트 링 */}
      {clickPulse > 0.01 && (
        <div style={{
          position: 'absolute', left: 944, top: 524,
          width: 32, height: 32, borderRadius: '50%',
          border: `3px solid ${C.main}`,
          transform: `scale(${1 + clickPulse * 6})`,
          opacity: 1 - clickPulse,
          boxShadow: GLOW.strong.box,
          pointerEvents: 'none', zIndex: 195,
        }} />
      )}

      {/* === 대시보드 본체 === */}
      <div style={{
        position: 'absolute',
        left: 100, top: 80, width: 1720, height: 900,
        background: '#0A0F0E',
        border: `2px solid ${C.borderActive}`,
        borderRadius: 20,
        opacity: dashOp,
        transform: `scale(${dashScale})`,
        transformOrigin: 'center center',
        boxShadow: GLOW.strong.box,
        overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* 상단 헤더 */}
        <div style={{
          padding: '24px 40px',
          borderBottom: `1px solid rgba(0,255,208,0.15)`,
          background: 'linear-gradient(180deg, rgba(0,255,208,0.06) 0%, transparent 100%)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              background: C.main, display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#000', fontSize: 24, fontWeight: 900,
              boxShadow: GLOW.mid.box,
            }}>S</div>
            <div>
              <div style={{
                color: C.main, fontSize: 30, fontWeight: 900, letterSpacing: 4,
                textShadow: GLOW.mid.text,
              }}>STOCK BRAIN</div>
              <div style={{ color: C.textSub, fontSize: 14, fontWeight: 500, letterSpacing: 2 }}>
                2026-05-27 (화) · 08:00 · KOSPI 2,847 (+0.42%)
              </div>
            </div>
          </div>
          <div style={{
            display: 'flex', gap: 12, alignItems: 'center',
          }}>
            <div style={{
              padding: '8px 18px', background: 'rgba(0,255,208,0.1)',
              border: `1px solid ${C.main}`, borderRadius: 8,
              color: C.main, fontSize: 14, fontWeight: 700,
            }}>● LIVE</div>
            <div style={{ color: C.textSub, fontSize: 14 }}>새벽 4시 기준 312건 누적</div>
          </div>
        </div>

        {/* 본문 — 좌(탑픽) + 우(섹터·일정) */}
        <div style={{ flex: 1, display: 'flex', gap: 24, padding: 28 }}>

          {/* 좌측: 오늘의 탑픽 3종목 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
              marginBottom: 4,
            }}>
              <div style={{
                color: C.textPrimary, fontSize: 22, fontWeight: 800, letterSpacing: 4,
              }}>🎯 오늘의 탑픽</div>
              <div style={{ color: C.textSub, fontSize: 14 }}>점수 기준 정렬 · 최대 9점</div>
            </div>

            {TOP_PICKS.map((p, i) => {
              const a = cardAnim(i);
              return (
                <div key={i} style={{
                  background: i === 0 ? 'rgba(0,255,208,0.04)' : '#0F1413',
                  border: `1px solid ${i === 0 ? C.borderActive : C.borderSub}`,
                  borderRadius: 14,
                  padding: '20px 24px',
                  opacity: a.op, transform: `translateY(${a.ty}px)`,
                  display: 'flex', gap: 20, alignItems: 'center',
                  boxShadow: i === 0 ? GLOW.weak.box : undefined,
                }}>
                  {/* 좌측 랭킹 + 점수 */}
                  <div style={{
                    width: 80, textAlign: 'center', flexShrink: 0,
                  }}>
                    <div style={{ color: C.textSub, fontSize: 14, fontWeight: 700, letterSpacing: 2 }}>#{p.rank}</div>
                    <div style={{
                      color: C.main, fontSize: 56, fontWeight: 900, lineHeight: 1,
                      textShadow: i === 0 ? GLOW.mid.text : GLOW.weak.text,
                      fontFamily: '"Consolas", "Menlo", monospace',
                    }}>{p.score}</div>
                    <div style={{ color: C.textSub, fontSize: 11, fontWeight: 600 }}>/ 9</div>
                  </div>

                  {/* 중앙 종목 정보 */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4,
                    }}>
                      <div style={{ color: C.textPrimary, fontSize: 28, fontWeight: 800 }}>{p.name}</div>
                      <div style={{ color: C.textSub, fontSize: 14, fontWeight: 500 }}>{p.code}</div>
                      <div style={{ color: C.textSub, fontSize: 13 }}>· {p.sector} · {p.subsector}</div>
                    </div>
                    <div style={{
                      display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap',
                    }}>
                      {p.badges.map((b, j) => (
                        <div key={j} style={{
                          padding: '3px 9px', borderRadius: 4,
                          background: 'rgba(0,255,208,0.1)',
                          border: `1px solid rgba(0,255,208,0.3)`,
                          color: C.main, fontSize: 12, fontWeight: 700,
                        }}>{b}</div>
                      ))}
                    </div>
                    <div style={{ color: C.textSub, fontSize: 14, fontWeight: 500, lineHeight: 1.4 }}>
                      {p.why}
                    </div>
                  </div>

                  {/* 우측 가격 */}
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ color: C.textPrimary, fontSize: 26, fontWeight: 800, fontFamily: '"Consolas", "Menlo", monospace' }}>
                      ₩{p.price}
                    </div>
                    <div style={{ color: '#FF4336', fontSize: 18, fontWeight: 700, marginTop: 2 }}>
                      ▲ {p.change}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 우측: 섹터 온도 + 일정 (350px) */}
          <div style={{
            width: 360, display: 'flex', flexDirection: 'column', gap: 16,
            opacity: sideOp,
          }}>
            {/* 섹터 온도 */}
            <div style={{
              background: '#0F1413', border: `1px solid ${C.borderSub}`,
              borderRadius: 14, padding: '18px 20px',
            }}>
              <div style={{ color: C.textPrimary, fontSize: 17, fontWeight: 800, letterSpacing: 3, marginBottom: 14 }}>
                🌡 섹터 온도
              </div>
              {SECTORS.map((s, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10,
                }}>
                  <div style={{ fontSize: 18, width: 24 }}>{s.temp}</div>
                  <div style={{ color: C.textPrimary, fontSize: 16, fontWeight: 600, flex: 1 }}>{s.name}</div>
                  <div style={{
                    width: 100, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden',
                  }}>
                    <div style={{
                      width: `${s.score}%`, height: '100%',
                      background: s.score > 75 ? C.main : s.score > 60 ? '#FFA500' : '#FFD700',
                      boxShadow: s.score > 75 ? '0 0 8px rgba(0,255,208,0.6)' : undefined,
                    }} />
                  </div>
                  <div style={{
                    color: C.main, fontSize: 13, fontWeight: 700, width: 30, textAlign: 'right',
                    fontFamily: '"Consolas", "Menlo", monospace',
                  }}>{s.score}</div>
                </div>
              ))}
            </div>

            {/* 임박 이벤트 */}
            <div style={{
              background: '#0F1413', border: `1px solid ${C.borderSub}`,
              borderRadius: 14, padding: '18px 20px', flex: 1,
            }}>
              <div style={{ color: C.textPrimary, fontSize: 17, fontWeight: 800, letterSpacing: 3, marginBottom: 14 }}>
                📅 임박 이벤트
              </div>
              {EVENTS.map((e, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12,
                  paddingBottom: 12,
                  borderBottom: i < EVENTS.length - 1 ? `1px solid rgba(255,255,255,0.04)` : 'none',
                }}>
                  <div style={{
                    width: 56, padding: '4px 0', borderRadius: 6,
                    background: 'rgba(0,255,208,0.1)',
                    border: `1px solid rgba(0,255,208,0.3)`,
                    color: C.main, fontSize: 14, fontWeight: 800, textAlign: 'center',
                    fontFamily: '"Consolas", "Menlo", monospace',
                  }}>{e.date}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: C.textPrimary, fontSize: 14, fontWeight: 600 }}>{e.text}</div>
                    <div style={{ color: C.textSub, fontSize: 11, marginTop: 2 }}>{e.tag}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 우측 가이드 자막 (대시보드 위 오버레이) */}
      <div style={{
        position: 'absolute', left: 60, bottom: 60, width: 360,
        opacity: guideOp,
        background: 'rgba(0,0,0,0.7)', borderRadius: 12, padding: 22,
        backdropFilter: 'blur(8px)',
      }}>
        <div style={{
          color: C.main, fontSize: 18, fontWeight: 800, letterSpacing: 3,
          marginBottom: 10,
        }}>이게 다 어디서 왔나</div>
        <div style={{
          color: C.textPrimary, fontSize: 16, fontWeight: 500,
          lineHeight: 1.7,
        }}>
          • 04:12 텔레방 SK하이닉스 메시지<br />
          • 05:00 Claude 분류·교차분석<br />
          • 06:00 위키 자동 누적<br />
          • 08:00 점수 매겨 한 장에 정렬
        </div>
      </div>

      {/* 딸깍 자막 */}
      <div style={{
        position: 'absolute', bottom: 60, right: 80,
        textAlign: 'right',
        opacity: ddakOp,
        transform: `scale(${ddakScale * ddakPulse})`,
        transformOrigin: 'right bottom',
        zIndex: 150,
      }}>
        <div style={{
          color: C.textSub, fontSize: 22, fontWeight: 600, letterSpacing: 6,
          marginBottom: 4,
        }}>한 번의 클릭</div>
        <div style={{
          color: C.main, fontSize: 140, fontWeight: 900, letterSpacing: 12,
          textShadow: GLOW.strong.text, lineHeight: 1,
        }}>딸깍</div>
      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 20, left: 0, right: 0,
        textAlign: 'center', opacity: timeOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 24, fontWeight: 700, opacity: 0.5 }}>
          STAGE 4 · 의사결정
        </div>
      </div>

    </AbsoluteFill>
  );
};
