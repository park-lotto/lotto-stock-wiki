/**
 * DocumentHighlightScene.tsx
 *
 * T3CHFEED 스타일: 문서·리포트 스크린샷 → 크롭 줌인 → 형광펜 연출
 *
 * 제미나이 코드의 clip-path 버그를 수정:
 *   clip-path는 숨기기만 할 뿐 확대 안 됨.
 *   올바른 방법: scale(S) translate(tx%, ty%) 조합.
 *
 * ─────────────────────────────────────────────────────────────
 * 컴포넌트 2종:
 *
 * ① DocumentHighlightScene
 *    단일 crop 영역 + 형광펜 하이라이트 1~N개
 *    용도: 리포트 한 구역 줌인, 수치 강조
 *
 * ② DocPanScene
 *    세그먼트 배열로 동일 문서 내 여러 구역을 부드럽게 팬
 *    용도: 한 페이지에서 여러 핵심 수치 순차 강조
 *
 * ─────────────────────────────────────────────────────────────
 * 사용 예시:
 *
 *   <Series.Sequence durationInFrames={150}>
 *     <DocumentHighlightScene
 *       imageSrc="images/samsung_report.png"
 *       crop={{ top: 35, right: 5, bottom: 45, left: 5 }}
 *       highlights={[{ top: 48, left: 8, width: 60, height: 12, delay: 45 }]}
 *       caption="2Q26 OPM 13.2% — 컨센서스 대비 +2.1%p 상회"
 *       tag={{ text: "삼성전기 실적발표", sub: "2026.06.13" }}
 *     />
 *   </Series.Sequence>
 */

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { C, FONT } from '../constants';

// ── 타입 정의 ─────────────────────────────────────────────────

/** 이미지에서 줌인할 영역 (각 방향에서 잘라낼 % 지정) */
export interface CropRegion {
  top: number;     // 이미지 위쪽에서 잘라낼 % — 0이면 잘리지 않음
  right: number;   // 이미지 오른쪽에서 잘라낼 %
  bottom: number;  // 이미지 아래쪽에서 잘라낼 %
  left: number;    // 이미지 왼쪽에서 잘라낼 %
}

/**
 * 형광펜 바 하나.
 * top/left/width/height 는 팝업 컨테이너(표시 영역) 기준 %.
 * 즉, 줌인 후 보이는 화면을 100%×100%로 봤을 때의 위치.
 */
export interface HighlightBar {
  top: number;       // 표시 영역 세로 위치 %
  left: number;      // 표시 영역 가로 위치 %
  width: number;     // 형광펜 너비 %
  height: number;    // 형광펜 높이 %
  color?: string;    // 기본값: '#FFE500'
  delay?: number;    // 애니메이션 시작 딜레이 (프레임), 기본 45
  animDur?: number;  // 그어지는 데 걸리는 프레임 수, 기본 18
}

/** 우측 하단 출처 태그 (T3CHFEED의 "STARLINK FACTORY" 스타일) */
export interface LocationTag {
  text: string;  // 굵은 텍스트. 예: "골드만삭스 리포트"
  sub?: string;  // 작은 텍스트. 예: "2026.06.13"
}

// ── 크롭 줌 계산 헬퍼 ────────────────────────────────────────

/**
 * clip-path 대신 scale + translate 조합으로 크롭+줌을 구현.
 *
 * 원리:
 *   1. crop 영역의 가로/세로 비율을 계산
 *   2. 그 영역이 컨테이너를 꽉 채우도록 배율(scale) 산출
 *   3. crop 영역 중심이 컨테이너 중앙에 오도록 translate 산출
 *
 * CSS에서 transform: scale(S) translate(tx%, ty%) 순서 적용 시:
 *   screen_x = 0.5 + S * (cx + tx/100 - 0.5) = 0.5 가 되려면
 *   tx = (0.5 - cx) * 100  (scale에 독립적)
 */
