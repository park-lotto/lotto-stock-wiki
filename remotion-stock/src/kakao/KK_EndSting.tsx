/**
 * KK_EndSting — 마무리 스팅 (110f · 3.7s · life.tsx 디자인)
 *
 * 타임라인:
 *   f0~6    화이트 플래시 + sting_hit
 *   f4~28   로고 락업 펀치 인 (ClaudeIcon + STOCKBRAIN)
 *   f30~50  "구독" CTA
 *   f44~64  "좋아요" CTA
 *   f58~80  "고정댓글 확인" CTA
 *   f90~110 페이드아웃 + end_whoosh
 * 골든 레퍼런스: KK_S3_L30.tsx
 */

import React from 'react';
import { useCurrentFrame } from 'remotion';
import { pop, flashAt, cl, riseFade, Sfx } from './fx';
import { Stage, ClaudeIcon, LIME, LIME_GLOW, RED, SUB } from './life';

export const KK_ENDSTING_FRAMES = 110;

const MONO = "'Space Mono','Roboto Mono',monospace";
const KFONT = "'Noto Sans KR',sans-serif";

const CTAS = [
  { icon: '🔔', label: '구독', sub: 'SUBSCRIBE', at: 30, color: RED },
  { icon: '👍', label: '좋아요', sub: 'LIKE', at: 44, color: LIME },
  { icon: '📌', label: '고정댓글 프롬프트 확인', sub: 'PINNED', at: 58, color: '#FFFFFF' },
];

export const KK_EndSting: React.FC = () => {
  const f = useCurrentFrame();

  const logoScale = 0.8 + pop(f, 4, { damping: 12, stiffness: 200 }) * 0.2;
  const logoOp = cl(f, 4, 16);
  const flash = flashAt(f, 0, 6, 0.6);
  const fadeOut = cl(f, 92, 110, 1, 0);
  const glowPulse = 1 + Math.sin(f * 0.12) * 0.03;

  return (
    <Stage>
      <Sfx at={0} file="sting_hit.mp3" vol={0.5} />
      <Sfx at={30} file="pop_appear.mp3" vol={0.4} />
      <Sfx at={44} file="pop_appear.mp3" vol={0.4} />
      <Sfx at={58} file="pop_appear.mp3" vol={0.4} />
      <Sfx at={92} file="end_whoosh.mp3" vol={0.4} />

      {/* 라임 라디얼 글로우 */}
      <div style={{ position: 'absolute', left: '50%', top: '42%', width: 1000, height: 1000, transform: `translate(-50%,-50%) scale(${glowPulse})`, borderRadius: '50%', background: `radial-gradient(circle, ${LIME}1f 0%, transparent 60%)`, opacity: cl(f, 4, 16) * fadeOut, pointerEvents: 'none' }} />

      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 46, opacity: fadeOut }}>
        {/* 로고 락업 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, transform: `scale(${logoScale})`, opacity: logoOp }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <ClaudeIcon size={88} />
            <div style={{ fontFamily: KFONT, fontSize: 84, fontWeight: 900, letterSpacing: -2, color: '#fff', textShadow: '0 2px 24px rgba(0,0,0,0.6)' }}>
              STOCK<span style={{ color: LIME, textShadow: `0 0 30px ${LIME_GLOW}` }}>BRAIN</span>
            </div>
          </div>
          <div style={{ fontFamily: MONO, fontSize: 18, letterSpacing: 5, color: SUB }}>정보의 홍수에서 인사이트만</div>
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
                  <div style={{ fontFamily: KFONT, fontSize: 22, fontWeight: 900, color: '#fff' }}>{c.label}</div>
                  <div style={{ fontFamily: MONO, fontSize: 10, color: c.color, letterSpacing: 3 }}>{c.sub}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flash, pointerEvents: 'none' }} />
    </Stage>
  );
};
