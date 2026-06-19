/**
 * KK_ColdOpen — 콜드오픈 훅 (60f · 2s)
 * 폰 클로즈업 → 카톡 알림 '딩' → 아침 브리핑 메시지 촤르륵.
 * SFX: kakao_ding@15, tick(메시지마다)
 */

import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { LIME } from './theme';
import { pop, cl, riseFade, GlowOrb, Sfx } from './fx';

export const KK_COLDOPEN_FRAMES = 60;

const BRIEF_LINES = [
  '📊 오늘 주도 섹터: 반도체·조선',
  '🔴 수급 빈집: 3종목 포착',
  '📅 핵심 일정 2건',
];

export const KK_ColdOpen: React.FC = () => {
  const f = useCurrentFrame();

  const phoneScale = 0.86 + pop(f, 0, { damping: 14, stiffness: 140 }) * 0.14 + cl(f, 0, 60, 0, 0.06);
  const phoneOp = cl(f, 0, 10);
  const notiPop = pop(f, 15, { damping: 8, stiffness: 300 });
  const notiOp = cl(f, 15, 22);

  return (
    <AbsoluteFill style={{ background: '#000', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
      <Sfx at={15} file="kakao_ding.mp3" vol={0.55} />
      {BRIEF_LINES.map((_, i) => (
        <Sfx key={i} at={28 + i * 9} file="tick.mp3" vol={0.3} />
      ))}

      <GlowOrb f={f} size={560} />

      {/* 폰 목업 */}
      <div
        style={{
          width: 360,
          height: 740,
          borderRadius: 52,
          background: 'linear-gradient(160deg, #1a1a1a 0%, #0a0a0a 100%)',
          border: '6px solid #222',
          boxShadow: '0 0 60px rgba(170,255,0,0.12), inset 0 0 0 2px #000',
          opacity: phoneOp,
          transform: `scale(${phoneScale})`,
          position: 'relative',
          overflow: 'hidden',
          padding: 18,
        }}
      >
        {/* 노치 */}
        <div
          style={{
            position: 'absolute',
            top: 14,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 130,
            height: 26,
            background: '#000',
            borderRadius: 16,
            zIndex: 5,
          }}
        />

        {/* 카톡 알림 배너 */}
        <div
          style={{
            marginTop: 54,
            opacity: notiOp,
            transform: `translateY(${(1 - notiPop) * -30}px) scale(${0.92 + notiPop * 0.08})`,
            background: '#FEE500',
            borderRadius: 18,
            padding: '14px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            boxShadow: '0 8px 28px rgba(0,0,0,0.5)',
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              background: '#3A1D1D',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
            }}
          >
            💬
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 900, color: '#1a1a1a' }}>스탁브레인</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#3a3a3a' }}>아침 브리핑이 도착했어요</div>
          </div>
          <div style={{ fontSize: 11, color: '#7a6a00', fontWeight: 700 }}>지금</div>
        </div>

        {/* 브리핑 메시지 버블 */}
        <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {BRIEF_LINES.map((line, i) => {
            const { opacity, y } = riseFade(f, 28 + i * 9, 8, 16);
            return (
              <div
                key={i}
                style={{
                  opacity,
                  transform: `translateY(${y}px)`,
                  alignSelf: 'flex-start',
                  maxWidth: '92%',
                  background: 'rgba(255,255,255,0.95)',
                  color: '#111',
                  fontSize: 15,
                  fontWeight: 700,
                  padding: '12px 14px',
                  borderRadius: '4px 16px 16px 16px',
                }}
              >
                {line}
              </div>
            );
          })}
        </div>
      </div>

      {/* 하단 라임 라벨 */}
      <div
        style={{
          position: 'absolute',
          bottom: 64,
          fontFamily: "'Roboto Mono', monospace",
          fontSize: 16,
          letterSpacing: 4,
          color: LIME,
          opacity: cl(f, 40, 54),
          textShadow: '0 0 16px rgba(170,255,0,0.7)',
        }}
      >
        매일 아침, 자동으로.
      </div>
    </AbsoluteFill>
  );
};
