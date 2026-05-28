// Sample A — 24시간 다이얼
// 영상 전체가 거대한 원형 시계. 시침이 24시간 돌면서 시간대별 아이콘 활성
// 08:00 위치에 노트북 아이콘이 가장 강하게 빛나며 "딸깍" 회수
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 240; // 8초

// 시간대별 마커 (각도, 아이콘, 라벨, 점등 시점 progress 0~1 기준)
const MARKERS = [
  { hour: 4,  icon: '🖥️', label: '서버',     onAt: 0.15 },
  { hour: 8,  icon: '💻', label: '대시보드', onAt: 0.45, hero: true },
  { hour: 9,  icon: '📈', label: '매수',     onAt: 0.55 },
  { hour: 15, icon: '🔔', label: '마감',     onAt: 0.70 },
  { hour: 23, icon: '🛏️', label: '잠',      onAt: 0.85 },
];

export const DakkakA_Dial = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [10, DUR - 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 시침 회전 (시계 12시=top 기준, 24시간 = 360도)
  const hourAngle = prog * 360;

  // 다이얼 등장 스케일
  const dialScale = interpolate(f, [0, 30], [0.7, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // 08:00 클라이맥스 — prog 0.42~0.50 구간에 강한 펄스
  const climaxProg = interpolate(prog, [0.40, 0.50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const climaxFade = interpolate(prog, [0.50, 0.65], [1, 0.3], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const heroIntensity = climaxProg * climaxFade;

  // 마지막 "딸깍" 자막 (prog 0.85~1)
  const ddakOp = interpolate(prog, [0.85, 0.95], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 라벨
  const labelOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // 배경 펄스
  const bgGlow = Math.sin(f * 0.04) * 0.025 + 0.04;

  const RADIUS = 380;
  const CX = 960;
  const CY = 540;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      {/* 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 60%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 40, right: 60,
        color: C.textSub, fontSize: 22, fontWeight: 600, letterSpacing: 4,
        opacity: labelOp,
      }}>SAMPLE A · 24H DIAL</div>

      {/* 다이얼 본체 */}
      <div style={{
        position: 'absolute', left: CX - RADIUS, top: CY - RADIUS,
        width: RADIUS * 2, height: RADIUS * 2,
        transform: `scale(${dialScale})`,
        transformOrigin: 'center center',
      }}>
        {/* 외곽 링 */}
        <div style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          border: `2px solid ${C.borderSub}`,
          boxShadow: 'inset 0 0 80px rgba(0,255,208,0.05)',
        }} />
        {/* 진행 호 (이미 지난 시간) */}
        <svg width={RADIUS * 2} height={RADIUS * 2} style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <linearGradient id="arcGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00FFD0" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#00BF9A" stopOpacity="0.4" />
            </linearGradient>
          </defs>
          <circle
            cx={RADIUS} cy={RADIUS} r={RADIUS - 10}
            fill="none" stroke="url(#arcGrad)" strokeWidth={4}
            strokeDasharray={`${2 * Math.PI * (RADIUS - 10)}`}
            strokeDashoffset={`${2 * Math.PI * (RADIUS - 10) * (1 - prog)}`}
            transform={`rotate(-90 ${RADIUS} ${RADIUS})`}
            style={{ filter: 'drop-shadow(0 0 6px #00FFD0)' }}
          />
        </svg>

        {/* 24시간 눈금 */}
        {Array.from({ length: 24 }).map((_, h) => {
          const angle = (h / 24) * 360 - 90;
          const rad = (angle * Math.PI) / 180;
          const isMajor = h % 6 === 0;
          const r1 = RADIUS - 24;
          const r2 = RADIUS - (isMajor ? 48 : 36);
          const x1 = RADIUS + Math.cos(rad) * r1;
          const y1 = RADIUS + Math.sin(rad) * r1;
          const x2 = RADIUS + Math.cos(rad) * r2;
          const y2 = RADIUS + Math.sin(rad) * r2;
          return (
            <svg key={h} width={RADIUS * 2} height={RADIUS * 2} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
              <line x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={isMajor ? C.main : C.borderSub}
                strokeWidth={isMajor ? 3 : 1.5}
                opacity={isMajor ? 0.9 : 0.5}
              />
              {isMajor && (
                <text
                  x={RADIUS + Math.cos(rad) * (RADIUS - 70)}
                  y={RADIUS + Math.sin(rad) * (RADIUS - 70) + 8}
                  fill={C.textSub} fontSize={22} fontWeight={700}
                  textAnchor="middle" fontFamily={FONT}
                >{String(h).padStart(2, '0')}</text>
              )}
            </svg>
          );
        })}

        {/* 시간대별 아이콘 마커 */}
        {MARKERS.map((m, i) => {
          const angle = (m.hour / 24) * 360 - 90;
          const rad = (angle * Math.PI) / 180;
          const r = RADIUS - 130;
          const x = RADIUS + Math.cos(rad) * r;
          const y = RADIUS + Math.sin(rad) * r;
          const isOn = prog >= m.onAt;
          const turnOn = interpolate(prog, [m.onAt, m.onAt + 0.05], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
          const heroBoost = m.hero ? heroIntensity * 1.2 : 0;
          const scale = isOn ? 1 + turnOn * 0.3 - turnOn * 0.2 + (m.hero ? heroIntensity * 0.4 : 0) : 0.5;
          const op = isOn ? 0.6 + turnOn * 0.4 : 0.15;
          return (
            <div key={i} style={{
              position: 'absolute',
              left: x - 36, top: y - 36,
              width: 72, height: 72,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 48,
              opacity: op,
              transform: `scale(${scale})`,
              filter: isOn
                ? `drop-shadow(0 0 ${10 + heroBoost * 24}px #00FFD0) drop-shadow(0 0 ${heroBoost * 50}px rgba(0,255,208,0.6))`
                : 'grayscale(1) brightness(0.5)',
            }}>{m.icon}</div>
          );
        })}

        {/* 시침 */}
        <div style={{
          position: 'absolute',
          left: RADIUS - 2, top: 30,
          width: 4, height: RADIUS - 30,
          background: GLOW.mid.text ? 'linear-gradient(180deg, #00FFD0 0%, #00BF9A 100%)' : C.main,
          transformOrigin: `2px ${RADIUS - 30}px`,
          transform: `rotate(${hourAngle}deg)`,
          boxShadow: '0 0 12px rgba(0,255,208,0.9)',
          borderRadius: 2,
        }} />
        {/* 중앙 점 */}
        <div style={{
          position: 'absolute',
          left: RADIUS - 10, top: RADIUS - 10,
          width: 20, height: 20, borderRadius: '50%',
          background: C.main, boxShadow: GLOW.mid.box,
        }} />
      </div>

      {/* 클라이맥스 "딸깍" 자막 */}
      <div style={{
        position: 'absolute', bottom: 110, left: 0, right: 0,
        textAlign: 'center',
        color: C.main, fontSize: 96, fontWeight: 900,
        letterSpacing: 8,
        textShadow: GLOW.strong.text,
        opacity: ddakOp,
        transform: `scale(${0.85 + ddakOp * 0.15})`,
      }}>딸깍</div>

      {/* 하단 자막 바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '12%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: labelOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 34, fontWeight: 700, opacity: 0.85 }}>
          24시간이 한 화면 안에서 흐른다
        </div>
      </div>
    </AbsoluteFill>
  );
};
