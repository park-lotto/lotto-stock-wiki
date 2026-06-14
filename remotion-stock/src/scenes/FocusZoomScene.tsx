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

// ─── FocusZoom: 특정 박스 영역만 줌인, 나머지 어둡게 ──────────────────
// 용도: 문서/화면에서 핵심 문장 강조 후 줌인
// 스티브 파도타기 / T3CHFEED 스타일

export interface FocusBox {
  top: number;
  left: number;
  width: number;
  height: number;
}

interface FocusZoomProps {
  imageSrc: string;         // staticFile 경로 (images/ 상대)
  focusBox: FocusBox;       // 강조할 영역 (1920×1080 기준 px)
  zoomScale?: number;       // 줌 배율 (기본 2.4)
  boxColor?: string;        // 테두리 색 (기본 흰색)
  overlayDark?: number;     // 배경 어두운 정도 0~1 (기본 0.72)
  dimStart?: number;        // 어두워지기 시작 프레임
  zoomStart?: number;       // 줌 시작 프레임
}

export const FocusZoomScene: React.FC<FocusZoomProps> = ({
  imageSrc,
  focusBox,
  zoomScale = 2.4,
  boxColor = 'rgba(255,255,255,0.92)',
  overlayDark = 0.72,
  dimStart = 0,
  zoomStart = 35,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const boxCX = focusBox.left + focusBox.width / 2;
  const boxCY = focusBox.top + focusBox.height / 2;

  // ① 배경 dim
  const darkOpacity = interpolate(
    frame,
    [dimStart, dimStart + 22],
    [0, overlayDark],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  // ② 박스 테두리 등장
  const boxOpacity = interpolate(
    frame,
    [dimStart + 10, dimStart + 24],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );
  const boxScale = spring({
    frame: frame - (dimStart + 10),
    fps,
    config: { damping: 13, stiffness: 190, mass: 0.75 },
  });

  // ③ 줌인 (transformOrigin = 박스 중심)
  const zoom = interpolate(
    frame,
    [zoomStart, zoomStart + 45],
    [1, zoomScale],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  return (
    <AbsoluteFill style={{ backgroundColor: '#000', overflow: 'hidden' }}>

      {/* ── 레이어 1: 배경 이미지 (줌 적용) ── */}
      <div
        style={{
          position: 'absolute', inset: 0,
          transform: `scale(${zoom})`,
          transformOrigin: `${boxCX}px ${boxCY}px`,
        }}
      >
        <Img
          src={staticFile(imageSrc)}
          style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }}
        />

        {/* ── 레이어 2: 전체 dark 오버레이 ── */}
        <div
          style={{
            position: 'absolute', inset: 0,
            backgroundColor: `rgba(0,0,0,${darkOpacity})`,
          }}
        />

        {/* ── 레이어 3: 박스 영역만 원본 밝기로 "구멍 뚫기" ── */}
        <div
          style={{
            position: 'absolute',
            top: focusBox.top - 6,
            left: focusBox.left - 6,
            width: focusBox.width + 12,
            height: focusBox.height + 12,
            overflow: 'hidden',
            borderRadius: 10,
            opacity: boxOpacity,
          }}
        >
          <Img
            src={staticFile(imageSrc)}
            style={{
              position: 'absolute',
              top: -(focusBox.top - 6),
              left: -(focusBox.left - 6),
              width: 1920,
              height: 1080,
              objectFit: 'cover',
              objectPosition: 'top',
            }}
          />
        </div>

        {/* ── 레이어 4: 박스 테두리 ── */}
        <div
          style={{
            position: 'absolute',
            top: focusBox.top - 6,
            left: focusBox.left - 6,
            width: focusBox.width + 12,
            height: focusBox.height + 12,
            border: `2.5px solid ${boxColor}`,
            borderRadius: 10,
            boxShadow: `0 0 32px rgba(255,255,255,0.22), 0 0 8px rgba(255,255,255,0.12)`,
            opacity: boxOpacity,
            transform: `scale(${0.96 + boxScale * 0.04})`,
            transformOrigin: 'center center',
          }}
        />
      </div>

    </AbsoluteFill>
  );
};

export const FOCUS_ZOOM_FRAMES = 180;
