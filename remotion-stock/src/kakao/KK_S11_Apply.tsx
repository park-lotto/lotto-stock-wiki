/**
 * KK_S11_Apply — 응용 4종 + 마무리 (744f · 순수 Remotion)
 * Whisper 4세그 자막 + 응용카드 4종 + 고정댓글 CTA + 따뜻한 엔딩.
 */

import React from 'react';
import { AbsoluteFill, Audio, staticFile, useCurrentFrame } from 'remotion';
import { LIME } from './theme';
import { pop, cl, riseFade, GlowOrb, Scanlines, SubBar, Sfx, type Sub } from './fx';

export const KK_S11_APPLY_FRAMES = 744;

const SUBS: Sub[] = [
  { from: 0, to: 162, text: '이 구조만 익히면 응용은 무궁무진합니다.', accent: '무궁무진' },
  { from: 162, to: 397, text: '아침 브리핑, 종목 브리핑, 핵심 일정, 장중 브리핑까지.', accent: '장중 브리핑' },
  { from: 397, to: 628, text: '프롬프트 4개는 고정댓글에 올려둘게요. 몇 줄만 바꾸면 끝.', accent: '고정댓글' },
  { from: 628, to: 744, text: '잘 활용해 보세요. 감사합니다.', accent: '감사합니다' },
];

const APPS = [
  { icon: '🌅', title: '아침 브리핑', sub: '장 시작 전 시황 요약', at: 175 },
  { icon: '🎯', title: '개별 종목 브리핑', sub: '내 종목 리포트·뉴스', at: 205 },
  { icon: '📅', title: '이번 주 핵심 일정', sub: '실적·이벤트 캘린더', at: 235 },
  { icon: '⏱️', title: '장중 매시간 브리핑', sub: '실시간 흐름 추적', at: 265 },
];

export const KK_S11_Apply: React.FC = () => {
  const f = useCurrentFrame();
  const endFade = cl(f, 700, 744, 1, 0.3);

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(circle at 50% 40%, #0d1410 0%, #000 78%)',
        fontFamily: "'Noto Sans KR', sans-serif",
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Audio src={staticFile('kakao/ep1/s11_audio.mp4')} />
      {APPS.map((a, i) => (
        <Sfx key={i} at={a.at} file="pop_appear.mp3" vol={0.32} />
      ))}
      <Sfx at={400} file="chime_up.mp3" vol={0.4} />
      <Sfx at={628} file="end_whoosh.mp3" vol={0.3} />

      <GlowOrb f={f} size={680} />
      <Scanlines opacity={0.05} />

      <div style={{ opacity: endFade, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* 헤더 */}
        <div style={{ textAlign: 'center', opacity: cl(f, 10, 30), marginBottom: 44 }}>
          <div
            style={{
              fontFamily: "'Roboto Mono', monospace",
              fontSize: 16,
              letterSpacing: 6,
              color: LIME,
              marginBottom: 12,
            }}
          >
            APPLY · 응용은 무궁무진
          </div>
          <div style={{ fontSize: 56, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>
            이제 <span style={{ color: LIME, textShadow: '0 0 30px rgba(170,255,0,0.6)' }}>당신만의 무기</span>
          </div>
        </div>

        {/* 응용 카드 2×2 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22, width: 820 }}>
          {APPS.map((a, i) => {
            const { opacity, y } = riseFade(f, a.at, 12, 26);
            const punch = pop(f, a.at, { damping: 8, stiffness: 240 });
            return (
              <div
                key={i}
                style={{
                  opacity,
                  transform: `translateY(${y}px) scale(${0.9 + punch * 0.1})`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 18,
                  padding: '22px 26px',
                  background: 'rgba(0,0,0,0.78)',
                  border: `2px solid rgba(170,255,0,0.5)`,
                  borderRadius: 16,
                  boxShadow: '0 0 22px rgba(170,255,0,0.12)',
                }}
              >
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: 14,
                    background: 'rgba(170,255,0,0.12)',
                    border: `1px solid rgba(170,255,0,0.4)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 30,
                  }}
                >
                  {a.icon}
                </div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: '#fff' }}>{a.title}</div>
                  <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.5)', marginTop: 3 }}>{a.sub}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 고정댓글 CTA */}
        <div
          style={{
            marginTop: 40,
            opacity: cl(f, 405, 425),
            transform: `translateY(${cl(f, 405, 430, 20, 0)}px)`,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '14px 30px',
            background: 'rgba(170,255,0,0.14)',
            border: `1.5px solid ${LIME}`,
            borderRadius: 999,
            fontSize: 22,
            fontWeight: 800,
            color: LIME,
          }}
        >
          📌 프롬프트 4종 → 고정댓글 확인 ↓
        </div>
      </div>

      <SubBar f={f} subs={SUBS} />
    </AbsoluteFill>
  );
};