function calcCropZoom(crop: CropRegion): { scale: number; tx: number; ty: number } {
  const regionW = (100 - crop.left - crop.right) / 100;
  const regionH = (100 - crop.top  - crop.bottom) / 100;

  // 더 큰 쪽을 기준으로 맞춰 crop 영역 전체가 보이도록 (letterbox)
  const scale = 1 / Math.max(regionW, regionH);

  // crop 영역의 중심 (0~1 정규화)
  const cx = (crop.left / 100 + (1 - crop.right  / 100)) / 2;
  const cy = (crop.top  / 100 + (1 - crop.bottom / 100)) / 2;

  return {
    scale,
    tx: (0.5 - cx) * 100,
    ty: (0.5 - cy) * 100,
  };
}

// ── ① DocumentHighlightScene ─────────────────────────────────

export interface DocHighlightProps {
  imageSrc: string;
  crop: CropRegion;
  highlights?: HighlightBar[];
  caption?: string;
  tag?: LocationTag;
}

export const DocumentHighlightScene: React.FC<DocHighlightProps> = ({
  imageSrc, crop, highlights = [], caption, tag,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 씬 페이드인
  const fadeIn = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: 'clamp' });

  // 팝업 등장 — Spring 탄성 (damping 낮을수록 더 통통 튐)
  const entrance = spring({
    frame,
    fps,
    from: 0,
    to: 1,
    config: { damping: 14, stiffness: 120, mass: 1 },
  });

  // 배경 미세 켄번스 (정지 느낌 방지)
  const bgScale = interpolate(frame, [0, 180], [1.0, 1.06], { extrapolateRight: 'clamp' });

  // 크롭 줌 계산
  const { scale: cropScale, tx, ty } = calcCropZoom(crop);

  // 자막 / 태그 타이밍
  const captionOp = interpolate(frame, [30, 50], [0, 1], { extrapolateRight: 'clamp' });
  const tagOp     = interpolate(frame, [20, 40], [0, 1], { extrapolateRight: 'clamp' });
  const tagX      = interpolate(frame, [20, 40], [20, 0], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  const hasCaption = Boolean(caption);

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>

      {/* ── LAYER 1: 블러 배경 (원본 이미지 흐리게) ── */}
      <div style={{
        position: 'absolute',
        inset: -30,            // 블러 엣지 아티팩트 제거
        transform: `scale(${bgScale})`,
        transformOrigin: 'center center',
      }}>
        <Img
          src={staticFile(imageSrc)}
          style={{
            width: '100%', height: '100%',
            objectFit: 'cover',
            filter: 'blur(18px) brightness(0.25) saturate(0.6)',
          }}
        />
      </div>

      {/* ── LAYER 2: 팝업 컨테이너 (Spring 등장) ── */}
      <div style={{
        position: 'absolute',
        top: '50%', left: '50%',
        width: '88%',
        height: hasCaption ? '76%' : '86%',
        transform: `translate(-50%, ${hasCaption ? '-54%' : '-50%'}) scale(${entrance})`,
        transformOrigin: 'center center',
        overflow: 'hidden',
        borderRadius: 10,
        boxShadow: [
          '0 28px 90px rgba(0,0,0,0.88)',
          '0 0 0 1px rgba(255,255,255,0.10)',
        ].join(', '),
      }}>

        {/* 크롭+줌 이미지 — scale+translate 방식 (clip-path 아님) */}
        <div style={{
          position: 'absolute', inset: 0,
          transform: `scale(${cropScale}) translate(${tx}%, ${ty}%)`,
          transformOrigin: 'center center',
        }}>
          <Img
            src={staticFile(imageSrc)}
            style={{ width: '100%', height: '100%', objectFit: 'fill', display: 'block' }}
          />
        </div>

        {/* ── LAYER 3: 형광펜 바들 ── */}
        {highlights.map((h, i) => {
          const delay = h.delay  ?? 45;
          const dur   = h.animDur ?? 18;
          const prog  = interpolate(frame, [delay, delay + dur], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                top:    `${h.top}%`,
                left:   `${h.left}%`,
                width:  `${h.width}%`,
                height: `${h.height}%`,
                // multiply/screen 모두 흰배경에서 수식상 희미해짐.
                // 단순 반투명 오버레이가 모든 배경에서 가장 일관적으로 보임.
                backgroundColor: h.color ?? '#FFE500',
                opacity: 0.52,
                transformOrigin: 'left center',
                transform: `scaleX(${prog})`,
                pointerEvents: 'none',
                borderRadius: 3,
                zIndex: 20,
              }}
            />
          );
        })}
      </div>

      {/* ── 출처 태그 (우측 하단) ── */}
      {tag && (
        <div style={{
          position: 'absolute',
          right: 56,
          bottom: hasCaption ? 102 : 52,
          opacity: tagOp,
          transform: `translateX(${tagX}px)`,
          background: 'rgba(0,0,0,0.78)',
          border: '1px solid rgba(255,255,255,0.14)',
          borderRadius: 6,
          padding: '8px 18px',
        }}>
          <div style={{ color: C.textPrimary, fontSize: 20, fontWeight: 700, letterSpacing: 1.5 }}>
            {tag.text}
          </div>
          {tag.sub && (
            <div style={{ color: C.textSub, fontSize: 15, fontWeight: 400, marginTop: 2 }}>
              {tag.sub}
            </div>
          )}
        </div>
      )}

      {/* ── 하단 자막 바 ── */}
      {hasCaption && (
        <div style={{
          position: 'absolute',
          bottom: 0, left: 0, right: 0,
          height: '14%',
          display: 'flex', alignItems: 'center',
          paddingInline: 80,
          backgroundColor: 'rgba(0,0,0,0.84)',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          opacity: captionOp,
        }}>
          <div style={{ color: C.textPrimary, fontSize: 38, fontWeight: 700, lineHeight: 1.4 }}>
            {caption}
          </div>
        </div>
      )}

    </AbsoluteFill>
  );
};

