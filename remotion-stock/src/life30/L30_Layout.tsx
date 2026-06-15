/**
 * L30_Layout — LIFE 3.0 마스터 레이아웃
 *
 * 두 가지 모드:
 *   fullscreen — 아바타 영상이 전체화면, 데이터 카드가 그 위에 오버레이
 *   pip        — 블랙 또는 커스텀 배경, 아바타는 우하단 골드 PiP
 *
 * HUD (CH 레이블 + 타임코드)는 항상 최상단에 렌더링됨
 * 자막은 하단 그라데이션 바에 표시
 *
 * 사용법 예시:
 *   // S1 훅 — 아바타 전체화면 + 데이터 카드 오버레이
 *   <L30_Layout
 *     avatarFile="avatar_s01.mp4"
 *     mode="fullscreen"
 *     chapter="01" chapterTitle="HOOK"
 *     timeStart="00:00" timeEnd="00:40"
 *     subtitles={SUBTITLES}
 *   >
 *     <L30_TimestampCard ... />
 *     <L30_LogoCard ... />
 *   </L30_Layout>
 *
 *   // S4 로드맵 — 블랙 배경 + 인포그래픽 + PiP 아바타
 *   <L30_Layout
 *     avatarFile="avatar_s04.mp4"
 *     mode="pip"
 *     chapter="04" chapterTitle="ROADMAP"
 *     timeStart="01:32" timeEnd="01:48"
 *   >
 *     <L30_BarChart bars={...} />
 *   </L30_Layout>
 */

import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { L30C } from './L30_constants';
import { L30_HUD } from './L30_HUD';
import { L30_PipAvatar } from './L30_PipAvatar';

export interface L30SubtitleLine {
  text:  string;
  from:  number;
  to:    number;
}

interface L30_LayoutProps {
  // 아바타
  avatarFile?: string;              // public/kakao/ 파일명
  mode?:       'fullscreen' | 'pip';
  pipShowAt?:  number;

  // HUD
  chapter:      string;   // "01"
  chapterTitle: string;   // "HOOK"
  timeStart:    string;   // "00:00"
  timeEnd:      string;   // "00:40"

  // 자막
  subtitles?: L30SubtitleLine[];

  // 데이터 오버레이 (children)
  children?: React.ReactNode;
}

export const L30_Layout: React.FC<L30_LayoutProps> = ({
  avatarFile,
  mode       = 'fullscreen',
  pipShowAt  = 0,
  chapter,
  chapterTitle,
  timeStart,
  timeEnd,
  subtitles  = [],
  children,
}) => {
  const f = useCurrentFrame();

  const activeSub = subtitles.find(s => f >= s.from && f < s.to);

  // 자막 페이드
  const subOp = activeSub
    ? interpolate(f, [activeSub.from, activeSub.from + 6], [0, 1], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      })
    : 0;

  return (
    <AbsoluteFill style={{
      background:  L30C.bg,
      fontFamily:  L30C.fontMain,
      overflow:    'hidden',
    }}>

      {/* ── 아바타 전체화면 (fullscreen 모드) ─────────────────────── */}
      {mode === 'fullscreen' && avatarFile && (
        <AbsoluteFill style={{ zIndex: 1 }}>
          <OffthreadVideo
            src={staticFile(`kakao/${avatarFile}`)}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        </AbsoluteFill>
      )}

      {/* ── 데이터 오버레이 (children) ──────────────────────────────── */}
      {children && (
        <AbsoluteFill style={{ zIndex: 10, pointerEvents: 'none' }}>
          {children}
        </AbsoluteFill>
      )}

      {/* ── PiP 아바타 (pip 모드) ───────────────────────────────────── */}
      {mode === 'pip' && avatarFile && (
        <L30_PipAvatar
          avatarFile={avatarFile}
          showAt={pipShowAt}
        />
      )}

      {/* ── HUD (항상 최상단) ────────────────────────────────────────── */}
      <L30_HUD
        chapter={chapter}
        title={chapterTitle}
        timeStart={timeStart}
        timeEnd={timeEnd}
      />

      {/* ── 자막 바 ─────────────────────────────────────────────────── */}
      {activeSub && (
        <div style={{
          position:   'absolute',
          bottom:     0, left: 0, right: 0,
          padding:    '32px 80px 36px',
          background: mode === 'fullscreen'
            ? 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0) 100%)'
            : 'linear-gradient(to top, rgba(0,0,0,0.80) 0%, rgba(0,0,0,0) 100%)',
          zIndex:     90,
          opacity:    subOp,
        }}>
          <span style={{
            fontFamily:  L30C.fontMain,
            fontSize:    36,
            fontWeight:  700,
            color:       L30C.white,
            lineHeight:  1.45,
            textShadow:  '0 2px 14px rgba(0,0,0,0.95)',
          }}>
            {activeSub.text}
          </span>
        </div>
      )}

    </AbsoluteFill>
  );
};
