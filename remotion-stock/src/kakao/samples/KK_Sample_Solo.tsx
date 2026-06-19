/**
 * [샘플 C] 리모션 단독 부분 — 순수 검정 무대 + 큰 Claude CI 그래픽
 * 레퍼런스 187151(설치)·196152($19)·170150(플랜) 스타일.
 * Free/Pro/Max 플랜 → $19 가격 임팩트.
 */

import React from 'react';
import { useCurrentFrame } from 'remotion';
import { cl, pop, flashAt } from '../fx';
import { Stage, Kicker, Watermark, ClaudeIcon, WireGlobe, ORANGE, ORANGE_GLOW, LIME, SUB } from '../life';

export const KK_SAMPLE_SOLO_FRAMES = 240;

const PLANS = [
  { name: 'Free', sub: '자동화 없음', dim: true },
  { name: 'Pro', sub: '필요', dim: false },
  { name: 'Max', sub: '오버스펙', dim: true },
];

export const KK_Sample_Solo: React.FC = () => {
  const f = useCurrentFrame();

  // Phase1 플랜(0~130) → Phase2 가격(130~)
  const planOut = cl(f, 120, 138, 1, 0);
  const priceIn = cl(f, 138, 156);

  return (
    <Stage>
      <Kicker ch="CH 02" title="THE PLAN" color={ORANGE} f={f} />
      <WireGlobe x="50%" y="50%" size={760} f={f} color={ORANGE} />

      {/* 컷 플래시 */}
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flashAt(f, 132, 8, 0.5), pointerEvents: 'none' }} />

      {/* Phase 1 — 플랜 선택 */}
      {f < 140 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: planOut }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 50, opacity: cl(f, 6, 24) }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: ORANGE }} />
            <span style={{ fontFamily: "'Space Mono',monospace", fontSize: 24, letterSpacing: 6, color: '#fff' }}>요금제 PLAN</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
            {PLANS.map((p, i) => {
              const sp = pop(f, 24 + i * 10, { damping: 9 });
              const isPro = !p.dim;
              return (
                <div
                  key={i}
                  style={{
                    width: isPro ? 300 : 220,
                    height: isPro ? 240 : 190,
                    borderRadius: 22,
                    background: isPro ? 'rgba(217,119,87,0.08)' : 'rgba(255,255,255,0.03)',
                    border: `2px solid ${isPro ? ORANGE : 'rgba(255,255,255,0.12)'}`,
                    boxShadow: isPro ? `0 0 60px ${ORANGE_GLOW}` : 'none',
                    opacity: (p.dim ? 0.4 : 1) * cl(f, 24 + i * 10, 40 + i * 10),
                    transform: `scale(${(p.dim ? 0.92 : 1) * (0.7 + sp * 0.3)})`,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 14,
                  }}
                >
                  <div style={{ fontSize: isPro ? 84 : 56, fontWeight: 900, color: '#fff', letterSpacing: -2 }}>{p.name}</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: isPro ? ORANGE : SUB }}>{p.sub}</div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 56, fontSize: 56, fontWeight: 900, color: '#fff', letterSpacing: -2, opacity: cl(f, 60, 80) }}>
            <span style={{ color: ORANGE, textShadow: `0 0 30px ${ORANGE_GLOW}` }}>Claude Pro</span> 이상의 요금제
          </div>
        </div>
      )}

      {/* Phase 2 — $19 가격 카드 */}
      {f >= 132 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: priceIn }}>
          <div
            style={{
              width: 900,
              padding: '64px 80px',
              borderRadius: 28,
              background: 'rgba(20,16,14,0.92)',
              border: `2px solid ${ORANGE}`,
              boxShadow: `0 0 80px ${ORANGE_GLOW}`,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              transform: `scale(${0.85 + pop(f, 138, { damping: 9 }) * 0.15})`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28 }}>
              <ClaudeIcon size={48} />
              <span style={{ fontFamily: "'Space Mono',monospace", fontSize: 22, letterSpacing: 5, color: ORANGE }}>CLAUDE PRO</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline' }}>
              <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 200, fontWeight: 900, color: ORANGE, letterSpacing: -8, lineHeight: 0.9, textShadow: `0 0 60px ${ORANGE_GLOW}` }}>$</span>
              <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 200, fontWeight: 900, color: '#fff', letterSpacing: -8, lineHeight: 0.9 }}>19</span>
              <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 60, fontWeight: 800, color: SUB, marginLeft: 16 }}>/ month</span>
            </div>
            <div style={{ marginTop: 24, fontSize: 38, fontWeight: 700, color: '#fff' }}>
              월 <span style={{ color: LIME }}>3만원</span> — 수수료 한 번이면 사라질 돈
            </div>
          </div>
        </div>
      )}

      <Watermark />
    </Stage>
  );
};
