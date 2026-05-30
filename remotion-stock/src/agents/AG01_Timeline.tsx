// AG01 — 24시간 타임라인 (7개 이벤트 / 카드 대형화)
// hook: 밤새 7개 / climax: 낮 포함 전체
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

// hook: 600프레임 (씬1 수정 녹음 19.98초 기준)
// climax: 900프레임 (별도 녹음 후 조정)
const DUR_HOOK    = 600;
const DUR_CLIMAX  = 900;

// ── 씬1 수정 녹음 타임스탬프 기반 싱크 프레임 ──────────────
// Whisper 단어별 타임스탬프 (씬1 수정 2026-05-30)
// "잠들었습니다" f55 / "그때부터" f97 / "10명이" f149
// "밤새" f220 / "텔레그램" f259 / "종목" f362
// "아침" f424 / "월급은" f526
const HOOK_SYNC_FRAMES = [
  42,   // 내가 잠든다       ← "잠들었습니다" f55 직전
  215,  // 미국 정규장 오픈  ← "밤새 미국" f220 직전
  252,  // 실적·뉴스 캐치   ← "텔레그램" f259 직전
  352,  // 수급 스캔        ← "종목" f362 직전
  375,  // 탑픽 분석        ← "스크린인" f382 직전
  415,  // 아침 브리핑      ← "아침" f424 직전
  515,  // 내가 일어난다    ← "월급은" f526 직전
];

interface Evt {
  time: string;
  label: string;
  sub: string;
  icon: string;
  accent: string;
  isSleep?: boolean;
  isWake?: boolean;
  isDayOnly?: boolean;
}

// hook 모드: 7개 (수면 포함)
const HOOK_EVENTS: Evt[] = [
  { time: '23:00', label: '취침',                     sub: '',                                  icon: '💤', accent: '#4a5568', isSleep: true },
  { time: '23:32', label: '미국 정규장 오픈',         sub: '나스닥 · SOX · 섹터 ETF 추적 시작',  icon: '🇺🇸', accent: '#FFA502' },
  { time: '01:14', label: '실적 · 뉴스 캐치',         sub: '스노우플레이크 서프 · MU TP 상향',    icon: '📡', accent: '#FFA502' },
  { time: '03:00', label: '수급 오실레이터 스캔',      sub: '500종목 전수 · A등급 빈집 29개',     icon: '🔍', accent: C.main   },
  { time: '05:33', label: '탑픽 교차 분석',            sub: '삼성전기 7/9점 — 탑픽 선정',        icon: '🎯', accent: C.main   },
  { time: '06:31', label: '아침 브리핑 생성',          sub: '섹터온도 · 탑픽 · 매크로 · 일정',   icon: '📊', accent: C.main   },
  { time: '07:00', label: '기상',                      sub: '결과만 확인한다',                   icon: '☀️', accent: C.dataUp, isWake: true },
];

// climax 모드: 낮 이벤트 3개 + hook 7개 = 10개
const CLIMAX_EVENTS: Evt[] = [
  { time: '14:23', label: '증권사 리포트 수집',        sub: '삼성전기 TP 상향 외 2건',            icon: '📄', accent: '#555', isDayOnly: true },
  { time: '15:04', label: '텔레그램 뉴스 감지',        sub: 'TSMC +38% · HLB D-54',              icon: '📡', accent: '#555', isDayOnly: true },
  { time: '16:31', label: '장마감 후 리포트 11건',     sub: 'LG이노텍 1.6M · 현대차 32만',       icon: '📄', accent: '#555', isDayOnly: true },
  ...HOOK_EVENTS,
];

function ip(f: number, a: number, b: number, from = 0, to = 1, ease = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease,
  });
}

// ── 시계 표시 계산 (hook 모드: 23:00 → 09:00 진행) ───────────────
// 오디오 싱크 프레임 기준으로 시각 보간
const CLOCK_ANCHORS = [
  { frame: 0,   h: 23, m: 0  },   // 시작: 23:00
  { frame: 42,  h: 23, m: 0  },   // 잠드는 순간
  { frame: 215, h: 23, m: 32 },   // 미국장 오픈
  { frame: 252, h: 1,  m: 14 },   // 실적 캐치
  { frame: 352, h: 3,  m: 0  },   // 수급 스캔
  { frame: 415, h: 6,  m: 31 },   // 브리핑 생성
  { frame: 515, h: 7,  m: 0  },   // 전송 완료
  { frame: 600, h: 7,  m: 0  },   // 기상 (07:00)
];

