// AG02 — AI 직원 10명 도식 (완전 재설계)
// 보스 상단 중앙 / 직원 2열 × 5행 화면 꽉 채움 / 카드 대형화
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 750;

const WORKERS = [
  { name: '수집 직원',   role: '뉴스 · 리포트 · 텔레그램 24시간',   icon: '📡', col: C.main    },
  { name: '미국장 직원', role: '나스닥 · SOX · 섹터 ETF 실시간',    icon: '🇺🇸', col: '#FFA502' },
  { name: '리포트 직원', role: '증권사 리포트 자동 분류 · 요약',     icon: '📄', col: '#9ca3af' },
  { name: '수급 직원',   role: '500종목 수급 빈집 오실레이터',       icon: '🔍', col: C.main    },
  { name: '투경 직원',   role: '투자경고 해제 조건 모니터링',        icon: '⚠️', col: '#FFA502' },
  { name: '분석 직원',   role: '8개 탑픽 기준 교차 분석',           icon: '📊', col: C.main    },
  { name: '탑픽 직원',   role: '오늘의 탑픽 자동 선정',             icon: '🎯', col: '#FF4757' },
  { name: '브리핑 직원', role: '아침 노트 HTML 자동 생성',           icon: '📋', col: C.main    },
  { name: '검증 직원',   role: '팩트체크 · 오류 제거',              icon: '✅', col: '#9ca3af' },
  { name: '배포 직원',   role: '텔레그램 자동 전송 완료',            icon: '📨', col: C.main    },
];

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease,
  });
}

