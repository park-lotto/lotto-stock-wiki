/**
 * [샘플 A] AI 영상 부분 — Veo 호스트 + 플로팅 인포카드
 * 레퍼런스 114156·130155·157160 (LIFE 3.0 AI 호스트) 스타일.
 * 얼굴 안 가리고 모서리 카드 + 로어서드만.
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame } from 'remotion';
import { cl, pop } from '../fx';
import { Kicker, Watermark, FloatCard, LowerThird, WireGlobe, ClaudeIcon, LIME, ORANGE, SUB } from '../life';

export const KK_SAMPLE_AI_FRAMES = 240;

const RANK = [
  { n: '01', name: '정보 정리', v: '∞' },
  { n: '02', name: '수급 빈집', v: '↑' },
  { n: '03', name: '주도 섹터', v: '🔥' },
];

export const KK_Sample_AI: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: '#000' }}>
      <OffthreadVideo src={staticFile('kakao/ep1/intro.mp4')} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />

      {/* 좌상단 카드 뒤 부분 그라디언트만 (얼굴 보존) */}
      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(105deg, rgba(0,0,0,0.55) 0%, transparent 32%, transparent 68%, rgba(0,0,0,0.5) 100%)', pointerEvents: 'none' }} />

      <Kicker ch="EP 01" title="STOCK BRAIN" f={f} />

      {/* 좌상단: 거대 수치 카드 */}
      <FloatCard kicker="TODAY · 누적 인사이트" accent={LIME} f={f} at={20} style={{ left: 56, top: 110, width: 300 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 76, fontWeight: 900, color: '#fff', letterSpacing: -2, lineHeight: 1 }}>420</span>
          <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 30, fontWeight: 800, color: LIME }}>건+</span>
        </div>
        <div style={{ fontSize: 16, color: SUB, marginTop: 6 }}>매일 복리로 쌓이는 중</div>
      </FloatCard>

      {/* 좌측: Claude 연동 배지 */}
      <FloatCard kicker="ENGINE" accent={ORANGE} f={f} at={46} style={{ left: 56, top: 300, width: 300, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ClaudeIcon size={42} />
          <div>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>Claude</div>
            <div style={{ fontSize: 14, color: SUB }}>제2의 두뇌</div>
          </div>
        </div>
      </FloatCard>

      {/* 우측 세로 리스트 */}
      <div style={{ position: 'absolute', right: 56, top: 130, width: 320, opacity: cl(f, 60, 80) }}>
        <div style={{ fontFamily: "'Space Mono',monospace", fontSize: 14, letterSpacing: 4, color: LIME, marginBottom: 14, textAlign: 'right' }}>
          STOCKBRAIN · 핵심 3축
        </div>
        {RANK.map((r, i) => {
          const p = pop(f, 70 + i * 12, { damping: 10 });
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '14px 18px',
                marginBottom: 10,
                background: 'rgba(0,0,0,0.6)',
                borderRight: `3px solid ${LIME}`,
                borderRadius: '8px 0 0 8px',
                backdropFilter: 'blur(6px)',
                opacity: cl(f, 70 + i * 12, 84 + i * 12),
                transform: `translateX(${(1 - p) * 30}px)`,
              }}
            >
              <span style={{ fontFamily: "'Space Mono',monospace", fontSize: 18, color: SUB }}>{r.n}</span>
              <span style={{ flex: 1, fontSize: 24, fontWeight: 800, color: '#fff' }}>{r.name}</span>
              <span style={{ fontSize: 24 }}>{r.v}</span>
            </div>
          );
        })}
      </div>

      <WireGlobe x="50%" y="118%" size={900} f={f} color={LIME} />

      <LowerThird tagline="A space for your money to think." accent={LIME} f={f} at={110} />

      <Watermark />
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: '#FF4455', boxShadow: '0 0 12px #FF4455' }} />
    </AbsoluteFill>
  );
};
