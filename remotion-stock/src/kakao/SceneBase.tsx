import React from 'react';
import { AbsoluteFill, Audio, OffthreadVideo, staticFile, useCurrentFrame, interpolate } from 'remotion';
import { LIME } from './theme';

export type Sub = { from: number; to: number; text: string; accent: string };

interface SceneBaseProps {
  /** public 기준 경로. null이면 플레이스홀더 배경(에셋 도착 전 프리뷰용) */
  video: string | null;
  subs: Sub[];
  children: (f: number) => React.ReactNode;
  /** 배경 위 다크닝 정도 (0~1). 그래픽 가독성 ↑ */
  dim?: number;
  /** 나레이션 음성 파일 (public 기준 경로). 화면녹화 없는 그래픽 씬용 */
  audio?: string;
}

export const ClaudeLogo: React.FC<{ size?: number }> = ({ size = 46 }) => (
  <svg width={size} height={size} viewBox="0 0 46 46">
    <rect width="46" height="46" rx="10" fill="#D97757" />
    <rect x="10" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="19.5" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="29" y="10" width="7" height="26" rx="3.5" fill="white" />
  </svg>
);

const KFONT = "'Noto Sans KR', 'Malgun Gothic', sans-serif";

/** 에셋 도착 전 배경 플레이스홀더 */
const PlaceholderBG: React.FC<{ label: string }> = ({ label }) => (
  <AbsoluteFill
    style={{
      background: 'radial-gradient(circle at 50% 40%, #0d1410 0%, #000 70%)',
    }}
  >
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundImage:
          'linear-gradient(rgba(170,255,0,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(170,255,0,0.05) 1px, transparent 1px)',
        backgroundSize: '64px 64px',
      }}
    />
    <div
      style={{
        position: 'absolute',
        top: 28,
        left: 28,
        fontFamily: "'Roboto Mono', monospace",
        fontSize: 13,
        color: 'rgba(170,255,0,0.4)',
        letterSpacing: 2,
      }}
    >
      ▢ 영상 자리 — {label}
    </div>
  </AbsoluteFill>
);

export const SceneBase: React.FC<SceneBaseProps> = ({ video, subs, children, dim = 0, audio }) => {
  const f = useCurrentFrame();
  const activeSub = subs.find((s) => f >= s.from && f < s.to);

  // 자막 등장 애니메이션 (각 큐 시작 기준)
  let subOpacity = 1;
  let subY = 0;
  if (activeSub) {
    const local = f - activeSub.from;
    subOpacity = interpolate(local, [0, 6], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
    subY = interpolate(local, [0, 7], [14, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  }

  return (
    <AbsoluteFill style={{ fontFamily: KFONT, overflow: 'hidden', background: '#000' }}>
      {audio && <Audio src={staticFile(audio)} />}
      {video ? (
        <OffthreadVideo src={staticFile(video)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      ) : (
        <PlaceholderBG label="" />
      )}

      {/* 다크 그라디언트 오버레이 */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: `linear-gradient(to bottom, rgba(0,0,0,${0.2 + dim}) 0%, rgba(0,0,0,${dim}) 28%, rgba(0,0,0,${dim}) 58%, rgba(0,0,0,${0.6 + dim * 0.6}) 100%)`,
        }}
      />

      {/* 씬별 패널 */}
      {children(f)}

      {/* 자막 바 */}
      {activeSub && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '19%',
            background: 'linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.45) 55%, transparent 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              fontFamily: KFONT,
              fontSize: 40,
              fontWeight: 700,
              color: '#fff',
              textAlign: 'center',
              paddingInline: 90,
              maxWidth: '88%',
              lineHeight: 1.4,
              textShadow: '0 2px 18px rgba(0,0,0,0.98)',
              opacity: subOpacity,
              transform: `translateY(${subY}px)`,
            }}
          >
            {activeSub.text.split(activeSub.accent).map((part, i, arr) => (
              <React.Fragment key={i}>
                {part}
                {i < arr.length - 1 && activeSub.accent && (
                  <span style={{ color: LIME, textShadow: `0 0 16px rgba(170,255,0,0.9)` }}>{activeSub.accent}</span>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
