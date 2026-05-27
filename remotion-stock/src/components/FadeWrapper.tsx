import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { SDUR } from '../constants';

// FadeWrapper 자체가 검은 배경 → 씬 fadeIn 투명구간에도 체커보드 없음
// 종료: dur-50 → dur-30 프레임 검은 오버레이 페이드인
// dur 기본값 = SDUR(180). 12초 씬은 dur={360} 전달.
export const FadeWrapper: React.FC<{ children: React.ReactNode; dur?: number }> = ({ children, dur = SDUR }) => {
  const f = useCurrentFrame();

  const endOp = interpolate(f, [dur - 50, dur - 30], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ background: '#000000' }}>
      {children}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: '#000000',
        opacity: endOp,
        pointerEvents: 'none',
      }} />
    </AbsoluteFill>
  );
};
