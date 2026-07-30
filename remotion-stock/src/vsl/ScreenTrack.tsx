/**
 * ScreenTrack — VSL 배경 레이어(제품 화면 녹화) 재생기. T1의 본체.
 *
 * 설계(2026-07-30, 사장님 방향): "배경엔 프로그램이 계속 돌아가고, 그 위에 그래픽이
 * 나레이션에 붙는다." 그래서 배경은 **자르지 않고 흐르게** 두고, 길이는 **구간별 배속**으로
 * 맞춘다(경쟁사 VSL 실측: 데모 구간 컷이 분당 1~2개뿐 — 컷을 안 쓰는 게 정답이었다).
 *
 * ★왜 Sequence를 구간마다 쪼개나 (OffthreadVideo 하나로는 안 된다)
 *   OffthreadVideo의 playbackRate는 그 인스턴스 전체에 걸리는 상수다. 한 클립 안에서
 *   "여긴 8배, 여긴 1배"처럼 배속을 바꾸려면 구간마다 별도 인스턴스를 놓고 각자
 *   trimBefore/trimAfter로 원본 구간을 지정하는 수밖에 없다. 렌더가 결정적(deterministic)이고
 *   seek에도 안전하다.
 *
 * 배속 원칙(촬영시트와 같은 규칙 — 균등 배속은 금지):
 *   · 대기(렌더·자막제거 처리): speed 크게 주거나 아예 구간에서 제외(=컷)
 *   · 조작(클릭·선택): 1~1.5배. 시니어 타깃이라 여기서 아끼면 안 된다
 *   · 결과물 노출: speed 1 고정. 정점이라 배속하면 감동이 죽는다
 */

import React from 'react';
import { AbsoluteFill, OffthreadVideo, Sequence, staticFile } from 'remotion';

/** 원본 녹화의 한 구간. from/to는 **원본 파일의 초**, speed는 재생 배속(2=2배 빠르게). */
export type ScreenSegment = {
  from: number;
  to: number;
  /** 기본 1. 대기 구간엔 4~8, 결과 노출엔 반드시 1. */
  speed?: number;
  /** 편집 메모용(렌더에 영향 없음) — 나중에 왜 이 배속인지 알아보게. */
  note?: string;
};

export type ScreenTrackProps = {
  /** public/ 기준 상대경로. 예: 'vsl/test_screen.mp4' */
  src: string;
  segments: ScreenSegment[];
  fps: number;
  /** 화면을 어둡게(훅 구간에서 중앙 자막을 얹을 때). 0=그대로, 0.55=꽤 어둡게 */
  dim?: number;
  style?: React.CSSProperties;
};

/** 구간을 컴포지션 프레임으로 환산. 배속이 걸린 구간은 그만큼 짧아진다. */
export const planSegments = (segments: ScreenSegment[], fps: number) => {
  let cursor = 0;
  return segments.map((s) => {
    const speed = s.speed && s.speed > 0 ? s.speed : 1;
    const srcDur = Math.max(0, s.to - s.from);
    // 최소 1프레임 — 0프레임 Sequence는 Remotion이 렌더하지 않는다.
    const durationInFrames = Math.max(1, Math.round((srcDur / speed) * fps));
    const plan = { ...s, speed, durationInFrames, startAtFrame: cursor };
    cursor += durationInFrames;
    return plan;
  });
};

/** 이 트랙이 차지하는 총 프레임 수 = 컴포지션 durationInFrames 계산에 쓴다. */
export const screenTrackFrames = (segments: ScreenSegment[], fps: number) =>
  planSegments(segments, fps).reduce((n, s) => n + s.durationInFrames, 0);

export const ScreenTrack: React.FC<ScreenTrackProps> = ({
  src,
  segments,
  fps,
  dim = 0,
  style,
}) => {
  const plan = planSegments(segments, fps);
  return (
    <AbsoluteFill style={{ background: '#000', ...style }}>
      {plan.map((s, i) => (
        <Sequence
          key={`${i}-${s.from}-${s.to}`}
          from={s.startAtFrame}
          durationInFrames={s.durationInFrames}
          // 구간 경계에서 앞 구간이 남아 겹쳐 보이지 않게 한다.
          layout="none"
        >
          <OffthreadVideo
            src={staticFile(src)}
            // trimBefore/trimAfter는 **컴포지션 fps 기준 프레임**이다(초 × fps).
            trimBefore={Math.round(s.from * fps)}
            trimAfter={Math.round(s.to * fps)}
            playbackRate={s.speed}
            // 나레이션이 오디오 기준이므로 화면 소리는 죽인다. 성우 미리듣기처럼
            // 소리를 들려줄 구간만 이 컴포넌트 밖에서 따로 얹는다.
            volume={0}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        </Sequence>
      ))}
      {dim > 0 ? (
        <AbsoluteFill style={{ background: `rgba(0,0,0,${dim})` }} />
      ) : null}
    </AbsoluteFill>
  );
};
