/**
 * KK_S4_Roadmap — 5단계 로드맵 (322f · 순수 Remotion)
 * Whisper 3세그 자막 + 5스텝 카드 순차 등장.
 */

import React from 'react';
import { AbsoluteFill, Audio, staticFile, useCurrentFrame } from 'remotion';
import { LIME } from './theme';
import { pop, cl, riseFade, GlowOrb, Scanlines, SubBar, Sfx, type Sub } from './fx';

export const KK_S4_ROADMAP_FRAMES = 322;

const SUBS: Sub[] = [
  { from: 0, to: 108, text: '오늘 할 것 딱 5단계입니다.', accent: '5단계' },
  { from: 108, to: 202, text: '길게 안 끌고 10분 안에 끝내드릴게요.', accent: '10분' },
  { from: 202, to: 322, text: '코딩 한 줄도 없으니까 편하게 따라오세요.', accent: '코딩 한 줄도 없으니까' },
];

const STEPS = [
  { n: 1, icon: '🖥️', title: 'Claude 설치', sub: '데스크탑 앱' },
  { n: 2, icon: '🔌', title: 'PlayMCP 연결', sub: '네이버·카톡' },
  { n: 3, icon: '✍️', title: '프롬프트 작성', sub: '업무 지시서' },
  { n: 4, icon: '📦', title: '플러그인 패키징', sub: '/브리핑' },
  { n: 5, icon: '⏰', title: '예약 자동화', sub: '매일 7시' },
];

const START = 34;
const GAP = 18;

export const KK_S4_Roadmap: React.FC = () => {
  const f = useCurrentFrame();
  const allDone = STEPS[STEPS.length - 1].n * GAP + START + 20;

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(circle at 50% 35%, #0d1410 0%, #000 75%)',
        fontFamily: "'Noto Sans KR', sans-serif",
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Audio src={staticFile('kakao/ep1/s04_audio.m4a')} />
      {STEPS.map((s, i) => (
        <Sfx key={i} at={START + i * GAP} file="pop_appear.mp3" vol={0.32} />
      ))}
      <Sfx at={allDone} file="chime_up.mp3" vol={0.4} />

      <GlowOrb f={f} size={640} />
      <Scanlines opacity={0.05} />

      {/* 헤더 */}
      <div style={{ position: 'absolute', top: 120, textAlign: 'center', opacity: cl(f, 6, 24) }}>
        <div
          style={{
            fontFamily: "'Roboto Mono', monospace",
            fontSize: 16,
            letterSpacing: 6,
            color: LIME,
            marginBottom: 14,
          }}
        >
          TODAY · ROADMAP
        </div>
        <div style={{ fontSize: 60, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
          딱 <span style={{ color: LIME, textShadow: '0 0 30px rgba(170,255,0,0.6)' }}>5단계</span>면 끝납니다
        </div>
      </div>

      {/* 스텝 카드 행 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginTop: 60 }}>
        {STEPS.map((s, i) => {
          const at = START + i * GAP;
          const { opacity, y } = riseFade(f, at, 12, 30);
          const punch = pop(f, at, { damping: 8, stiffness: 260 });
          const lineW = cl(f, at, at + 14, 0, 56);
          return (
            <React.Fragment key={s.n}>
              {i > 0 && (
                <div
                  style={{
                    width: lineW,
                    height: 3,
                    background: `linear-gradient(90deg, ${LIME}, rgba(170,255,0,0.3))`,
                    borderRadius: 2,
                    boxShadow: `0 0 10px rgba(170,255,0,0.4)`,
                  }}
                />
              )}
              <div
                style={{
                  opacity,
                  transform: `translateY(${y}px) scale(${0.85 + punch * 0.15})`,
                  width: 188,
                  padding: '22px 16px',
                  background: 'rgba(0,0,0,0.8)',
                  border: `2px solid ${LIME}`,
                  borderRadius: 16,
                  textAlign: 'center',
                  boxShadow: `0 0 26px rgba(170,255,0,0.18)`,
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    margin: '0 auto 12px',
                    borderRadius: '50%',
                    background: LIME,
                    color: '#000',
                    fontSize: 20,
                    fontWeight: 900,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {s.n}
                </div>
                <div style={{ fontSize: 30, marginBottom: 8 }}>{s.icon}</div>
                <div style={{ fontSize: 19, fontWeight: 800, color: '#fff', lineHeight: 1.3 }}>{s.title}</div>
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 4 }}>{s.sub}</div>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* 10분 컷 배지 */}
      <div
        style={{
          position: 'absolute',
          bottom: 230,
          opacity: cl(f, 150, 170),
          transform: `scale(${0.9 + pop(f, 150, { damping: 7 }) * 0.1})`,
          padding: '12px 28px',
          background: 'rgba(170,255,0,0.12)',
          border: `1.5px solid ${LIME}`,
          borderRadius: 999,
          fontSize: 22,
          fontWeight: 800,
          color: LIME,
        }}
      >
        ⏱ 10분 컷 · 코딩 0줄
      </div>

      <SubBar f={f} subs={SUBS} />
    </AbsoluteFill>
  );
};
