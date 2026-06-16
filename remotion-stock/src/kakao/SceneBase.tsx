import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame } from 'remotion';
import { LIME } from './theme';

export type Sub = { from: number; to: number; text: string; accent: string };

interface SceneBaseProps {
  video: string;
  subs: Sub[];
  children: (f: number) => React.ReactNode;
}

export const ClaudeLogo: React.FC<{ size?: number }> = ({ size = 46 }) => (
  <svg width={size} height={size} viewBox="0 0 46 46">
    <rect width="46" height="46" rx="10" fill="#D97757" />
    <rect x="10" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="19.5" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="29" y="10" width="7" height="26" rx="3.5" fill="white" />
  </svg>
);

export const SceneBase: React.FC<SceneBaseProps> = ({ video, subs, children }) => {
  const f = useCurrentFrame();
  const activeSub = subs.find(s => f >= s.from && f < s.to);

  return (
    <AbsoluteFill style={{ fontFamily: "'Inter', sans-serif", overflow: 'hidden', background: '#000' }}>

      <OffthreadVideo
        src={staticFile(video)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* 다크 그라디언트 오버레이 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.2) 0%, transparent 28%, transparent 60%, rgba(0,0,0,0.55) 100%)',
      }} />

      {/* 씬별 패널 */}
      {children(f)}

      {/* 자막 바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '17%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: 36, fontWeight: 700, color: '#fff',
            textAlign: 'center', paddingInline: 80,
            textShadow: '0 2px 16px rgba(0,0,0,0.95)',
            lineHeight: 1.4,
          }}>
            {activeSub.text.split(activeSub.accent).map((part, i, arr) => (
              <React.Fragment key={i}>
                {part}
                {i < arr.length - 1 && (
                  <span style={{ color: LIME, textShadow: `0 0 12px rgba(170,255,0,0.85)` }}>
                    {activeSub.accent}
                  </span>
                )}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
