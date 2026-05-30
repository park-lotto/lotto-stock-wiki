// AG04 — 씬7 여운 (30초 / 900프레임)
// AG02 구조도 흐릿 + "?" 오버레이 → "다음 편: 실제 설계 공개" 예고
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

const WORKERS = [
  { name: '수집 직원',   role: '뉴스 · 리포트',     icon: '📡', col: C.main    },
  { name: '미국장 직원', role: '나스닥 · 섹터 ETF', icon: '🇺🇸', col: '#FFA502' },
  { name: '리포트 직원', role: '증권사 리포트',      icon: '📄', col: '#9ca3af' },
  { name: '수급 직원',   role: '500종목 스캔',       icon: '🔍', col: C.main    },
  { name: '투경 직원',   role: '투자경고 모니터링', icon: '⚠️', col: '#FFA502' },
  { name: '분석 직원',   role: '8개 기준 교차',      icon: '📊', col: C.main    },
  { name: '탑픽 직원',   role: '탑픽 자동 선정',    icon: '🎯', col: '#FF4757' },
  { name: '브리핑 직원', role: '아침 노트 생성',     icon: '📋', col: C.main    },
  { name: '검증 직원',   role: '팩트체크',           icon: '✅', col: '#9ca3af' },
  { name: '배포 직원',   role: '텔레그램 전송',      icon: '📨', col: C.main    },
];

