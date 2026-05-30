// AG02 — AI 직원 10명 도식 씬 (씬3 선언 구간)
// 총괄이 먼저 등장 → 직원 10명이 하나씩 펼쳐짐
// 20초 = 600프레임

import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
} from 'remotion';

const DUR = 600;

const C = {
  bg:      '#0a0e1a',
  panel:   '#111827',
  border:  '#1e2d45',
  mint:    '#00e5c3',
  mintDim: '#00b89a',
  red:     '#ff4757',
  yellow:  '#ffa502',
  gray:    '#4a5568',
  white:   '#f0f4f8',
  dim:     '#6b7280',
};

const BOSS = {
  name: '총괄',
  role: '지시 · 취합 · 조율',
  icon: '🧠',
  color: C.mint,
};

const WORKERS = [
  { name: '수집 직원',   role: '뉴스·리포트·텔레그램 24시간',  icon: '📡', color: C.mint },
  { name: '미국장 직원', role: '나스닥·SOX·섹터 ETF 추적',      icon: '🇺🇸', color: C.yellow },
  { name: '리포트 직원', role: '증권사 리포트 자동 분류·요약',   icon: '📄', color: C.mint },
  { name: '수급 직원',   role: '500종목 빈집 오실레이터 스캔',   icon: '🔍', color: C.mint },
  { name: '투경 직원',   role: '투자경고 해제 조건 모니터링',    icon: '⚠️', color: C.yellow },
  { name: '분석 직원',   role: '8개 탑픽 기준 교차 분석',        icon: '📊', color: C.mint },
  { name: '탑픽 직원',   role: '오늘의 탑픽 자동 선정',          icon: '🎯', color: C.red },
  { name: '브리핑 직원', role: '아침 노트 HTML 자동 생성',        icon: '📋', color: C.mint },
  { name: '검증 직원',   role: '팩트체크 · 오류 제거',           icon: '✅', color: C.mintDim },
  { name: '배포 직원',   role: '텔레그램 자동 전송 완료',         icon: '📨', color: C.mint },
];

function ease(f: number, a: number, b: number, from = 0, to = 1) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
}

export const AG02_Agents: React.FC = () => {
  const f = useCurrentFrame();

  const fadeIn = ease(f, 0, 20);

  // 총괄 등장
  const bossAppear = ease(f, 20, 45);
  const bossScale  = interpolate(f, [20, 45], [0.6, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.5)),
  });

  // 라인 draw-on (총괄 → 직원들)
  const lineProgress = ease(f, 50, 90);

  // 직원들 등장 (하나씩, 60~240프레임)
  const workerAppearFrames = WORKERS.map((_, i) => 70 + i * 38);

  // 월급 0원 텍스트
  const salaryAppear = ease(f, DUR - 80, DUR - 55);

  return (
    <AbsoluteFill
      style={{
        background: C.bg,
        opacity: fadeIn,
        fontFamily: "'Noto Sans KR', sans-serif",
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute',
        top: '20%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: 600,
        height: 300,
        background: `radial-gradient(ellipse, ${C.mint}0a 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      {/* 헤더 */}
      <div style={{
        marginTop: 40,
        fontSize: 18,
        color: C.dim,
        letterSpacing: '0.15em',
        textTransform: 'uppercase',
      }}>
        STOCK BRAIN — AI 직원 팀
      </div>

      {/* 총괄 카드 */}
      <div style={{
        marginTop: 32,
        opacity: bossAppear,
        transform: `scale(${bossScale})`,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}>
        <div style={{
          padding: '16px 40px',
          background: `${C.mint}15`,
          border: `2px solid ${C.mint}`,
          borderRadius: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          boxShadow: `0 0 30px ${C.mint}30`,
        }}>
          <span style={{ fontSize: 28 }}>{BOSS.icon}</span>
          <div>
            <div style={{ fontSize: 20, color: C.mint, fontWeight: 700 }}>
              {BOSS.name}
            </div>
            <div style={{ fontSize: 12, color: C.dim, marginTop: 2 }}>
              {BOSS.role}
            </div>
          </div>
        </div>

        {/* 총괄 → 직원 연결선 */}
        <div style={{
          width: 2,
          height: Math.round(lineProgress * 30),
          background: `linear-gradient(to bottom, ${C.mint}, ${C.mint}44)`,
          marginTop: 0,
        }} />
      </div>

      {/* 직원 그리드 — 2열 5행 */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '10px 20px',
        marginTop: 10,
        width: 860,
        opacity: lineProgress,
      }}>
        {WORKERS.map((w, i) => {
          const af = workerAppearFrames[i];
          const workerFade  = ease(f, af, af + 15);
          const workerSlide = interpolate(f, [af, af + 15], [12, 0], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });

          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 16px',
                background: `${C.panel}dd`,
                border: `1px solid ${w.color}30`,
                borderRadius: 10,
                opacity: workerFade,
                transform: `translateY(${workerSlide}px)`,
              }}
            >
              <span style={{ fontSize: 20, flexShrink: 0 }}>{w.icon}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 13,
                  color: C.white,
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}>
                  {w.name}
                </div>
                <div style={{
                  fontSize: 11,
                  color: C.dim,
                  marginTop: 2,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  {w.role}
                </div>
              </div>
              <div style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: w.color,
                flexShrink: 0,
                boxShadow: `0 0 6px ${w.color}`,
              }} />
            </div>
          );
        })}
      </div>

      {/* 월급 0원 */}
      <div style={{
        marginTop: 24,
        opacity: salaryAppear,
        display: 'flex',
        alignItems: 'center',
        gap: 20,
      }}>
        <div style={{ height: 1, width: 120, background: C.border }} />
        <span style={{
          fontSize: 16,
          color: C.dim,
          letterSpacing: '0.1em',
        }}>
          월급{' '}
          <span style={{ color: C.mint, fontWeight: 700 }}>0원</span>
          {' '} · 퇴근 없음 · 불평 없음
        </span>
        <div style={{ height: 1, width: 120, background: C.border }} />
      </div>
    </AbsoluteFill>
  );
};
