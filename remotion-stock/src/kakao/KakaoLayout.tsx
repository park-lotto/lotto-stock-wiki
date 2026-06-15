/**
 * KakaoLayout — 아바타 + 화면녹화 합성 레이아웃
 *
 * fullscreen 모드 (S1~S4, S11~S13 — 나레이션 구간):
 *   아바타 영상이 전체화면을 채우고, 하단 자막 바가 오버레이됨
 *
 * pip 모드 (S5~S10 — 데모 구간):
 *   화면녹화가 전체 배경 → pipEnterAt 프레임부터 아바타가 우하단으로 슬라이드
 *   children = 모션그래픽 오버레이 (하이라이트 박스, STEP 카운터, TECHFEED 등)
 *
 * 파일 위치: remotion-stock/public/kakao/
 *   avatar_s01.mp4 ~ avatar_s13.mp4  (씬별 아바타 클립)
 *   screen_s05.mp4 ~ screen_s10.mp4  (데모 화면녹화)
 */

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { FONT } from '../constants';

// ── PiP 치수 (1920×1080 기준) ──────────────────────────────────────────────
const PIP_W          = 360;
const PIP_H          = 202;   // 16:9
const PIP_MARGIN_R   = 36;    // 우측 마진
const SUBTITLE_H     = 0.16;  // 자막 바 비율
const PIP_MARGIN_B   = 28;    // 자막 바 상단에서 추가 마진

const VIDEO_W = 1920;
const VIDEO_H = 1080;

const PIP_LEFT = VIDEO_W - PIP_W - PIP_MARGIN_R;
const PIP_TOP  = VIDEO_H - VIDEO_H * SUBTITLE_H - PIP_MARGIN_B - PIP_H;

// ── 타입 ───────────────────────────────────────────────────────────────────
export interface SubtitleLine {
  text: string;
  from: number;   // 시작 프레임
  to:   number;   // 끝 프레임
}

interface KakaoLayoutProps {
  /** public/kakao/ 하위 파일명. staticFile() 자동 적용 */
  avatarFile: string;
  /** pip 모드에서 배경으로 쓸 화면녹화 파일명 */
  screenFile?: string;
  /** fullscreen | pip (default: fullscreen) */
  mode?: 'fullscreen' | 'pip';
  /**
   * pip 모드에서 PiP 전환 시작 프레임.
   * 0이면 씬 시작부터 이미 PiP 상태.
   * 양수면 해당 프레임까지 아바타 전체화면 → 이후 PiP 슬라이드.
   */
  pipEnterAt?: number;
  /** 자막 라인 배열 */
  subtitles?: SubtitleLine[];
  /** 모션그래픽 오버레이 (하이라이트 박스, 화살표, TECHFEED 등) */
  children?: React.ReactNode;
}

// ── 헬퍼 ──────────────────────────────────────────────────────────────────
const clamp = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], {
    extrapolateLeft:  'clamp',
    extrapolateRight: 'clamp',
  });

// ── 컴포넌트 ──────────────────────────────────────────────────────────────
export const KakaoLayout: React.FC<KakaoLayoutProps> = ({
  avatarFile,
  screenFile,
  mode = 'fullscreen',
  pipEnterAt = 0,
  subtitles = [],
  children,
}) => {
  const f   = useCurrentFrame();
  const { fps } = useVideoConfig();

  const avatarSrc = staticFile(`kakao/${avatarFile}`);
  const screenSrc = screenFile ? staticFile(`kakao/${screenFile}`) : null;

  // ── PiP 전환 스프링 ────────────────────────────────────────────────────
  const pipProgress = mode === 'pip'
    ? spring({
        frame: Math.max(0, f - pipEnterAt),
        fps,
        config: { damping: 18, stiffness: 140, mass: 1.0 },
        durationInFrames: 38,
      })
    : 0;

  // ── 아바타 위치/크기 보간 ─────────────────────────────────────────────
  const avatarW      = interpolate(pipProgress, [0, 1], [VIDEO_W, PIP_W]);
  const avatarH      = interpolate(pipProgress, [0, 1], [VIDEO_H, PIP_H]);
  const avatarLeft   = interpolate(pipProgress, [0, 1], [0, PIP_LEFT],
    { easing: Easing.out(Easing.cubic), extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const avatarTop    = interpolate(pipProgress, [0, 1], [0, PIP_TOP],
    { easing: Easing.out(Easing.cubic), extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const avatarRadius = interpolate(pipProgress, [0, 1], [0, 16]);
  const avatarBorder = pipProgress > 0.6 ? '2px solid rgba(255,255,255,0.28)' : 'none';

  // ── 화면녹화 투명도 (PiP 전환 중 서서히 등장) ────────────────────────
  const screenOp = mode === 'pip'
    ? clamp(f, pipEnterAt + 4, pipEnterAt + 28)
    : 0;

  // ── 자막 활성 라인 ────────────────────────────────────────────────────
  const activeSub = subtitles.find(s => f >= s.from && f < s.to);

  // ── 자막 바 스타일 ────────────────────────────────────────────────────
  const subBarBg = mode === 'fullscreen'
    ? 'linear-gradient(to top, rgba(0,0,0,0.82) 0%, rgba(0,0,0,0.0) 100%)'
    : 'rgba(0,0,0,0.85)';
  const subBarBorder = mode === 'pip'
    ? '1px solid rgba(255,255,255,0.06)'
    : 'none';

  return (
    <AbsoluteFill style={{ fontFamily: FONT, overflow: 'hidden', background: '#000' }}>

      {/* ── 화면녹화 배경 (pip 모드에서만) ───────────────────────────── */}
      {mode === 'pip' && screenSrc && (
        <AbsoluteFill style={{ opacity: screenOp, zIndex: 1 }}>
          <OffthreadVideo
            src={screenSrc}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        </AbsoluteFill>
      )}

      {/* ── 아바타 동영상 ─────────────────────────────────────────────── */}
      <div style={{
        position:     'absolute',
        left:         avatarLeft,
        top:          avatarTop,
        width:        avatarW,
        height:       avatarH,
        borderRadius: avatarRadius,
        overflow:     'hidden',
        zIndex:       mode === 'pip' ? 20 : 2,
        boxShadow:    pipProgress > 0.3
          ? `0 8px 40px rgba(0,0,0,${0.55 * pipProgress})`
          : 'none',
        outline:      avatarBorder,
      }}>
        <OffthreadVideo
          src={avatarSrc}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>

      {/* ── 모션그래픽 오버레이 (children) ────────────────────────────── */}
      {children && (
        <AbsoluteFill style={{ zIndex: 30, pointerEvents: 'none' }}>
          {children}
        </AbsoluteFill>
      )}

      {/* ── 자막 바 ───────────────────────────────────────────────────── */}
      <div style={{
        position:   'absolute',
        bottom:     0, left: 0, right: 0,
        height:     `${SUBTITLE_H * 100}%`,
        background: subBarBg,
        borderTop:  subBarBorder,
        display:    'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex:     40,
      }}>
        {activeSub && (
          <div style={{
            fontSize:    40,
            fontWeight:  700,
            color:       '#FFFFFF',
            textAlign:   'center',
            paddingInline: 80,
            textShadow:  '0 2px 14px rgba(0,0,0,0.95)',
            lineHeight:  1.35,
          }}>
            {activeSub.text}
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
