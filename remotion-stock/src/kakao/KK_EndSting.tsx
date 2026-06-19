/**
 * KK_EndSting — 마무리 스팅 (110f · 3.7s)
 *
 * 타임라인:
 *   f0~6    화이트 플래시 + sting_hit
 *   f4~28   로고 락업 펀치 인
 *   f30~50  "구독" CTA
 *   f44~64  "좋아요" CTA
 *   f58~80  "고정댓글 확인" CTA
 *   f90~110 페이드아웃 + end_whoosh
 */

import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { LIME } from './theme';
import { pop, flashAt, cl, riseFade, Scanlines, GlowOrb, LogoLockup, Sfx } from './fx';

export const KK_ENDSTING_FRAMES = 110;

const CTAS = [
  { icon: '🔔', label: '구독', sub: 'SUBSCRIBE', at: 30, color: '#FF4455' },
  { icon: '👍', label: '좋아요', sub: 'LIKE', at: 44, color: LIME },
  { icon: '📌', label: '고정댓글 프롬프트 확인', sub: 'PINNED', at: 58, color: '#FFFFFF' },
];

export const KK_EndSting: React.FC = () => {
  const f = useCurrentFrame();

  const logoScale = 0.8 + pop(f, 4, { damping: 12, stiffness: 200 }) * 0.2;
  const logoOp = cl(f, 4, 16);
  const flash = flashAt(f, 0, 6, 0.6);
  const fadeOut = cl(f, 92, 110, 1, 0);

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(circle at 50% 38%, #0d1410 0%, #000 75%)',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
      <Sfx at={0} file="sting_hit.mp3" vol={0.5} />
      <Sfx at={30} file="pop_appear.mp3" vol={0.4} />
      <Sfx at={44} file="pop_appear.mp3" vol={0.4} />
      <Sfx at={58} file="pop_appear.mp3" vol={0.4} />
      <Sfx at={92} file="end_whoosh.mp3" vol={0.4} />

      <GlowOrb f={f} size={680} />
      <Scanlines opacity={0.06} />

      <div style={{ opacity: fadeOut, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 46 }}>
        {/* 로고 */}
        <div style={{ transform: `scale(${logoScale})`, opacity: logoOp }}>
          <LogoLockup scale={1.3} glow={0.9} />
        </div>

        {/* CTA 3종 */}
        <div style={{ display: 'flex', gap: 26 }}>
          {CTAS.map((c, i) => {
            const { opacity, y } = riseFade(f, c.at, 12, 22);
            const punch = pop(f, c.at, { damping: 7, stiffness: 280 });
            return (
              <div
                key={i}
                style={{
                  opacity,
                  transform: `translateY(${y}px) scale(${0.9 + punch * 0.1})`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '16px 26px',
                  background: 'rgba(0,0,0,0.7)',
                  border: `2px solid ${c.color}`,
                  borderRadius: 14,
                  boxShadow: `0 0 22px ${c.color}55`,
                }}
              >
                <span style={{ fontSize: 30 }}>{c.icon}</span>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 900, color: '#fff' }}>{c.label}</div>
                  <div
                    style={{
                      fontFamily: "'Roboto Mono', monospace",
                      fontSize: 10,
                      color: c.color,
                      letterSpacing: 3,
                    }}
                  >
                    {c.sub}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flash, pointerEvents: 'none' }} />
    </AbsoluteFill>
  );
};
