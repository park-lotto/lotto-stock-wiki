/**
 * PostFX — 시네마틱 후처리 래퍼 v2
 *
 * v1 문제점 수정:
 *  - 그레인: overlay → screen 블렌드 (검정 배경에서 보임)
 *  - 스캔라인: 검정→검정 대신 흰 줄 방식 (어두운 배경에서 보임)
 *  - 컬러 그레이딩: 값 강화
 *  - 비네팅: 중앙 민트 글로우 + 가장자리 검정
 *  - 크로마틱: 좌우 R/B 엣지 그라데이션
 */

import React from 'react';
import { useCurrentFrame } from 'remotion';

interface PostFXProps {
  children: React.ReactNode;
  grain?: number;      // 0-1 (기본 0.12)
  vignette?: number;  // 0-1 (기본 0.80)
  scanlines?: boolean;
  grade?: boolean;
  chromatic?: boolean;
  /** 라이트 모드 (흰 배경) — 스캔라인·비네팅 조정 */
  light?: boolean;
}

export const PostFX: React.FC<PostFXProps> = ({
  children,
  grain = 0.12,
  vignette = 0.80,
  scanlines = true,
  grade = true,
  chromatic = true,
  light = false,
}) => {
  const f = useCurrentFrame();
  const seed = Math.floor(f / 2) % 60;
  const gid  = `pfx-${seed}`;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>

      {/* ── 1. 컬러 그레이딩 ── */}
      <div style={{
        position: 'absolute', inset: 0,
        filter: grade
          ? `contrast(1.18) brightness(${light ? 0.96 : 0.88}) saturate(0.78)`
          : undefined,
      }}>
        {children}
      </div>

      {/* ── 2. 스캔라인
           dark: 밝은 얇은 줄 (어두운 배경에서 미세하게 빛남)
           light: 어두운 얇은 줄 (밝은 배경에서 미세하게 어두움)
      ── */}
      {scanlines && (
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: light
            ? `repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.07) 3px, rgba(0,0,0,0.07) 4px)`
            : `repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.04) 3px, rgba(255,255,255,0.04) 4px)`,
          pointerEvents: 'none',
          zIndex: 88,
        }} />
      )}

      {/* ── 3. 크로마틱 어버레이션 (좌=빨강 / 우=파랑 엣지) ── */}
      {chromatic && !light && (
        <div style={{
          position: 'absolute', inset: 0,
          background: `linear-gradient(
            90deg,
            rgba(255,20,60,0.07)  0%,
            transparent           4%,
            transparent          96%,
            rgba(20,80,255,0.07) 100%
          )`,
          pointerEvents: 'none',
          zIndex: 89,
        }} />
      )}

      {/* ── 4. 비네팅 + 중앙 민트 앰비언트 ── */}
      <div style={{
        position: 'absolute', inset: 0,
        background: light
          ? `radial-gradient(ellipse at 50% 50%,
              transparent               40%,
              rgba(0,0,0,${vignette * 0.35}) 72%,
              rgba(0,0,0,${vignette * 0.55}) 100%)`
          : `radial-gradient(ellipse at 50% 50%,
              rgba(0,255,208,0.025)      0%,
              transparent               30%,
              rgba(0,0,0,${vignette * 0.45}) 65%,
              rgba(0,0,0,${vignette * 0.88}) 88%,
              rgba(0,0,0,${vignette})        100%)`,
        pointerEvents: 'none',
        zIndex: 90,
      }} />

      {/* ── 5. 필름 그레인
           screen 블렌드: 노이즈 밝은 부분이 아래 레이어 위에 더해짐
           → 검정 배경에서도 밝은 노이즈 스펙클이 보임
      ── */}
      <svg
        style={{
          position: 'absolute', inset: 0,
          width: '100%', height: '100%',
          opacity: grain,
          mixBlendMode: light ? 'multiply' : 'screen',
          pointerEvents: 'none',
          zIndex: 91,
        }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <filter id={gid} x="0%" y="0%" width="100%" height="100%"
            colorInterpolationFilters="sRGB">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.68 0.72"
              numOctaves="4"
              seed={seed}
            />
            <feColorMatrix type="saturate" values="0" />
          </filter>
        </defs>
        <rect width="100%" height="100%" filter={`url(#${gid})`} />
      </svg>

    </div>
  );
};
