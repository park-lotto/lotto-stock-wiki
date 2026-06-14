import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

// ─── 타이밍 상수 ─────────────────────────────────
const DIM_START   = 0;   // 배경 어두워지기 시작
const DIM_END     = 20;  // 배경 dim 완료
const TEXT_START  = 25;  // 한국어 텍스트 등장 시작
const TEXT_GAP    = 22;  // 텍스트 줄 간격 (프레임)
const FOCUS_START = 110; // FocusCard 등장
const ZOOM_START  = 165; // DocHighlight 줌인 시작
const ZOOM_DUR    = 40;  // 줌인 걸리는 시간

// ─── 콘텐츠 (교체 가능) ──────────────────────────
const KR_LINES = [
  '• 우주에 데이터 센터를 설치하면 지구상의 자원 수요를 줄일 수 있다',
  '• 데이터 센터의 과도한 열 발생 — 우주 냉각은 중대한 엔지니어링 과제',
  '• 궤도 위성 수 증가 시 관리·충돌 위험이 커진다',
];
const SUBTITLE = '우주 데이터센터를 궤도에 배치하는 것은 공학적으로 또 경제적으로 장벽이 있다';

// FocusCard 타겟 — Key Takeaways 섹션 (1920×1080 기준 픽셀)
const FOCUS_BOX = { top: 435, left: 32, width: 1856, height: 260 };

// ─── 메인 컴포넌트 ────────────────────────────────
export const TechFeedScene: React.FC<{
  imageSrc?: string;
  krLines?: string[];
  subtitle?: string;
  focusBox?: { top: number; left: number; width: number; height: number };
}> = ({
  imageSrc = 'images/techfeed_demo.png',
  krLines = KR_LINES,
  subtitle = SUBTITLE,
  focusBox = FOCUS_BOX,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 배경 밝기 dim
  const brightness = interpolate(frame, [DIM_START, DIM_END], [1, 0.32], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // FocusCard spring
  const focusProgress = spring({
    frame: frame - FOCUS_START,
    fps,
    config: { damping: 14, stiffness: 200, mass: 0.7 },
  });
  const focusOpacity = interpolate(frame, [FOCUS_START, FOCUS_START + 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // 줌인 스케일
  const zoomScale = interpolate(frame, [ZOOM_START, ZOOM_START + ZOOM_DUR], [1, 1.55], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // 줌인 Y 오프셋 — FocusCard 중심으로 이동
  const zoomTranslateY = interpolate(frame, [ZOOM_START, ZOOM_START + ZOOM_DUR], [0, -12], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ backgroundColor: '#000', fontFamily: 'Pretendard, Noto Sans KR, sans-serif' }}>

      {/* ── 배경 스크린샷 (dim 처리) ── */}
      <div
        style={{
          position: 'absolute', inset: 0,
          transform: `scale(${zoomScale}) translateY(${zoomTranslateY}%)`,
          transformOrigin: `center ${focusBox.top + focusBox.height / 2}px`,
          transition: 'none',
        }}
      >
        <Img
          src={staticFile(imageSrc)}
          style={{
            width: '100%', height: '100%',
            objectFit: 'cover', objectPosition: 'top',
            filter: `brightness(${brightness})`,
          }}
        />

        {/* ── FocusCard — Key Takeaways 섹션 강조 ── */}
        {frame >= FOCUS_START && (
          <div
            style={{
              position: 'absolute',
              top: focusBox.top,
              left: focusBox.left,
              width: focusBox.width,
              height: focusBox.height,
              border: '2.5px solid rgba(255,255,255,0.88)',
              borderRadius: 10,
              backgroundColor: 'rgba(255,255,255,0.06)',
              boxShadow: '0 0 48px rgba(255,255,255,0.18), inset 0 0 24px rgba(255,255,255,0.04)',
              opacity: focusOpacity,
              transform: `scale(${0.96 + focusProgress * 0.04})`,
              transformOrigin: 'center center',
            }}
          />
        )}
      </div>

      {/* ── 한국어 번역 텍스트 stagger ── */}
      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        {krLines.map((line, i) => {
          const lineStart = TEXT_START + i * TEXT_GAP;
          const opacity = interpolate(frame, [lineStart, lineStart + 14], [0, 1], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          });
          const ty = interpolate(frame, [lineStart, lineStart + 18], [14, 0], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          });
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                top: 52 + i * 76,
                left: 56, right: 56,
                opacity,
                transform: `translateY(${ty}px)`,
                color: '#fff',
                fontSize: 33,
                fontWeight: 700,
                lineHeight: 1.55,
                textShadow: '0 2px 12px rgba(0,0,0,0.85)',
                letterSpacing: '-0.3px',
              }}
            >
              {line}
            </div>
          );
        })}
      </AbsoluteFill>

      {/* ── 하단 자막 바 ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 0, left: 0, right: 0,
          height: 74,
          backgroundColor: 'rgba(0,0,0,0.82)',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', alignItems: 'center',
          paddingLeft: 44,
        }}
      >
        <span style={{ color: '#fff', fontSize: 30, fontWeight: 600, letterSpacing: '-0.2px' }}>
          {subtitle}
        </span>
      </div>

    </AbsoluteFill>
  );
};

export const TECHFEED_DEMO_FRAMES = 240;
