/**
 * KK_ChannelSting — 채널 로고 스팅 (21f · 0.7s · life.tsx 디자인)
 * 구조상 ①오프닝 ③AI→사람 ⑤사람→AI 총 3회 재사용.
 *
 * 타임라인:
 *   f0~4   화이트 플래시 인
 *   f2~10  로고 글리치 펀치 인
 *   f8~15  홀드 + 펄스
 *   f15~21 스케일업 + 페이드아웃
 * SFX: sting_whoosh@0, sting_hit@3
 * 골든 레퍼런스: KK_S3_L30.tsx (Stage·ClaudeIcon·STOCKBRAIN)
 */

import React from 'react';
import { useCurrentFrame } from 'remotion';
import { pop, flashAt, glitchX, cl, Sfx } from './fx';
import { Stage, ClaudeIcon, LIME, LIME_GLOW } from './life';

export const KK_CHANNELSTING_FRAMES = 21;

export const KK_ChannelSting: React.FC = () => {
  const f = useCurrentFrame();

  const inScale = 0.7 + pop(f, 2, { damping: 8, stiffness: 320, mass: 0.6 }) * 0.3;
  const gx = glitchX(f, 3, 9, 7);
  const flash = flashAt(f, 0, 4, 0.7);
  const holdPulse = 1 + Math.sin(f * 0.6) * 0.02;
  const outScale = cl(f, 15, 21, 1, 1.12);
  const outOp = cl(f, 16, 21, 1, 0);
  const glitchFlicker = f >= 3 && f <= 9 && f % 2 === 0 ? 0.6 : 1;
  const logoOp = outOp * glitchFlicker * cl(f, 1, 5);

  return (
    <Stage baseline={false}>
      <Sfx at={0} file="sting_whoosh.mp3" vol={0.4} />
      <Sfx at={3} file="sting_hit.mp3" vol={0.5} />

      {/* 라임 라디얼 글로우 */}
      <div style={{ position: 'absolute', left: '50%', top: '50%', width: 900, height: 900, transform: `translate(-50%,-50%) scale(${holdPulse})`, borderRadius: '50%', background: `radial-gradient(circle, ${LIME}22 0%, transparent 62%)`, opacity: cl(f, 2, 8) * outOp, pointerEvents: 'none' }} />

      {/* 로고 락업 (ClaudeIcon + STOCKBRAIN) */}
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 26, transform: `translateX(${gx}px) scale(${inScale * holdPulse * outScale})`, opacity: logoOp }}>
          <ClaudeIcon size={96} />
          <div style={{ fontFamily: "'Noto Sans KR',sans-serif", fontSize: 92, fontWeight: 900, letterSpacing: -2, color: '#fff', textShadow: '0 2px 24px rgba(0,0,0,0.6)' }}>
            STOCK<span style={{ color: LIME, textShadow: `0 0 30px ${LIME_GLOW}` }}>BRAIN</span>
          </div>
        </div>
      </div>

      {/* 글리치 라임 슬릿 */}
      {f >= 3 && f <= 9 && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: 0,
            right: 0,
            height: 3,
            background: LIME,
            opacity: 0.7,
            transform: `translateY(${Math.sin(f * 9) * 40}px)`,
            boxShadow: `0 0 20px ${LIME}`,
          }}
        />
      )}

      {/* 화이트 플래시 */}
      <div style={{ position: 'absolute', inset: 0, background: '#fff', opacity: flash, pointerEvents: 'none' }} />
    </Stage>
  );
};
