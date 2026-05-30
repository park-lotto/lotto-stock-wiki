// AG01 — 24시간 타임라인 씬 (씬1 훅 + 씬5 클라이맥스 재사용)
// 낮(장중) → 저녁 → 내가 잠든다 → 밤새 미국장 → 아침 브리핑
// 25초 = 750프레임

import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
} from 'remotion';

const DUR = 750;

const C = {
  bg:       '#0a0e1a',
  panel:    '#111827',
  border:   '#1e2d45',
  mint:     '#00e5c3',
  mintDim:  '#00b89a',
  red:      '#ff4757',
  yellow:   '#ffa502',
  gray:     '#4a5568',
  grayText: '#9ca3af',
  white:    '#f0f4f8',
  dimText:  '#6b7280',
  sleep:    '#1a1f35',  // 잠든 구간 배경
  us:       '#1e3a5f',  // 미국장 구간
};

// 타임라인 이벤트 정의
const TIMELINE_EVENTS = [
  { time: '낮 14:00', label: '증권사 리포트 수집', tag: '리포트', color: C.mint,   icon: '📄', isDay: true },
  { time: '낮 15:00', label: '텔레그램 뉴스 감지', tag: '뉴스',   color: C.mint,   icon: '📡', isDay: true },
  { time: '저녁 16:30', label: '리포트 쏟아짐 — 자동 수집', tag: '리포트', color: C.mintDim, icon: '📄', isDay: true },
  { time: '밤 23:00', label: '★ 내가 잠든다',    tag: '수면',   color: C.gray,   icon: '💤', isSleep: true },
  { time: '밤 23:30', label: '미국 정규장 오픈', tag: '미국장',  color: C.yellow, icon: '🇺🇸', isUS: true },
  { time: '새벽 1:00', label: '미국 실적·연준 발언 캐치', tag: '뉴스', color: C.yellow, icon: '📡', isUS: true },
  { time: '새벽 3:00', label: '500종목 수급 스캔', tag: '수급',   color: C.mint,   icon: '🔍', isUS: true },
  { time: '새벽 5:00', label: '미국 장 마감 — 종가 확정', tag: '미국장', color: C.yellow, icon: '🏁', isUS: true },
  { time: '새벽 6:30', label: '아침 브리핑 생성', tag: '브리핑',  color: C.mint,   icon: '📊', isUS: false },
  { time: '아침 7:00', label: '텔레그램 전송 완료', tag: '배포',  color: C.mint,   icon: '✅', isUS: false },
  { time: '아침 9:00', label: '★ 내가 일어난다 — 결과만 본다', tag: '완료', color: C.red, icon: '☀️', isWake: true },
];

// 각 이벤트가 몇 프레임에 등장할지
const EVENT_APPEAR_FRAMES = TIMELINE_EVENTS.map((_, i) =>
  Math.round(60 + i * 58)
);