export const AG02_Agents: React.FC = () => {
  const f    = useCurrentFrame();
  const prog = ip(f, 15, DUR - 60);
  const fadeIn = ip(f, 0, 24);

  // ── 보스 등장 (0 ~ 0.15)
  const bossOp    = ip(prog, 0, 0.13);
  const bossScale = interpolate(prog, [0, 0.13], [0.25, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(2.4)),
  });
  const bossPulse = Math.sin(f * 0.07) * 0.5 + 0.5;

  // ── 연결선 (0.15 ~ 0.30)
  const lineProg = ip(prog, 0.15, 0.32);

  // ── 직원 스태거 (0.30 ~ 0.82) — 80프레임 간격
  const workerAnim = (i: number) => {
    const start = 0.30 + i * 0.050;
    return {
      op:    ip(prog, start, start + 0.08),
      scale: interpolate(prog, [start, start + 0.08], [0.55, 1], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
        easing: Easing.out(Easing.back(1.5)),
      }),
      ty: interpolate(prog, [start, start + 0.08], [30, 0], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
        easing: Easing.out(Easing.cubic),
      }),
    };
  };

  // ── ₩0 클라이맥스 (0.85 ~ 0.96)
  const salaryOp    = ip(prog, 0.85, 0.95);
  const salaryScale = interpolate(prog, [0.85, 0.95], [0.15, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.55)),
  });
  const salaryPulse = salaryOp > 0.97 ? 1 + Math.sin(f * 0.09) * 0.025 : 1;

  const timeOp = ip(f, 10, 30);

  // ── 레이아웃 상수 (화면 꽉 채우기)
  const PAD_X   = 80;   // 좌우 여백
  const BOSS_H  = 120;
  const BOSS_Y  = 70;
  const BOSS_W  = 700;

  const GRID_Y  = BOSS_Y + BOSS_H + 38;
  const GRID_H  = 1080 - GRID_Y - 60;   // 하단 여백 60
  const ROWS    = 5;
  const COLS    = 2;
  const COL_GAP = 36;
  const CARD_W  = (1920 - PAD_X * 2 - COL_GAP) / COLS;   // ≈842
  const CARD_H  = (GRID_H - (ROWS - 1) * 14) / ROWS;     // ≈148
  const ROW_GAP = 14;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 30%, rgba(0,255,208,0.055) 0%, transparent 58%)',
        pointerEvents: 'none',
      }} />

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 3 · AI 직원 팀</div>

      {/* 좌상단 */}
      <div style={{ position: 'absolute', top: 30, left: 60, opacity: timeOp }}>
        <div style={{ color: '#4b5563', fontSize: 13, fontWeight: 600, letterSpacing: 5, marginBottom: 4 }}>STOCK BRAIN</div>
        <div style={{
          color: C.main, fontSize: 52, fontWeight: 900,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: GLOW.mid.text, letterSpacing: 3, lineHeight: 1,
        }}>AI TEAM</div>
      </div>

      {/* SVG 연결선 */}
      <svg style={{ position: 'absolute', inset: 0, width: 1920, height: 1080, pointerEvents: 'none' }}>
        {WORKERS.map((_, i) => {
          const col = i % COLS;
          const row = Math.floor(i / COLS);
          const wx  = PAD_X + col * (CARD_W + COL_GAP) + CARD_W / 2;
          const wy  = GRID_Y + row * (CARD_H + ROW_GAP) + CARD_H / 2;
          const x1  = 960;
          const y1  = BOSS_Y + BOSS_H;
          const r   = Math.min(1, lineProg);
          return (
            <line key={i}
              x1={x1} y1={y1}
              x2={x1 + (wx - x1) * r} y2={y1 + (wy - y1) * r}
              stroke="rgba(0,255,208,0.10)"
              strokeWidth={1.5}
              strokeDasharray="9 6"
            />
          );
        })}
      </svg>

      {/* 보스 카드 — 중앙, 네온 강하게 */}
      <div style={{
        position: 'absolute',
        left: 960 - BOSS_W / 2, top: BOSS_Y,
        width: BOSS_W, height: BOSS_H,
        opacity: bossOp, transform: `scale(${bossScale})`,
        transformOrigin: 'center center',
      }}>
        <div style={{
          width: '100%', height: '100%',
          background: `rgba(0,255,208,${0.07 + bossPulse * 0.05})`,
          border: `2.5px solid ${C.main}`,
          borderRadius: 22,
          display: 'flex', alignItems: 'center', gap: 24, padding: '0 32px',
          boxShadow: `0 0 ${32 + bossPulse * 28}px rgba(0,255,208,${0.45 + bossPulse * 0.2})`,
        }}>
          <div style={{
            width: 66, height: 66, borderRadius: 16,
            background: C.main,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 32, flexShrink: 0, boxShadow: GLOW.mid.box,
          }}>🧠</div>
          <div style={{ flex: 1 }}>
            <div style={{
              color: C.main, fontSize: 36, fontWeight: 900, letterSpacing: 6,
              textShadow: GLOW.mid.text,
            }}>총괄</div>
            <div style={{ color: '#6b7280', fontSize: 17, fontWeight: 500, marginTop: 4 }}>
              지시 · 취합 · 조율
            </div>
          </div>
          <div style={{
            color: '#4b5563', fontSize: 13, fontWeight: 700, letterSpacing: 2,
            padding: '6px 16px', borderRadius: 8,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}>ORCHESTRATOR</div>
        </div>
      </div>

      {/* 직원 카드 2열 × 5행 — 화면 꽉 채움 */}
      {WORKERS.map((w, i) => {
        const { op, scale, ty } = workerAnim(i);
        const col = i % COLS;
        const row = Math.floor(i / COLS);
        const x   = PAD_X + col * (CARD_W + COL_GAP);
        const y   = GRID_Y + row * (CARD_H + ROW_GAP);
        const isTopPick = w.name === '탑픽 직원';

        return (
          <div key={i} style={{
            position: 'absolute',
            left: x, top: y, width: CARD_W, height: CARD_H,
            opacity: op,
            transform: `scale(${scale}) translateY(${ty}px)`,
            transformOrigin: 'center top',
          }}>
            <div style={{
              width: '100%', height: '100%',
              background: isTopPick ? 'rgba(255,71,87,0.07)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${isTopPick ? 'rgba(255,71,87,0.35)' : 'rgba(255,255,255,0.09)'}`,
              borderRadius: 18,
              display: 'flex', alignItems: 'center', gap: 22, padding: '0 28px',
            }}>
              {/* 아이콘 */}
              <div style={{
                width: 58, height: 58, borderRadius: 14,
                background: `${w.col}18`,
                border: `1px solid ${w.col}35`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 28, flexShrink: 0,
              }}>{w.icon}</div>

              {/* 텍스트 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 24, fontWeight: 700,
                  color: isTopPick ? '#FF4757' : '#e5e7eb',
                  marginBottom: 6,
                }}>{w.name}</div>
                <div style={{
                  fontSize: 16, color: '#4b5563', lineHeight: 1.3,
                }}>{w.role}</div>
              </div>

              {/* 상태 점 */}
              <div style={{
                width: 10, height: 10, borderRadius: '50%',
                background: w.col, flexShrink: 0,
                boxShadow: isTopPick ? `0 0 10px ${w.col}88` : undefined,
              }} />
            </div>
          </div>
        );
      })}

      {/* ₩0 클라이맥스 */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'flex-end',
        paddingBottom: 56, pointerEvents: 'none',
        opacity: salaryOp,
        transform: `scale(${salaryScale * salaryPulse})`,
        transformOrigin: 'center bottom',
      }}>
        <div style={{
          color: '#6b7280', fontSize: 26, fontWeight: 600, letterSpacing: 8, marginBottom: 4,
        }}>퇴근 없음 · 불평 없음 · 인건비</div>
        <div style={{
          color: C.main, fontSize: 140, fontWeight: 900, letterSpacing: 6,
          fontFamily: '"Consolas","Menlo",monospace', lineHeight: 1,
          textShadow: GLOW.strong.text,
        }}>₩0</div>
      </div>

      {/* 하단 */}
      <div style={{
        position: 'absolute', bottom: 20, left: 0, right: 0,
        textAlign: 'center', opacity: ip(f, 10, 30),
      }}>
        <div style={{ color: '#374151', fontSize: 18, fontWeight: 600, letterSpacing: 4 }}>
          SCENE 3 · AI 직원 팀 선언
        </div>
      </div>

    </AbsoluteFill>
  );
};