export const AG04_Tease: React.FC = () => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 20);
  const timeOp = ip(f, 10, 30);

  // ── 배경 구조도 흐릿하게 페이드인 (f0~80)
  const bgTeamOp = ip(f, 0, 80, 0, 0.18);   // 최대 투명도 18% (블러 느낌)

  // ── 블러 강도 감소 (시작엔 완전 블러, 중반부터 살짝 보임)
  // CSS filter로는 Remotion에서 잘 작동하나, 대신 opacity + 검은 오버레이로 처리
  const blurOverlayOp = ip(f, 0, 60, 0.85, 0.72);  // 상시 거의 가림

  // ── "?" 오버레이 등장 (f80~130)
  const qOp    = ip(f, 80, 130);
  const qScale = interpolate(f, [80, 130], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.7)),
  });
  const qPulse = qOp > 0.97 ? 1 + Math.sin(f * 0.06) * 0.04 : 1;

  // ── "이 시스템" 텍스트 (f140~185)
  const t1Op = ip(f, 140, 180);
  const t1Y  = interpolate(f, [140, 180], [40, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── "어떻게 설계됐는지 궁금하시죠?" (f210~260)
  const t2Op = ip(f, 210, 255);
  const t2Y  = interpolate(f, [210, 255], [40, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // ── 연결선 힌트 draw-on (f290~380)
  const lineProg = ip(f, 290, 380);

  // ── "다음 영상에서 전부 보여드리겠습니다" (f460~530)
  const nextOp    = ip(f, 460, 520);
  const nextScale = interpolate(f, [460, 520], [0.6, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.6)),
  });
  const nextPulse = nextOp > 0.95 ? 1 + Math.sin(f * 0.08) * 0.022 : 1;

  // ── "다음 편" 태그 (f560~610)
  const tagOp    = ip(f, 560, 605);
  const tagScale = interpolate(f, [560, 605], [0.5, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(2.0)),
  });

  // 배경 글로우
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;

  // 카드 레이아웃 상수 (AG02와 동일)
  const PAD_X   = 80;
  const BOSS_H  = 120;
  const BOSS_Y  = 70;
  const BOSS_W  = 700;
  const GRID_Y  = BOSS_Y + BOSS_H + 38;
  const GRID_H  = 1080 - GRID_Y - 60;
  const COLS    = 2;
  const ROWS    = 5;
  const COL_GAP = 36;
  const CARD_W  = (1920 - PAD_X * 2 - COL_GAP) / COLS;
  const CARD_H  = (GRID_H - (ROWS - 1) * 14) / ROWS;
  const ROW_GAP = 14;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse at 50% 40%, rgba(0,255,208,1) 0%, transparent 65%)`,
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* ── 배경: 구조도 희미하게 (AG02 레이아웃 재현, 흐림) ── */}
      <div style={{ position: 'absolute', inset: 0, opacity: bgTeamOp }}>

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
                stroke="rgba(0,255,208,0.30)"
                strokeWidth={1.5}
                strokeDasharray="9 6"
              />
            );
          })}
        </svg>

        {/* 보스 카드 희미하게 */}
        <div style={{
          position: 'absolute',
          left: 960 - BOSS_W / 2, top: BOSS_Y,
          width: BOSS_W, height: BOSS_H,
          background: 'rgba(0,255,208,0.06)',
          border: '2px solid rgba(0,255,208,0.20)',
          borderRadius: 22,
          display: 'flex', alignItems: 'center', gap: 24, padding: '0 32px',
        }}>
          <div style={{
            width: 66, height: 66, borderRadius: 16,
            background: 'rgba(0,255,208,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 32,
          }}>🧠</div>
          <div style={{
            color: 'rgba(0,255,208,0.5)', fontSize: 36, fontWeight: 900, letterSpacing: 6,
          }}>총괄</div>
        </div>

        {/* 직원 카드 희미하게 */}
        {WORKERS.map((w, i) => {
          const col = i % COLS;
          const row = Math.floor(i / COLS);
          return (
            <div key={i} style={{
              position: 'absolute',
              left: PAD_X + col * (CARD_W + COL_GAP),
              top: GRID_Y + row * (CARD_H + ROW_GAP),
              width: CARD_W, height: CARD_H,
              background: 'rgba(255,255,255,0.025)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 18,
              display: 'flex', alignItems: 'center', gap: 22, padding: '0 28px',
            }}>
              <span style={{ fontSize: 28, flexShrink: 0 }}>{w.icon}</span>
              <div style={{ fontSize: 22, color: 'rgba(255,255,255,0.25)', fontWeight: 600 }}>{w.name}</div>
            </div>
          );
        })}
      </div>

      {/* 블러 오버레이 — 구조도 가림 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: '#080c14',
        opacity: blurOverlayOp,
        pointerEvents: 'none',
      }} />

      {/* ── "?" 중앙 오버레이 ── */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: qOp,
        transform: `scale(${qScale * qPulse})`,
        transformOrigin: 'center',
        pointerEvents: 'none',
      }}>
        <div style={{
          fontSize: 280, fontWeight: 900, lineHeight: 1,
          color: C.main, textShadow: GLOW.strong.text,
          userSelect: 'none',
        }}>?</div>
      </div>

      {/* ── 텍스트 콘텐츠 ── */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        gap: 28,
        paddingTop: 100,  // "?" 아래쪽 공간 활용
      }}>

        {/* "이 시스템." */}
        <div style={{
          opacity: t1Op,
          transform: `translateY(${t1Y}px)`,
          fontSize: 72, fontWeight: 900, color: '#e5e7eb',
          textAlign: 'center', marginTop: 200,
        }}>이 시스템.</div>

        {/* "어떻게 설계됐는지 궁금하시죠?" */}
        <div style={{
          opacity: t2Op,
          transform: `translateY(${t2Y}px)`,
          fontSize: 42, fontWeight: 600, color: '#9ca3af',
          textAlign: 'center', lineHeight: 1.5,
        }}>
          총괄이 직원들에게 어떻게 지시를 내리는지.<br />
          직원들이 서로 어떻게 정보를 넘기는지.
        </div>

        {/* "다음 영상에서 전부 보여드리겠습니다" */}
        <div style={{
          opacity: nextOp,
          transform: `scale(${nextScale * nextPulse})`,
          transformOrigin: 'center',
          textAlign: 'center', marginTop: 12,
        }}>
          <div style={{
            fontSize: 56, fontWeight: 900,
            color: C.main, textShadow: GLOW.mid.text,
          }}>실제 설계 구조.</div>
          <div style={{
            fontSize: 44, fontWeight: 700, color: '#e5e7eb', marginTop: 10,
          }}>다음 영상에서 전부 보여드리겠습니다.</div>
        </div>

        {/* "다음 편" 배지 */}
        <div style={{
          opacity: tagOp,
          transform: `scale(${tagScale})`,
          transformOrigin: 'center',
          marginTop: 16,
          display: 'flex', alignItems: 'center', gap: 20,
          padding: '16px 44px',
          background: `${C.main}14`,
          border: `1.5px solid ${C.main}40`,
          borderRadius: 50,
        }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: C.main, boxShadow: GLOW.weak.box }} />
          <div style={{
            color: C.main, fontSize: 26, fontWeight: 800, letterSpacing: 4,
            textShadow: GLOW.weak.text,
          }}>다음 편 · 실제 설계 공개</div>
        </div>
      </div>

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>SCENE 7 · 여운</div>

      {/* 하단 */}
      <div style={{
        position: 'absolute', bottom: 18, left: 0, right: 0,
        textAlign: 'center', opacity: timeOp,
      }}>
        <div style={{ color: '#374151', fontSize: 18, fontWeight: 600, letterSpacing: 4 }}>
          SCENE 7 · 여운 · 다음 편 예고
        </div>
      </div>

    </AbsoluteFill>
  );
};