// ── ② DocPanScene ─────────────────────────────────────────────
// 하나의 문서에서 여러 구역을 순차 팬+줌. crop 좌표가 interpolate로 부드럽게 이동.

export interface PanSegment {
  startFrame: number;   // 이 세그먼트가 시작되는 씬 프레임
  endFrame:   number;
  crop:       CropRegion;
  highlights?: HighlightBar[];
  caption?:   string;
}

export interface DocPanProps {
  imageSrc: string;
  segments: PanSegment[];
  tag?: LocationTag;
}

const TRANSITION_FRAMES = 20; // 세그먼트 전환 보간 길이

export const DocPanScene: React.FC<DocPanProps> = ({ imageSrc, segments, tag }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn  = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const entrance = spring({
    frame, fps, from: 0, to: 1,
    config: { damping: 14, stiffness: 120, mass: 1 },
  });
  const bgScale = interpolate(frame, [0, 180], [1.0, 1.06], { extrapolateRight: 'clamp' });

  // 현재 활성 세그먼트 인덱스 (findLastIndex 대신 루프)
  let activeIdx = 0;
  for (let i = 0; i < segments.length; i++) {
    if (frame >= segments[i].startFrame) activeIdx = i;
  }
  const seg     = segments[activeIdx];
  const nextSeg = segments[activeIdx + 1] ?? null;

  // 다음 세그먼트로 전환 시 crop 좌표를 interpolate로 부드럽게 이동
  let currentCrop: CropRegion = seg.crop;
  if (nextSeg) {
    const transStart = nextSeg.startFrame - TRANSITION_FRAMES;
    const t = interpolate(frame, [transStart, nextSeg.startFrame], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.inOut(Easing.cubic),
    });
    currentCrop = {
      top:    seg.crop.top    + (nextSeg.crop.top    - seg.crop.top)    * t,
      right:  seg.crop.right  + (nextSeg.crop.right  - seg.crop.right)  * t,
      bottom: seg.crop.bottom + (nextSeg.crop.bottom - seg.crop.bottom) * t,
      left:   seg.crop.left   + (nextSeg.crop.left   - seg.crop.left)   * t,
    };
  }

  const { scale: cropScale, tx, ty } = calcCropZoom(currentCrop);

  const hasCaption = Boolean(seg.caption);
  const captionOp  = interpolate(frame, [30, 50], [0, 1], { extrapolateRight: 'clamp' });
  const tagOp      = interpolate(frame, [20, 40], [0, 1], { extrapolateRight: 'clamp' });
  const tagX       = interpolate(frame, [20, 40], [20, 0], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>

      {/* 블러 배경 */}
      <div style={{
        position: 'absolute', inset: -30,
        transform: `scale(${bgScale})`,
        transformOrigin: 'center center',
      }}>
        <Img
          src={staticFile(imageSrc)}
          style={{
            width: '100%', height: '100%', objectFit: 'cover',
            filter: 'blur(18px) brightness(0.25) saturate(0.6)',
          }}
        />
      </div>

      {/* 팝업 컨테이너 */}
      <div style={{
        position: 'absolute',
        top: '50%', left: '50%',
        width: '88%',
        height: hasCaption ? '76%' : '86%',
        transform: `translate(-50%, ${hasCaption ? '-54%' : '-50%'}) scale(${entrance})`,
        transformOrigin: 'center center',
        overflow: 'hidden',
        borderRadius: 10,
        boxShadow: [
          '0 28px 90px rgba(0,0,0,0.88)',
          '0 0 0 1px rgba(255,255,255,0.10)',
        ].join(', '),
      }}>

        {/* 줌 이미지 — crop 좌표가 interpolate되므로 자동으로 부드럽게 팬 */}
        <div style={{
          position: 'absolute', inset: 0,
          transform: `scale(${cropScale}) translate(${tx}%, ${ty}%)`,
          transformOrigin: 'center center',
        }}>
          <Img
            src={staticFile(imageSrc)}
            style={{ width: '100%', height: '100%', objectFit: 'fill', display: 'block' }}
          />
        </div>

        {/* 현재 세그먼트 형광펜 */}
        {seg.highlights?.map((h, i) => {
          const delay = h.delay   ?? 45;
          const dur   = h.animDur ?? 18;
          const prog  = interpolate(frame, [delay, delay + dur], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          return (
            <div key={i} style={{
              position: 'absolute',
              top:    `${h.top}%`,
              left:   `${h.left}%`,
              width:  `${h.width}%`,
              height: `${h.height}%`,
              backgroundColor: h.color ?? '#FFE500',
              opacity: 0.40,
              transformOrigin: 'left center',
              transform: `scaleX(${prog})`,
              mixBlendMode: 'screen',
              pointerEvents: 'none',
              borderRadius: 2,
            }} />
          );
        })}
      </div>

      {/* 출처 태그 */}
      {tag && (
        <div style={{
          position: 'absolute',
          right: 56,
          bottom: hasCaption ? 102 : 52,
          opacity: tagOp,
          transform: `translateX(${tagX}px)`,
          background: 'rgba(0,0,0,0.78)',
          border: '1px solid rgba(255,255,255,0.14)',
          borderRadius: 6,
          padding: '8px 18px',
        }}>
          <div style={{ color: C.textPrimary, fontSize: 20, fontWeight: 700, letterSpacing: 1.5 }}>
            {tag.text}
          </div>
          {tag.sub && (
            <div style={{ color: C.textSub, fontSize: 15, fontWeight: 400, marginTop: 2 }}>
              {tag.sub}
            </div>
          )}
        </div>
      )}

      {/* 하단 자막 */}
      {hasCaption && (
        <div style={{
          position: 'absolute',
          bottom: 0, left: 0, right: 0,
          height: '14%',
          display: 'flex', alignItems: 'center',
          paddingInline: 80,
          backgroundColor: 'rgba(0,0,0,0.84)',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          opacity: captionOp,
        }}>
          <div style={{ color: C.textPrimary, fontSize: 38, fontWeight: 700, lineHeight: 1.4 }}>
            {seg.caption}
          </div>
        </div>
      )}

    </AbsoluteFill>
  );
};
