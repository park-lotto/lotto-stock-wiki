/**
 * KK_ChannelSting — 채널 로고 스팅 (21f · 0.7s)
 * 구조상 ①오프닝 ③AI→사람 ⑤사람→AI 총 3회 재사용.
 *
 * 타임라인:
 *   f0~3   화이트 플래시 인
 *   f2~10  로고 글리치 펀치 인
 *   f8~15  홀드 + 펄스
 *   f15~21 스케일업 + 페이드아웃
 * SFX: sting_whoosh@0, sting_hit@3
 */

import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { LIME } from './theme';
import { pop, flashAt, glitchX, cl, Scanlines, GlowOrb, LogoLockup, Sfx } from './fx';

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

  return (
    <AbsoluteFill style={{ background: '#000', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
      <Sfx at={0} file="sting_whoosh.mp3" vol={0.4} />
      <Sfx at={3} file="sting_hit.mp3" vol={0.5} />

      <GlowOrb f={f} size={620} />
      <Scanlines opacity={0.14} />

      {/* 로고 락업 */}
      <div
        style={{
          transform: `translateX(${gx}px) scale(${inScale * holdPulse * outScale})`,
          opacity: outOp * glitchFlicker * cl(f, 1, 5),
        }}
      >
        <LogoLockup scale={1.15} glow={0.85} />
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
    </AbsoluteFill>
  );
};
