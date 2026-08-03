/**
 * VslDemo — 숏템메이커 VSL 씬 골격(T1). 4층 구조의 뼈대만 세운 것.
 *
 *   4층 자막            ← T2에서 words.json으로 자동 싱크
 *   3층 그래픽 오버레이  ← T4에서 CountCard/Versus/ScriptMatch 얹음
 *   2층 배경 화면녹화    ← ScreenTrack (지금 이 태스크)
 *   1층 나레이션 오디오  ← T2
 *
 * T1의 성공 기준: 화면녹화 하나가 **구간별 배속으로** 재생된다. 그것만 확인한다.
 * (자막·카운터는 자리만 잡아둔다 — 지금 채우면 T2/T4와 중복 작업이 된다)
 *
 * ★검증용 테스트 클립은 git에 넣지 않는다(.gitignore: remotion-stock/public/**\/*.mp4).
 *   다른 PC에서 다시 만들려면 remotion-stock/ 에서 이 한 줄:
 *     ffmpeg -y -f lavfi -i "testsrc=size=1280x720:rate=30:duration=60" \
 *       -c:v libx264 -preset veryfast -pix_fmt yuv420p public/vsl/test_screen.mp4
 *   testsrc는 화면에 **프레임 번호가 찍혀 있어** 배속이 실제로 걸렸는지 눈으로 보인다.
 *   2026-07-30 실측: 컴포지션 2.2s→카운터 11, 3.8s→24(8배 구간), 4.2s→40(1배 복귀).
 */

import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { ScreenTrack, ScreenSegment, screenTrackFrames } from './ScreenTrack';

export const VSL_FPS = 30;

/**
 * T1 검증용 구간표. 테스트 클립(testsrc)은 화면에 프레임 번호가 찍혀 있어서
 * **배속이 실제로 걸렸는지 눈으로 확인**할 수 있다 — 숫자가 뛰는 속도가 달라진다.
 * 실촬영 후에는 이 배열을 anchors.json에서 자동 생성한다(T3).
 */
export const DEMO_SEGMENTS: ScreenSegment[] = [
  { from: 0, to: 2, speed: 1, note: '조작 — 1배(시니어 타깃, 여기서 아끼면 안 됨)' },
  { from: 10, to: 26, speed: 8, note: '대기 — 8배로 압축(원본 16초 → 2초)' },
  { from: 40, to: 43, speed: 1, note: '결과 노출 — 1배 고정(정점이라 배속 금지)' },
];

export const VSL_DEMO_FRAMES = screenTrackFrames(DEMO_SEGMENTS, VSL_FPS);

type Props = {
  src?: string;
  segments?: ScreenSegment[];
  /** 훅 구간처럼 화면을 깔고 중앙 자막을 얹을 때만 쓴다. */
  dim?: number;
  /** 중앙 대형 자막(훅). T4에서 ImpactText로 교체 예정 — 지금은 자리표시. */
  centerTitle?: string;
};

export const VslDemo: React.FC<Props> = ({
  src = 'vsl/test_screen.mp4',
  segments = DEMO_SEGMENTS,
  dim = 0,
  centerTitle,
}) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      {/* 2층 — 배경 화면녹화 */}
      <ScreenTrack src={src} segments={segments} fps={fps} dim={dim} />

      {/* 3층 자리표시 — 클릭 카운터(T4에서 motion/CountCard 이식) */}
      <div
        style={{
          position: 'absolute', top: 28, right: 34,
          padding: '10px 18px', borderRadius: 10,
          background: 'rgba(12,20,17,0.72)', color: '#EDEDED',
          fontFamily: "'Space Mono','Roboto Mono',monospace",
          fontSize: 26, letterSpacing: '0.06em',
        }}
      >
        클릭 —
      </div>

      {/* 훅 구간 중앙 자막(옵션) */}
      {centerTitle ? (
        <AbsoluteFill
          style={{ alignItems: 'center', justifyContent: 'center' }}
        >
          <div
            style={{
              fontFamily: "'Pretendard','Archivo',sans-serif",
              fontSize: 86, fontWeight: 800, color: '#fff',
              textShadow: '0 6px 28px rgba(0,0,0,0.6)', textAlign: 'center',
            }}
          >
            {centerTitle}
          </div>
        </AbsoluteFill>
      ) : null}

      {/* 4층 자리표시 — 자막바(T2에서 words.json 싱크로 교체) */}
      <div
        style={{
          position: 'absolute', left: 0, right: 0, bottom: 54,
          display: 'flex', justifyContent: 'center',
        }}
      >
        <div
          style={{
            maxWidth: 1500, padding: '14px 26px', borderRadius: 12,
            background: 'rgba(0,0,0,0.55)', color: '#fff',
            fontFamily: "'Pretendard',sans-serif", fontSize: 34, fontWeight: 600,
            opacity: 0.35,
          }}
        >
          (자막 자리 — T2)
        </div>
      </div>
    </AbsoluteFill>
  );
};
