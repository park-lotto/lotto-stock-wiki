/**
 * L30_PipAvatar — PiP 아바타 창
 *
 * 영상 레퍼런스: https://youtu.be/kI1soqlxwl8
 *   - portrait=true: 세로 모드 270×480 (9:16)
 *   - 점 색상: 빨강 #FF2D2D (라임 아님)
 *   - 레이블: "LIVE · 09:16 ●" (시간 우측, 점 끝)
 *   - 테두리: 골드 (기본) or 라임 (circuit 씬)
 */

import React from 'react';
import { interpolate, OffthreadVideo, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { L30C, L30G } from './L30_constants';

// 가로 모드 (16:9)
const PIP_W_LAND   = 400;
const PIP_H_LAND   = 225;
// 세로 모드 (9:16)
const PIP_W_PORT   = 270;
const PIP_H_PORT   = 480;

const PIP_RIGHT    = 44;
const PIP_BOTTOM   = 44;

interface PipAvatarProps {
  avatarFile: string;
  showAt?:    number;
  /** 세로(포트레이트) 모드 — default false */
  portrait?:  boolean;
  /** 레이블 시간 텍스트 e.g. "09:16" — 없으면 "HOST" */
  time?:      string;
  /** 테두리 색 — default gold, 다크씬에서 'lime' */
  borderStyle?: 'gold' | 'lime';
}

export const L30_PipAvatar: React.FC<PipAvatarProps> = ({
  avatarFile,
  showAt      = 0,
  portrait    = false,
  time,
  borderStyle = 'gold',
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const PIP_W = portrait ? PIP_W_PORT : PIP_W_LAND;
  const PIP_H = portrait ? PIP_H_PORT : PIP_H_LAND;

  const progress = spring({
    frame: Math.max(0, f - showAt),
    fps,
    config: { damping: 22, stiffness: 160, mass: 0.85 },
    durationInFrames: 28,
  });

  const opacity    = progress;
  const translateX = interpolate(progress, [0, 1], [PIP_W + 30, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const borderColor = borderStyle === 'lime' ? L30C.limeBorder : L30C.pipGold;
  const boxShadow   = borderStyle === 'lime' ? L30G.lime.boxWk : L30G.gold.box;

  // 레이블: "LIVE · 09:16 ●" or "LIVE · HOST ●"
  const timeText = time ? `LIVE · ${time}` : 'LIVE · HOST';

  return (
    <div style={{
      position:     'absolute',
      right:        PIP_RIGHT,
      bottom:       PIP_BOTTOM,
      width:        PIP_W,
      height:       PIP_H,
      opacity,
      transform:    `translateX(${translateX}px)`,
      zIndex:       50,
      borderRadius: portrait ? 12 : 10,
      overflow:     'hidden',
      border:       `1.5px solid ${borderColor}`,
      boxShadow,
    }}>
      {/* 아바타 비디오 */}
      <OffthreadVideo
        src={staticFile(`kakao/${avatarFile}`)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* "LIVE · 09:16 ●" 레이블 (좌상단) */}
      <div style={{
        position:      'absolute',
        top:           10,
        left:          12,
        display:       'flex',
        alignItems:    'center',
        gap:           6,
        pointerEvents: 'none',
      }}>
        <span style={{
          fontFamily:    L30C.fontMono,
          fontSize:      9,
          fontWeight:    400,
          letterSpacing: '2px',
          textTransform: 'uppercase',
          color:         '#FFFFFF',
        }}>
          {timeText}
        </span>
        {/* 빨간 점 — 오른쪽 끝 */}
        <div style={{
          width:     6,
          height:    6,
          borderRadius: '50%',
          background: '#FF2D2D',
          boxShadow:  '0 0 5px #FF2D2D, 0 0 10px #FF000055',
          flexShrink: 0,
        }} />
      </div>
    </div>
  );
};