function ease(f: number, a: number, b: number) {
  return interpolate(f, [a, b], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
}

export const AG01_Timeline: React.FC<{ mode?: 'hook' | 'climax' }> = ({
  mode = 'hook',
}) => {
  const f = useCurrentFrame();

  const fadeIn = ease(f, 0, 20);

  // 클라이맥스 모드: 낮 이벤트까지 보임 (위로 스크롤)
  const showDayEvents = mode === 'climax';

  // 타임라인 라인 draw-on
  const lineProgress = ease(f, 30, DUR - 100);

  return (
    <AbsoluteFill
      style={{
        background: C.bg,
        opacity: fadeIn,
        fontFamily: "'Noto Sans KR', sans-serif",
      }}
    >
      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute',
        top: '30%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 800,
        height: 400,
        background: `radial-gradient(ellipse, ${C.mint}08 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      {/* 헤더 */}
      <div style={{
        position: 'absolute',
        top: 48,
        left: 80,
        right: 80,
        display: 'flex',
        alignItems: 'center',
        gap: 16,
      }}>
        <div style={{
          width: 4,
          height: 28,
          background: C.mint,
          borderRadius: 2,
        }} />
        <span style={{
          fontSize: 22,
          color: C.grayText,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
        }}>
          {mode === 'climax' ? '24시간 — 내가 뭘 하든 상관없이' : 'AI 직원들의 하루'}
        </span>
      </div>

      {/* 타임라인 중앙 라인 */}
      <div style={{
        position: 'absolute',
        left: 200,
        top: 110,
        bottom: 80,
        width: 2,
        background: C.border,
        overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: `${lineProgress * 100}%`,
          background: `linear-gradient(to bottom, ${C.mint}, ${C.mintDim}44)`,
        }} />
      </div>

      {/* 이벤트 목록 */}
      <div style={{
        position: 'absolute',
        top: 100,
        left: 80,
        right: 80,
        bottom: 80,
        overflow: 'hidden',
      }}>
        {TIMELINE_EVENTS.map((evt, i) => {
          const appearFrame = EVENT_APPEAR_FRAMES[i];
          const evtFade = ease(f, appearFrame, appearFrame + 18);
          const evtSlide = interpolate(f, [appearFrame, appearFrame + 18], [20, 0], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });

          // 낮 이벤트는 클라이맥스 모드에서만
          if (evt.isDay && !showDayEvents && !mode) return null;

          const isSleepRow = evt.isSleep;
          const isWakeRow  = evt.isWake;

          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 0,
                marginBottom: isSleepRow || isWakeRow ? 20 : 10,
                opacity: evtFade,
                transform: `translateX(${evtSlide}px)`,
              }}
            >
              {/* 시간 텍스트 */}
              <div style={{
                width: 110,
                textAlign: 'right',
                fontSize: isSleepRow || isWakeRow ? 14 : 12,
                color: isSleepRow ? C.gray : isWakeRow ? C.red : C.dimText,
                paddingRight: 12,
                fontWeight: isSleepRow || isWakeRow ? 700 : 400,
                flexShrink: 0,
              }}>
                {evt.time}
              </div>

              {/* 타임라인 점 */}
              <div style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: evt.color,
                flexShrink: 0,
                marginLeft: 82,
                boxShadow: `0 0 ${isSleepRow || isWakeRow ? 12 : 6}px ${evt.color}`,
                zIndex: 1,
              }} />

              {/* 이벤트 카드 */}
              <div style={{
                marginLeft: 20,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: isSleepRow || isWakeRow ? '10px 18px' : '7px 14px',
                background: isSleepRow ? C.sleep
                           : isWakeRow  ? `${C.red}15`
                           : evt.isUS   ? `${C.us}80`
                           : `${C.panel}cc`,
                borderRadius: 10,
                border: `1px solid ${
                  isSleepRow ? C.gray + '40'
                  : isWakeRow  ? C.red + '60'
                  : evt.isUS   ? C.yellow + '30'
                  : C.border
                }`,
              }}>
                <span style={{ fontSize: 16 }}>{evt.icon}</span>
                <span style={{
                  fontSize: isSleepRow || isWakeRow ? 16 : 13,
                  color: isSleepRow ? C.gray
                         : isWakeRow  ? C.red
                         : C.white,
                  fontWeight: isSleepRow || isWakeRow ? 700 : 400,
                }}>
                  {evt.label}
                </span>
                <div style={{
                  marginLeft: 8,
                  padding: '2px 8px',
                  background: `${evt.color}20`,
                  borderRadius: 4,
                  fontSize: 10,
                  color: evt.color,
                  fontWeight: 600,
                  letterSpacing: '0.05em',
                }}>
                  {evt.tag}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 하단 — "24시간 내내" 강조 (클라이맥스 모드) */}
      {mode === 'climax' && (
        <div style={{
          position: 'absolute',
          bottom: 40,
          left: 80,
          right: 80,
          textAlign: 'center',
          opacity: ease(f, DUR - 90, DUR - 60),
        }}>
          <span style={{
            fontSize: 28,
            color: C.mint,
            fontWeight: 700,
            letterSpacing: '0.08em',
          }}>
            내가 뭘 하든 상관없이 — 항상 돌아갑니다
          </span>
        </div>
      )}
    </AbsoluteFill>
  );
};
