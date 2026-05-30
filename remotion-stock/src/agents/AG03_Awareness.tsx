// AG03 — 씬6 자각 (40초 / 1200프레임)
// "매일 얼마나 쓰세요?" → 한 장짜리 브리핑만 → 오늘 뭘 살지 결정합니다
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

function ip(
  f: number,
  a: number,
  b: number,
  from = 0,
  to = 1,
  ease: (t: number) => number = Easing.out(Easing.cubic),
) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });
}

// ── Part 1 (f0~450): "매일 얼마나 쓰세요?" 질문 씬 ──────────────────
// ── Part 2 (f450~900): 브리핑 한 장 씬 ─────────────────────────────
// ── Part 3 (f900~1200): 결론 자막 씬 ───────────────────────────────

const TIME_ITEMS = [
  { icon: '📱', label: '텔레방 3개 탭탭탭',   time: '15분', color: '#6b7280' },
  { icon: '📰', label: '증권사 앱 뉴스 스크롤', time: '20분', color: '#6b7280' },
  { icon: '▶️', label: '유튜브 시황 영상',      time: '25분', color: '#6b7280' },
];

const TOTAL_MIN = 60;

export const AG03_Awareness: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 20);

  // ── 파트 전환 페이드 ──────────────────────────────────────────────
  const part1Op = ip(f, 0, 20) * (1 - ip(f, 400, 440));
  const part2Op = ip(f, 440, 480) * (1 - ip(f, 840, 880));
  const part3Op = ip(f, 880, 920);

  const timeOp = ip(f, 10, 30);

  // ━━━━ PART 1: 질문 씬 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  // 질문 타이틀 (f20~80)
  const q1Y  = interpolate(f, [20, 60], [50, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const q1Op = ip(f, 20, 60);

  // 항목 순차 등장 (f80, f150, f220 — 70프레임 간격)
  const itemFrames = [80, 150, 220];
  const itemAnim = (i: number) => {
    const s = itemFrames[i];
    return {
      op:    ip(f, s, s + 28),
      tx:    interpolate(f, [s, s + 28], [-60, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) }),
      scale: interpolate(f, [s, s + 28], [0.88, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.4)) }),
    };
  };

  // 합계 카운트업 (f280~360)
  const totalVal   = Math.round(ip(f, 280, 360, 0, TOTAL_MIN));
  const totalOp    = ip(f, 280, 320);
  const totalPulse = totalOp > 0.95 ? 1 + Math.sin(f * 0.1) * 0.018 : 1;

  // "저는 이 시간을 안 씁니다" (f370~420)
  const noTimeOp = ip(f, 370, 410);
  const noTimeY  = interpolate(f, [370, 410], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ━━━━ PART 2: 브리핑 한 장 씬 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  // 카드 4개 — 섹터온도 / 탑픽 / 매크로 / 오늘일정
  const BRIEF_CARDS = [
    { icon: '🌡️', title: '섹터 온도',   sub: '반도체 🔴 · 방산 🔴 · 조선 🟠',      col: C.main    },
    { icon: '🎯', title: '오늘의 탑픽', sub: '삼성전기 7/9점 — 매수 구간',           col: '#FF4757' },
    { icon: '🌐', title: '매크로 한 줄', sub: 'VIX 16↓ · 달러 104 · 코스닥↑',      col: '#FFA502' },
    { icon: '📅', title: '오늘 일정',   sub: 'ASCO 2026 바이오 · FOMC -16일',       col: '#9ca3af' },
  ];
  const briefStart = [480, 570, 660, 750];
  const briefAnim = (i: number) => {
    const s = briefStart[i];
    return {
      op:    ip(f, s, s + 36),
      ty:    interpolate(f, [s, s + 36], [40, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.6)) }),
    };
  };

  // "한 장만 보면 돼요" 클라이맥스 (f820~880)
  const onePageOp    = ip(f, 820, 860);
  const onePageScale = interpolate(f, [820, 860], [0.6, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.65)),
  });
  const onePagePulse = onePageOp > 0.95 ? 1 + Math.sin(f * 0.08) * 0.022 : 1;

  // ━━━━ PART 3: 결론 자막 씬 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  // Line1 좌에서 슬라이드 (f920~960)
  const c1X  = interpolate(f, [920, 960], [-120, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const c1Op = ip(f, 920, 960);

  // Line2 우에서 슬라이드 (f960~1000)
  const c2X  = interpolate(f, [960, 1000], [120, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const c2Op = ip(f, 960, 1000);

  // 결론 민트 텍스트 (f1010~1060)
  const c3Scale = interpolate(f, [1010, 1060], [0.5, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(1.1)),
  });
  const c3Op = ip(f, 1010, 1060);
  const c3Pulse = c3Op > 0.95 ? 1 + Math.sin(f * 0.09) * 0.025 : 1;

  // 글로우 펄스
  const pulse    = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz      = interpolate(pulse, [0, 1], [10, 32]);
  const dynGlow  = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5), 0 0 ${gSz * 4}px rgba(0,191,154,0.25)`;
  const bgGlow   = Math.sin(f * 0.04) * 0.03 + 0.045;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)`,
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 씬 라벨 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 6 · 자각</div>

      {/* ━━━━ PART 1: 질문 씬 ━━━━ */}
      {part1Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: part1Op,
        }}>

          {/* 질문 타이틀 */}
          <div style={{
            opacity: q1Op,
            transform: `translateY(${q1Y}px)`,
            textAlign: 'center', marginBottom: 60,
          }}>
            <div style={{ color: '#4b5563', fontSize: 22, fontWeight: 600, letterSpacing: 6, marginBottom: 16 }}>
              EVERY MORNING
            </div>
            <div style={{
              fontSize: 72, fontWeight: 900, color: '#e5e7eb', lineHeight: 1.2,
            }}>
              매일 아침<br />
              <span style={{ color: C.main, textShadow: GLOW.mid.text }}>얼마나</span> 쓰세요?
            </div>
          </div>

          {/* 항목 리스트 */}
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 20,
            width: 800, marginBottom: 50,
          }}>
            {TIME_ITEMS.map((item, i) => {
              const { op, tx, scale } = itemAnim(i);
              return (
                <div key={i} style={{
                  opacity: op,
                  transform: `translateX(${tx}px) scale(${scale})`,
                  display: 'flex', alignItems: 'center', gap: 24,
                  background: 'rgba(255,255,255,0.035)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 18, padding: '20px 32px',
                }}>
                  <span style={{ fontSize: 36, flexShrink: 0 }}>{item.icon}</span>
                  <div style={{ flex: 1, fontSize: 24, fontWeight: 600, color: '#9ca3af' }}>
                    {item.label}
                  </div>
                  <div style={{
                    fontSize: 30, fontWeight: 900,
                    fontFamily: '"Consolas","Menlo",monospace',
                    color: '#6b7280',
                  }}>{item.time}</div>
                </div>
              );
            })}
          </div>

          {/* 합계 카운트업 */}
          <div style={{
            opacity: totalOp,
            transform: `scale(${totalPulse})`,
            textAlign: 'center',
          }}>
            <div style={{ color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 5, marginBottom: 8 }}>
              합산
            </div>
            <div style={{
              fontSize: 130, fontWeight: 900, lineHeight: 1,
              fontFamily: '"Consolas","Menlo",monospace',
              color: '#e5e7eb',
            }}>
              {String(totalVal).padStart(2, '0')}
              <span style={{ fontSize: 48, color: '#6b7280', marginLeft: 12 }}>분</span>
            </div>
          </div>

          {/* "저는 이 시간을 안 씁니다" */}
          <div style={{
            opacity: noTimeOp,
            transform: `translateY(${noTimeY}px)`,
            textAlign: 'center', marginTop: 40,
            padding: '16px 48px',
            background: `${C.main}0f`,
            border: `1px solid ${C.main}30`,
            borderRadius: 16,
          }}>
            <div style={{
              fontSize: 36, fontWeight: 800,
              color: C.main, textShadow: GLOW.weak.text,
            }}>저는 이제 이 시간을 안 씁니다</div>
          </div>
        </div>
      )}

      {/* ━━━━ PART 2: 브리핑 한 장 씬 ━━━━ */}
      {part2Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: part2Op,
          paddingInline: 160,
        }}>
          {/* 타이틀 */}
          <div style={{
            textAlign: 'center', marginBottom: 48,
            opacity: ip(f, 480, 510),
            transform: `translateY(${interpolate(f, [480, 510], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })}px)`,
          }}>
            <div style={{ color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 6, marginBottom: 12 }}>MORNING BRIEF</div>
            <div style={{ fontSize: 60, fontWeight: 900, color: '#e5e7eb' }}>
              한 장이에요.
            </div>
          </div>

          {/* 카드 2×2 그리드 */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 24,
            width: '100%',
            maxWidth: 1500,
          }}>
            {BRIEF_CARDS.map((card, i) => {
              const { op, ty } = briefAnim(i);
              return (
                <div key={i} style={{
                  opacity: op,
                  transform: `translateY(${ty}px)`,
                  padding: '32px 40px',
                  background: 'rgba(255,255,255,0.04)',
                  border: `1px solid ${card.col}25`,
                  borderRadius: 22,
                  display: 'flex', alignItems: 'center', gap: 28,
                }}>
                  <span style={{ fontSize: 52, flexShrink: 0 }}>{card.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: 26, fontWeight: 800,
                      color: card.col, marginBottom: 10,
                      textShadow: card.col === C.main ? GLOW.weak.text : undefined,
                    }}>{card.title}</div>
                    <div style={{ fontSize: 18, color: '#6b7280', lineHeight: 1.4 }}>{card.sub}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* "한 장만 보면 돼요" */}
          <div style={{
            opacity: onePageOp,
            transform: `scale(${onePageScale * onePagePulse})`,
            transformOrigin: 'center bottom',
            marginTop: 48, textAlign: 'center',
          }}>
            <div style={{
              fontSize: 56, fontWeight: 900,
              color: C.main, textShadow: dynGlow,
              letterSpacing: 2,
            }}>한 장만 보면 돼요</div>
          </div>
        </div>
      )}

      {/* ━━━━ PART 3: 결론 씬 ━━━━ */}
      {part3Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          opacity: part3Op,
          gap: 32,
        }}>
          {/* 스캔라인 */}
          {f >= 880 && f <= 918 && (() => {
            const scanY  = interpolate(f, [880, 918], [-2, 104], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            const scanOp = interpolate(f, [880, 885, 913, 918], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            return (
              <div style={{
                position: 'absolute', left: 0, right: 0,
                top: `${scanY}%`, height: 2,
                background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
                boxShadow: '0 0 10px rgba(0,255,208,0.9)',
                opacity: scanOp, zIndex: 10, pointerEvents: 'none',
              }} />
            );
          })()}

          {/* Line1 */}
          <div style={{
            opacity: c1Op,
            transform: `translateX(${c1X}px)`,
            fontSize: 72, fontWeight: 900, color: '#e5e7eb',
            textAlign: 'center',
          }}>
            커피 한 잔 마시면서
          </div>

          {/* Line2 */}
          <div style={{
            opacity: c2Op,
            transform: `translateX(${c2X}px)`,
            fontSize: 72, fontWeight: 900, color: '#e5e7eb',
            textAlign: 'center',
          }}>
            브리핑 한 장만 보고.
          </div>

          {/* 결론 민트 */}
          <div style={{
            opacity: c3Op,
            transform: `scale(${c3Scale * c3Pulse})`,
            transformOrigin: 'center',
            textAlign: 'center', marginTop: 24,
          }}>
            <div style={{
              fontSize: 88, fontWeight: 900,
              color: C.main, textShadow: dynGlow,
              lineHeight: 1.2,
            }}>오늘 뭘 살지 결정합니다.</div>
          </div>
        </div>
      )}

      {/* 하단 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '10%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ color: '#374151', fontSize: 18, fontWeight: 600, letterSpacing: 4, opacity: timeOp }}>
          SCENE 6 · 자각
        </div>
      </div>

    </AbsoluteFill>
  );
};
