/**
 * KK_S4_Roadmap — 로드맵 (322f · 모드 C 리모션 단독)
 * 오디오(s04_audio) + 검정 무대. 자막 3줄 한 줄마다 중앙 그래픽이 호응(이탈 0).
 * 5단계 미리보기 → 10분 컷 → 코딩 0줄, 따라오세요
 *
 * 자막 = Whisper 1:1 (타이밍 변경 금지, DESIGN.md §7).
 * 골든 레퍼런스: KK_S3_L30.tsx
 */

import React from 'react';
import { Audio, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop, riseFade, zoomPunch, shake, flashAt, pulse, Sfx } from './fx';
import { Stage, Kicker, Watermark, ClaudeIcon, LifeSubBar, LIME, LIME_GLOW, ORANGE, RED, SUB } from './life';

export const KK_S4_ROADMAP_FRAMES = 322;

const NUM = "'Archivo','Noto Sans KR',sans-serif";
const MONO = "'Space Mono','Roboto Mono',monospace";

const SUBS = [
  { from: 0, to: 108, text: '오늘 할 것 딱 5단계입니다.', accent: '5단계' },
  { from: 108, to: 202, text: '길게 안 끌고 10분 안에 끝내드릴게요.', accent: '10분' },
  { from: 202, to: 322, text: '코딩 한 줄도 없으니까 편하게 따라오세요.', accent: '코딩 한 줄도 없으니까' },
];

const STEPS = [
  { n: 1, icon: '🖥️', title: 'Claude 설치', at: 16 },
  { n: 2, icon: '🔌', title: 'PlayMCP 연결', at: 34 },
  { n: 3, icon: '✍️', title: '프롬프트 작성', at: 52 },
  { n: 4, icon: '📦', title: '플러그인', at: 70 },
  { n: 5, icon: '⏰', title: '예약 자동화', at: 88 },
];

// ── ambient: 흐르는 흐름선 (S3 골든레퍼런스와 동일) ──
const FlowField: React.FC<{ f: number; color?: string }> = ({ f, color = LIME }) => (
  <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
    <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
      {Array.from({ length: 7 }).map((_, i) => {
        const yBase = 120 + i * 140;
        const amp = 38 + (i % 3) * 14;
        const pts: string[] = [];
        for (let x = -40; x <= 1960; x += 36) {
          const y = yBase + Math.sin(x * 0.0055 + f * 0.024 + i * 0.9) * amp + Math.sin(x * 0.013 - f * 0.01) * (amp * 0.4);
          pts.push(`${x},${y.toFixed(1)}`);
        }
        return <polyline key={i} points={pts.join(' ')} fill="none" stroke={color} strokeWidth={1} opacity={0.05 + (i % 2) * 0.04} />;
      })}
    </svg>
    {Array.from({ length: 22 }).map((_, i) => {
      const x = (i * 97) % 1920;
      const y = (1080 - ((f * (0.5 + (i % 4) * 0.25) + i * 60) % 1140)) - 30;
      const op = 0.12 + (i % 3) * 0.06;
      return <div key={i} style={{ position: 'absolute', left: x, top: y, width: 3 + (i % 3), height: 3 + (i % 3), borderRadius: '50%', background: color, opacity: op, boxShadow: `0 0 8px ${color}` }} />;
    })}
  </div>
);

// 중앙 비트 래퍼 (S3 동일)
const Beat: React.FC<{ show: boolean; op: number; extra?: React.CSSProperties; children: React.ReactNode }> = ({ show, op, extra, children }) =>
  show ? (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingBottom: '11%', opacity: op, ...extra }}>
      {children}
    </div>
  ) : null;

const KICK: React.CSSProperties = { fontFamily: MONO, fontSize: 17, letterSpacing: 5, marginBottom: 18 };

