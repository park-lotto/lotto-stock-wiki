import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

// ─── SpaceX 장면 내용 (이미지 없이 CSS로 재현) ───────────────────
const SpaceXContent: React.FC = () => (
  <>
    {/* Part.3 레이블 */}
    <div style={{
      position: 'absolute', top: 30, left: 42,
      color: '#fff', fontSize: 21, fontWeight: 500,
      fontFamily: 'Pretendard, sans-serif', letterSpacing: 0.2,
    }}>
      Part.3 | 혁신 기업을 찾는 기준
    </div>

    {/* SpaceX 로고 */}
    <div style={{
      position: 'absolute', top: 88, left: 0, right: 0,
      textAlign: 'center', color: '#fff',
      fontSize: 92, fontWeight: 900,
      fontFamily: 'Arial Black, Arial, sans-serif',
      letterSpacing: 14,
    }}>
      SPACE<span style={{ fontStyle: 'italic' }}>X</span>
    </div>

    {/* 흰색 문서 카드 */}
    <div style={{
      position: 'absolute', top: 216, left: 148, right: 148,
      backgroundColor: '#fff', borderRadius: 6,
      padding: '26px 38px 30px',
    }}>
      <div style={{ fontWeight: 700, fontSize: 21, color: '#111', marginBottom: 10, fontFamily: 'Arial, sans-serif' }}>
        Overview
      </div>
      <div style={{ fontSize: 17.5, lineHeight: 1.62, color: '#222', fontFamily: 'Arial, sans-serif' }}>
        <span style={{ backgroundColor: '#FFE066' }}>
          Founded in 2002, SpaceX is the only company building the integrated hardware and software infrastructure of the
          future across space, connectivity, and AI.
        </span>
        {' '}At our core, we are builders. We design, manufacture, launch, and operate
        products and services built on cutting-edge technologies, including the world's most advanced rockets and
        spacecraft. We safely and reliably transport astronauts, satellites, and other payloads on missions that benefit life on
        Earth. Since 2023, we have launched more than 80% of mass to orbit for the world each year with an over 99%
        mission success rate with Falcon rockets. We also operate a high-speed, low-latency global broadband data and
        communications network powered by approximately 9,600 Starlink broadband and mobile satellites in Low-Earth
        Orbit, delivering connectivity to millions of consumer, enterprise, and government customers across 164 countries,
        territories, and other markets, as of March 31, 2026.
      </div>
    </div>

    {/* 출처 */}
    <div style={{
      position: 'absolute', top: 624, right: 158,
      color: 'rgba(255,255,255,0.45)', fontSize: 15,
      fontFamily: 'Arial, sans-serif',
    }}>
      출처 : Space Exploration Technologies - S-1
    </div>

    {/* 아래 화살표 */}
    <div style={{
      position: 'absolute', top: 626, left: '50%',
      transform: 'translateX(-50%)',
      color: '#fff', fontSize: 34,
    }}>▼</div>

    {/* 한국어 번역 텍스트 (FocusZoom 타겟) */}
    <div style={{
      position: 'absolute', top: 670, left: 0, right: 0,
      textAlign: 'center',
      fontFamily: 'Pretendard, Noto Sans KR, sans-serif',
      lineHeight: 1.7,
    }}>
      <div style={{ fontSize: 36, color: '#fff', fontWeight: 500 }}>
        2002년에 설립된 SpaceX는{' '}
        <span style={{ color: '#FFD700', fontWeight: 700 }}>우주, 연결성 및 인공지능</span>
        {' '}분야에 걸쳐
      </div>
      <div style={{ fontSize: 36, color: '#fff', fontWeight: 500 }}>
        미래의 통합 하드웨어 및 소프트웨어{' '}
        <span style={{ color: '#FFD700', fontWeight: 700, borderBottom: '2.5px solid #FFD700' }}>
          인프라를 구축하는 유일한 기업
        </span>
        입니다.
      </div>
    </div>

    {/* 여기서 얘기하는 건 */}
    <div style={{
      position: 'absolute', top: 812, left: 0, right: 0,
      textAlign: 'center', color: '#fff',
      fontSize: 54, fontWeight: 700,
      fontFamily: 'Pretendard, sans-serif',
    }}>
      여기서 얘기하는 건
    </div>
  </>
);

// ─── 포커스 박스 설정 ─────────────────────────────────────────────
const FOCUS_BOX = { top: 663, left: 175, width: 1570, height: 132 };
const PAD = 12;

// 박스 중심 → 캔버스 중심(540)으로 이동하는 거리
const BOX_CENTER_Y = FOCUS_BOX.top + FOCUS_BOX.height / 2; // 729
const TRANSLATE_Y  = 540 - BOX_CENTER_Y;                   // -189px

export const FocusZoomDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ① 배경 블러 + 어둡게 (0~22f)
  const blurPx = interpolate(frame, [0, 22], [0, 9], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const bgBrightness = interpolate(frame, [0, 22], [1, 0.42], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // ② 포커스 카드: 중앙으로 이동 + 살짝 확대 (spring)
  const cardSpring = spring({
    frame: frame - 8, fps,
    config: { damping: 18, stiffness: 160, mass: 0.9 },
  });
  const cardTranslateY = cardSpring * TRANSLATE_Y;   // 0 → -189px
  const cardScale      = 1 + cardSpring * 0.22;       // 1.0 → 1.22x

  // ③ 박스 테두리 페이드
  const borderOpacity = interpolate(frame, [8, 26], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const bx = FOCUS_BOX.left - PAD;
  const by = FOCUS_BOX.top  - PAD;
  const bw = FOCUS_BOX.width  + PAD * 2;
  const bh = FOCUS_BOX.height + PAD * 2;

  const cardTransform = `translate(0px, ${cardTranslateY}px) scale(${cardScale})`;

  return (
    <AbsoluteFill style={{ backgroundColor: '#080808', overflow: 'hidden' }}>

      {/* 레이어 1: 블러 처리된 배경 */}
      <AbsoluteFill style={{
        filter: `blur(${blurPx}px) brightness(${bgBrightness})`,
      }}>
        <SpaceXContent />
      </AbsoluteFill>

      {/* 레이어 2: 포커스 카드 — 원본 선명, 중앙으로 이동, 살짝 확대 */}
      <div style={{
        position: 'absolute',
        top: by, left: bx, width: bw, height: bh,
        overflow: 'hidden',
        borderRadius: 12,
        transform: cardTransform,
        transformOrigin: 'center center',
      }}>
        <div style={{
          position: 'absolute',
          top: -by, left: -bx,
          width: 1920, height: 1080,
        }}>
          <SpaceXContent />
        </div>
      </div>

      {/* 레이어 3: 박스 테두리 (카드와 동일 transform) */}
      <div style={{
        position: 'absolute',
        top: by, left: bx, width: bw, height: bh,
        border: '2px solid rgba(255,255,255,0.88)',
        borderRadius: 12,
        boxShadow: '0 8px 40px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.1)',
        transform: cardTransform,
        transformOrigin: 'center center',
        opacity: borderOpacity,
        pointerEvents: 'none',
      }} />

    </AbsoluteFill>
  );
};

export const FOCUS_ZOOM_DEMO_FRAMES = 150;