function getClockTime(f: number): { h: number; m: number } {
  for (let i = 0; i < CLOCK_ANCHORS.length - 1; i++) {
    const a = CLOCK_ANCHORS[i];
    const b = CLOCK_ANCHORS[i + 1];
    if (f >= a.frame && f <= b.frame) {
      const t = (f - a.frame) / (b.frame - a.frame);
      // 분을 0~1440(24시간) 기준으로 보간
      const minA = a.h * 60 + a.m + (a.h < 12 && i > 0 ? 1440 : 0);
      const minB = b.h * 60 + b.m + (b.h < 12 && b.h < a.h ? 1440 : b.h < 12 && i > 0 ? 1440 : 0);
      const cur  = Math.round(minA + (minB - minA) * t) % 1440;
      return { h: Math.floor(cur / 60) % 24, m: cur % 60 };
    }
  }
  const last = CLOCK_ANCHORS[CLOCK_ANCHORS.length - 1];
  return { h: last.h, m: last.m };
}

function pad(n: number) { return String(n).padStart(2, '0'); }

export const AG01_Timeline: React.FC<{ mode?: 'hook' | 'climax' }> = ({ mode = 'hook' }) => {
  const f      = useCurrentFrame();
  const fadeIn = ip(f, 0, 24);

  const isClimax = mode === 'climax';
  const DUR      = isClimax ? DUR_CLIMAX : DUR_HOOK;
  const prog     = ip(f, 15, DUR - 60);
  const events   = isClimax ? CLIMAX_EVENTS : HOOK_EVENTS;

  // 카드 크기 — 이벤트 수에 따라 자동 계산
  const TIMELINE_TOP = 80;
  const TIMELINE_BOT = 1080 - 60;
  const AVAIL_H      = TIMELINE_BOT - TIMELINE_TOP;
  const CARD_H       = Math.floor(AVAIL_H / events.length) - 10;
  const CARD_GAP     = 10;

  // 이벤트 등장 — hook: 오디오 싱크 / climax: 균등 간격
  const evtFrames = isClimax
    ? events.map((_, i) => 40 + i * 68)
    : HOOK_SYNC_FRAMES;

  // ── 시계 계산 (안전하게 감싸기) ──
  let clock = { h: 23, m: 0 };
  try { if (!isClimax) clock = getClockTime(f); } catch (_) {}
  const clockStr = `${pad(clock.h)}:${pad(clock.m)}`;

  // ── 실시간 카운터 (수집 건수: 0 → 31)
  const collectCount = Math.round(ip(f, 42, 510, 0, 31));
  const counterOp   = ip(f, 38, 60);

  // 타임라인 수직선 draw-on
  const lineH = isClimax
    ? ip(prog, 0.03, 0.90, 0, 1, Easing.inOut(Easing.cubic))
    : ip(f, 42, 570, 0, 1, Easing.inOut(Easing.cubic));

  // 우측 통계 — hook: "아침" f415 이후
  const statsOp = isClimax
    ? ip(prog, 0.72, 0.84)
    : ip(f, 430, 500);

  const finalOp = ip(prog, 0.88, 0.96);
  const timeOp  = ip(f, 10, 30);

  // 선 X 위치
  const LINE_X = 370;

  // ── 직원 부트 애니메이션 ────────────────────────────────────────
  // "잠들었습니다"(f72) → "그때부터 직원 10명이"(f134) 사이 공백 채우기
  // 직원 10명이 순서대로 ON 표시 (6프레임 간격)
  const BOOT_WORKERS = [
    { icon: '📡', name: '수집',   col: C.main    },
    { icon: '🇺🇸', name: '미국장', col: '#FFA502' },
    { icon: '📄', name: '리포트', col: '#9ca3af' },
    { icon: '🔍', name: '수급',   col: C.main    },
    { icon: '⚠️', name: '투경',   col: '#FFA502' },
    { icon: '📊', name: '분석',   col: C.main    },
    { icon: '🎯', name: '탑픽',   col: '#FF4757' },
    { icon: '📋', name: '브리핑', col: C.main    },
    { icon: '✅', name: '검증',   col: '#9ca3af' },
    { icon: '📨', name: '배포',   col: C.main    },
  ];
  // ── 싱크 규칙: 말 시작 = 애니 시작 / 말 끝 = 애니 끝 ──────────
  // "그때부터 직원 10명이 일을 시작했어요"
  //  f97(그때부터) ─────────────────────── f179(시작했어요)
  //  직원1→2→3→...→10 순차 등장 (82프레임 / 10명 = 8프레임 간격)
  const BOOT_START = 97;   // "그때부터" 발화 시작
  const BOOT_END   = 179;  // "시작했어요" 발화 끝
  const BOOT_SPAN  = BOOT_END - BOOT_START;  // 82프레임

  const bootPanelOp = !isClimax
    ? ip(f, BOOT_START - 8, BOOT_START + 4) * (1 - ip(f, BOOT_END + 20, BOOT_END + 40))
    : 0;
  // 10명을 82프레임 안에 고르게: 각 8프레임 간격, 등장 12프레임
  const bootWorkerOn = (i: number) => {
    const start = BOOT_START + Math.round((i / 9) * (BOOT_SPAN - 8));
    return ip(f, start, start + 12);
  };

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: fadeIn, fontFamily: FONT }}>

      {/* 오디오 — hook 모드: 씬1 녹음 */}
      {mode === 'hook' && <Html5Audio src={staticFile('voice/s01.mp3')} volume={1} />}

      {/* ── 직원 부트 애니메이션 (f72~f134 공백 채우기) ── */}
      {bootPanelOp > 0.01 && (
        <div style={{
          position: 'absolute',
          left: '50%', top: '50%',
          transform: 'translate(-50%, -50%)',
          opacity: bootPanelOp,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 28,
        }}>
          {/* 상단 타이틀 */}
          <div style={{
            color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6,
          }}>SYSTEM BOOT</div>

          {/* 직원 5×2 그리드 — 크게 */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
            gap: '24px 48px',
          }}>
            {BOOT_WORKERS.map((w, i) => {
              const on = bootWorkerOn(i);
              const isOn = on > 0.5;
              return (
                <div key={i} style={{
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', gap: 12, width: 150,
                  opacity: 0.15 + on * 0.85,  // 꺼진 상태도 희미하게 보임
                }}>
                  {/* 아이콘 서클 — 크게 */}
                  <div style={{
                    width: 100, height: 100, borderRadius: '50%',
                    background: isOn ? `${w.col}22` : 'rgba(255,255,255,0.03)',
                    border: `2px solid ${isOn ? w.col : 'rgba(255,255,255,0.08)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 44,
                    boxShadow: isOn
                      ? `0 0 ${20 + Math.sin(f * 0.15 + i) * 8}px ${w.col}55`
                      : undefined,
                    transform: `scale(${0.88 + on * 0.12})`,
                  }}>{w.icon}</div>
                  {/* 이름 + 상태 */}
                  <div style={{ textAlign: 'center' }}>
                    <div style={{
                      color: isOn ? '#e5e7eb' : '#374151',
                      fontSize: 18, fontWeight: 700,
                    }}>{w.name}</div>
                    <div style={{
                      color: isOn ? w.col : '#374151',
                      fontSize: 14, fontWeight: 700, letterSpacing: 2, marginTop: 4,
                    }}>{isOn ? '● ON' : '○ --'}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 하단 상태 바 — 크게 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 16,
            marginTop: 8,
          }}>
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              background: C.main,
              boxShadow: `0 0 ${10 + Math.sin(f * 0.2) * 5}px ${C.main}`,
              flexShrink: 0,
            }} />
            <div style={{
              color: C.main, fontSize: 36, fontWeight: 900, letterSpacing: 4,
              textShadow: `0 0 20px ${C.main}66`,
            }}>
              직원 {Math.min(10, BOOT_WORKERS.filter((_, i) => bootWorkerOn(i) > 0.5).length)}명 가동 중...
            </div>
          </div>
        </div>
      )}

      {/* 배경 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 20% 50%, rgba(0,255,208,0.04) 0%, transparent 58%)',
        pointerEvents: 'none',
      }} />

      {/* 우상단 */}
      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: timeOp,
      }}>{isClimax ? '24시간 전체' : '밤새 타임라인'}</div>

      {/* 좌상단 — 실시간 시계 (항상 흘러감) */}
      <div style={{ position: 'absolute', top: 30, left: 60, opacity: timeOp }}>
        <div style={{ color: '#4b5563', fontSize: 13, fontWeight: 600, letterSpacing: 5, marginBottom: 4 }}>
          {isClimax ? 'ALWAYS ON' : 'WHILE YOU SLEEP'}
        </div>
        <div style={{
          color: C.main, fontSize: 88, fontWeight: 900,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: GLOW.mid.text,
          letterSpacing: 4, lineHeight: 1,
        }}>
          {isClimax ? '24HR' : clockStr}
        </div>
      </div>

      {/* 실시간 수집 카운터 — 우하단 */}
      {!isClimax && (
        <div style={{
          position: 'absolute', right: 52, bottom: 120,
          opacity: counterOp, textAlign: 'right',
        }}>
          <div style={{ color: '#4b5563', fontSize: 13, fontWeight: 600, letterSpacing: 4, marginBottom: 8 }}>
            NOW COLLECTING
          </div>
          <div style={{
            color: C.main, fontSize: 80, fontWeight: 900, lineHeight: 1,
            fontFamily: '"Consolas","Menlo",monospace',
            textShadow: GLOW.weak.text,
          }}>
            {String(collectCount).padStart(2, '0')}
          </div>
          <div style={{ color: '#4b5563', fontSize: 16, marginTop: 6 }}>건 수집 완료</div>
          <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: C.main,
              boxShadow: `0 0 ${8 + Math.sin(f * 0.15) * 4}px ${C.main}`,
            }} />
            <div style={{ color: C.main, fontSize: 14, fontWeight: 700, letterSpacing: 3 }}>LIVE</div>
          </div>
        </div>
      )}

      {/* 수직 타임라인 선 */}
      <div style={{
        position: 'absolute', left: LINE_X, top: TIMELINE_TOP, bottom: 60, width: 3,
        background: '#1a2030',
      }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0,
          height: `${lineH * 100}%`,
          background: `linear-gradient(to bottom, ${C.main}cc, ${C.main}22)`,
        }} />
      </div>

      {/* 이벤트 카드들 */}
      <div style={{
        position: 'absolute',
        left: 0, top: TIMELINE_TOP, right: 340, bottom: 60,
        display: 'flex', flexDirection: 'column',
        justifyContent: 'space-between',
        paddingBlock: 0,
      }}>
        {events.map((evt, i) => {
          const af       = evtFrames[i];
          const evtOp    = ip(f, af, af + 24);
          const evtSlide = interpolate(f, [af, af + 24], [50, 0], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          const isSleep = evt.isSleep;
          const isWake  = evt.isWake;
          const dotPulse = (isSleep || isWake)
            ? 1 + Math.sin(f * 0.07) * 0.40
            : 1;
          const dotSize = isSleep || isWake ? 22 : 13;

          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center',
              height: CARD_H,
              opacity: evtOp,
              transform: `translateX(${evtSlide}px)`,
            }}>
              {/* 시간 */}
              <div style={{
                width: 350, textAlign: 'right', paddingRight: 20, flexShrink: 0,
                fontSize: isSleep || isWake ? 26 : 21,
                fontFamily: '"Consolas","Menlo",monospace',
                color: isSleep ? '#5a6478' : isWake ? C.dataUp : '#6b7280',
                fontWeight: 700,
              }}>{evt.time}</div>

              {/* 도트 */}
              <div style={{
                width: dotSize, height: dotSize,
                borderRadius: '50%', flexShrink: 0, zIndex: 1,
                background: isSleep ? '#3a4055' : isWake ? C.dataUp : evt.accent,
                transform: `scale(${dotPulse})`,
                boxShadow: (isSleep || isWake || evt.accent === C.main)
                  ? `0 0 ${isSleep || isWake ? 20 : 10}px ${evt.accent}88`
                  : undefined,
              }} />

              {/* 카드 */}
              <div style={{
                marginLeft: 22, flex: 1, marginRight: 20,
                height: CARD_H - CARD_GAP,
                padding: '0 28px',
                background: isSleep ? 'rgba(255,255,255,0.02)'
                  : isWake  ? 'rgba(255,67,54,0.07)'
                  : evt.isDayOnly ? 'rgba(0,191,154,0.04)'
                  : 'rgba(255,255,255,0.035)',
                border: `1px solid ${
                  isSleep ? 'rgba(255,255,255,0.05)'
                  : isWake  ? 'rgba(255,67,54,0.28)'
                  : evt.isDayOnly ? 'rgba(0,191,154,0.15)'
                  : 'rgba(255,255,255,0.08)'}`,
                borderRadius: 16,
                display: 'flex', alignItems: 'center', gap: 18,
              }}>
                <span style={{ fontSize: isSleep || isWake ? 32 : 26, flexShrink: 0 }}>
                  {evt.icon}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* 메인 라벨 */}
                  <div style={{
                    fontSize: isSleep || isWake ? 32 : 26,
                    color: isSleep ? '#6b7280' : isWake ? C.dataUp : '#e5e7eb',
                    fontWeight: 700, lineHeight: 1.2,
                  }}>{evt.label}</div>
                  {/* 서브 */}
                  {evt.sub && (
                    <div style={{
                      fontSize: 17, color: '#4b5563', marginTop: 6,
                    }}>{evt.sub}</div>
                  )}
                </div>
                {/* 배지 */}
                {!isSleep && !isWake && (
                  <div style={{
                    padding: '5px 14px', borderRadius: 8, flexShrink: 0,
                    background: `${evt.accent}18`,
                    border: `1px solid ${evt.accent}38`,
                    color: evt.accent, fontSize: 14, fontWeight: 700, letterSpacing: 1,
                  }}>
                    {evt.isDayOnly ? '낮' : evt.accent === '#FFA502' ? '미국' : 'AI'}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 우측 통계 패널 */}
      <div style={{
        position: 'absolute', right: 20, top: '50%',
        transform: 'translateY(-50%)',
        width: 300, opacity: statsOp,
        display: 'flex', flexDirection: 'column', gap: 20,
      }}>
        {[
          { label: '수집', val: '31건',  sub: '뉴스 + 리포트' },
          { label: '스캔', val: '500+', sub: '전 섹터 종목' },
          { label: '탑픽', val: '3개',  sub: '선정 완료' },
        ].map((s, i) => (
          <div key={i} style={{
            padding: '20px 24px',
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 18,
          }}>
            <div style={{ color: '#555', fontSize: 13, fontWeight: 700, letterSpacing: 4, marginBottom: 10 }}>
              {s.label}
            </div>
            <div style={{
              color: C.main, fontSize: 52, fontWeight: 900, lineHeight: 1,
              fontFamily: '"Consolas","Menlo",monospace',
              textShadow: GLOW.weak.text,
            }}>{s.val}</div>
            <div style={{ color: '#6b7280', fontSize: 15, marginTop: 8 }}>{s.sub}</div>
          </div>
        ))}

        {isClimax && (
          <div style={{
            opacity: finalOp, marginTop: 4,
            padding: '22px 24px',
            background: `${C.main}0d`,
            border: `1px solid ${C.main}42`,
            borderRadius: 18,
          }}>
            <div style={{
              color: C.main, fontSize: 24, fontWeight: 800, lineHeight: 1.6,
              textShadow: GLOW.weak.text,
            }}>내가 뭘 하든<br />항상 돌아갑니다</div>
          </div>
        )}
      </div>

      {/* 하단 */}
      <div style={{
        position: 'absolute', bottom: 18, left: 0, right: 0,
        textAlign: 'center', opacity: ip(f, 10, 30),
      }}>
        <div style={{ color: '#374151', fontSize: 18, fontWeight: 600, letterSpacing: 4 }}>
          {isClimax ? 'CLIMAX · 24시간' : 'HOOK · 밤새 타임라인'}
        </div>
      </div>

    </AbsoluteFill>
  );
};