export const KK_S4_Roadmap: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <Stage>
      <Audio src={staticFile('kakao/ep1/s04_audio.m4a')} />
      <FlowField f={f} color={LIME} />
      <Kicker ch="CH 04" title="ROADMAP" f={f} />

      {STEPS.map((s, i) => (
        <Sfx key={i} at={s.at} file="pop_appear.mp3" vol={0.3} />
      ))}
      <Sfx at={112} file="impact.mp3" vol={0.4} />
      <Sfx at={206} file="pop_appear.mp3" vol={0.34} />
      <Sfx at={276} file="chime_up.mp3" vol={0.42} />

      {/* 컷 플래시 (비트 전환) */}
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 110, 7, 0.28), pointerEvents: 'none' }} />

      {/* B1 — 오늘 할 것 = 5단계 (0~108) */}
      <Beat show={f < 116} op={cl(f, 8, 30) * cl(f, 95, 108, 1, 0)}>
        <div style={{ ...KICK, color: LIME }}>TODAY · 오늘의 미션</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 34 }}>
          <span style={{ fontSize: 56, fontWeight: 800, color: SUB, letterSpacing: -1 }}>오늘 할 것 딱</span>
          <span style={{ fontFamily: NUM, fontSize: 150, fontWeight: 900, color: LIME, letterSpacing: -6, lineHeight: 1, textShadow: `0 0 50px ${LIME_GLOW}`, transform: `scale(${zoomPunch(f, 8, 1.12, 16)})`, display: 'inline-block' }}>5</span>
          <span style={{ fontSize: 70, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>단계</span>
        </div>
        {/* 5스텝 카드 행 (순차 빌드 + 연결선) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
          {STEPS.map((s, i) => {
            const { opacity, y } = riseFade(f, s.at, 12, 30);
            const p = pop(f, s.at, { damping: 8, stiffness: 260 });
            const lineW = cl(f, s.at, s.at + 13, 0, 44);
            return (
              <React.Fragment key={s.n}>
                {i > 0 && (
                  <div style={{ width: lineW, height: 3, background: `linear-gradient(90deg, ${LIME}, rgba(170,255,0,0.3))`, borderRadius: 2, boxShadow: `0 0 10px ${LIME}66` }} />
                )}
                <div style={{ opacity, transform: `translateY(${y}px) scale(${0.85 + p * 0.15})`, width: 176, padding: '20px 14px', background: 'rgba(0,0,0,0.6)', border: `2px solid ${LIME}`, borderRadius: 16, textAlign: 'center', boxShadow: `0 0 26px ${LIME}22` }}>
                  <div style={{ width: 38, height: 38, margin: '0 auto 10px', borderRadius: '50%', background: LIME, color: '#000', fontFamily: NUM, fontSize: 20, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{s.n}</div>
                  <div style={{ fontSize: 34, marginBottom: 6 }}>{s.icon}</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: '#fff', lineHeight: 1.25, whiteSpace: 'nowrap' }}>{s.title}</div>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </Beat>

      {/* B2 — 10분 컷 (108~202) */}
      {f >= 108 && f < 202 && (() => {
        const punch = zoomPunch(f, 112, 1.16, 18);
        return (
          <Beat show op={cl(f, 112, 138) * cl(f, 178, 202, 1, 0)} extra={{ transform: `scale(${punch})` }}>
            <div style={{ ...KICK, color: LIME }}>SPEED · 길게 안 끕니다</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
              <span style={{ fontSize: 50, fontWeight: 700, color: SUB }}>딱</span>
              <span style={{ fontFamily: NUM, fontSize: 200, fontWeight: 900, color: LIME, letterSpacing: -8, lineHeight: 1, textShadow: `0 0 60px ${LIME_GLOW}` }}>10</span>
              <span style={{ fontSize: 80, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>분</span>
            </div>
            <div style={{ fontSize: 44, fontWeight: 900, color: '#fff', marginTop: 10, transform: `scale(${pulse(f, 0.14, 0.98, 0.03)})` }}>
              안에 <span style={{ color: ORANGE, textShadow: `0 0 30px ${ORANGE}88` }}>전부 끝</span>
            </div>
          </Beat>
        );
      })()}

      {/* B3 — 코딩 0줄, 따라오세요 (202~322) */}
      {f >= 202 && (
        <Beat show op={cl(f, 206, 232)} extra={f < 270 ? { transform: `translate(${shake(f, 206, 16, 7).x}px, ${shake(f, 206, 16, 7).y}px)` } : undefined}>
          <div style={{ ...KICK, color: RED }}>NO CODE · 걱정 마세요</div>
          {/* 코딩 0줄 */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 18, marginBottom: 30 }}>
            <span style={{ fontFamily: MONO, fontSize: 64, fontWeight: 900, color: SUB, textDecoration: 'line-through', textDecorationColor: RED, textDecorationThickness: 5 }}>&lt;/&gt; 코딩</span>
            <span style={{ fontFamily: NUM, fontSize: 170, fontWeight: 900, color: RED, letterSpacing: -6, lineHeight: 1, textShadow: `0 0 50px rgba(255,68,85,0.6)` }}>0</span>
            <span style={{ fontSize: 64, fontWeight: 900, color: '#fff' }}>줄</span>
          </div>
          {/* 편하게 따라오세요 (270~) */}
          {(() => { const { opacity, y } = riseFade(f, 272, 14, 36); return (
            <div style={{ opacity, transform: `translateY(${y}px)`, display: 'flex', alignItems: 'center', gap: 16 }}>
              <ClaudeIcon size={56} />
              <div style={{ fontSize: 60, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
                편하게 <span style={{ color: LIME, textShadow: `0 0 36px ${LIME_GLOW}` }}>따라오세요</span>
              </div>
              <span style={{ fontSize: 64 }}>👋</span>
            </div>
          ); })()}
        </Beat>
      )}

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
    </Stage>
  );
};
