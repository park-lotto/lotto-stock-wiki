import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {LilyBasic} from './LilyBasic';
import {LilyLower} from './LilyLower';
import {LilyBubble} from './LilyBubble';
import {LilyDeco} from './LilyDeco';
import {LilyStamp} from './LilyStamp';

// 썰쇼츠 자막 오버레이 — 투명 배경으로 렌더해서 완성 영상 위에 얹는다.
// timing.json 의 컷을 그대로 받아 역할별로 다른 릴리 스타일을 배치한다.
// kind 로 어떤 스타일을 쓸지 정한다(대본 작성자가 컷마다 고른다).
export type SsulCut = {
  t: number;          // 시작(초)
  d: number;          // 길이(초)
  kind: 'narr' | 'hl' | 'lower' | 'bubble' | 'react' | 'stamp' | 'punch';
  text: string;
  highlight?: string; // hl: 형광펜 칠할 낱말
  name?: string;      // lower: 이름표
  color?: string;     // lower/bubble 색
};

export type SsulOverlayProps = {
  cuts: SsulCut[];
  /**
   * 자막층을 아래로 미는 양(px). 릴리 컴포넌트는 position(top/mid/bottom) 만 받아
   * 정확한 y 를 못 주므로, 렌더 실측으로 잡은 값을 쓴다.
   * 실측(2026-09-14, 이 합성판): shiftY=574 로 렌더하니 자막 중앙이 y=1408 이었다
   * (감싼 AbsoluteFill 이 marginTop 기준을 바꿔 밀린 양이 줄어든다).
   * 목표는 사진(469~1254) 아래 검은 띠 중앙 1587 → 574 + (1587-1408) = 753.
   */
  shiftY?: number;
};

export const SsulOverlay: React.FC<SsulOverlayProps> = ({cuts, shiftY = 753}) => {
  const {fps} = useVideoConfig();
  const shift = shiftY;
  return (
    // 배경 투명 — 알파로 렌더해서 원본 영상 위에 합성한다
    <AbsoluteFill style={{backgroundColor: 'transparent'}}>
      {cuts.map((c, i) => {
        const from = Math.round(c.t * fps);
        const dur = Math.max(1, Math.round(c.d * fps));
        let inner: React.ReactNode = null;

        if (c.kind === 'narr') {
          inner = <LilyBasic variant="box" text={c.text} position="bottom" />;
        } else if (c.kind === 'hl') {
          inner = (
            <LilyBasic
              variant="marker"
              text={c.text}
              highlight={c.highlight}
              markerColor="#ffe14d"
              position="bottom"
            />
          );
        } else if (c.kind === 'lower') {
          inner = (
            <LilyLower
              name={c.name ?? ''}
              text={c.text}
              variant="plain"
              color={c.color ?? '#2f6fd0'}
              position="bottom"
            />
          );
        } else if (c.kind === 'bubble') {
          // 댓글은 말풍선 '안'에 들어가야 남의 말로 읽힌다 → label 자리에 넣는다.
          // (본문 text 를 비우면 아래 빈 줄만 생기므로 label 전용으로 쓴다)
          inner = (
            <LilyBubble
              label={c.text}
              text=""
              labelBg={c.color ?? '#ff7ab8'}
              position="bottom"
            />
          );
        } else if (c.kind === 'react') {
          inner = <LilyDeco word={c.text} anim="shake" color={c.color ?? '#ff2d2d'} />;
        } else if (c.kind === 'stamp') {
          inner = <LilyStamp text={c.text} color={c.color ?? '#e02020'} />;
        } else if (c.kind === 'punch') {
          // 마지막 한 방은 글자 전체가 빨강이어야 한다.
          // LilyBasic 은 강조어만 색이 바뀌므로 color(본문색) 로 직접 준다.
          inner = (
            <LilyBasic
              variant="plain"
              text={c.text}
              color="#ff2d2d"
              position="bottom"
            />
          );
        }

        // react·stamp 는 사진 위에 얹는 게 맞다(한 방 효과) → 밀지 않는다.
        const onPhoto = c.kind === 'react' || c.kind === 'stamp';
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            {onPhoto ? inner : (
              <AbsoluteFill style={{transform: `translateY(${shift}px)`}}>
                {inner}
              </AbsoluteFill>
            )}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
