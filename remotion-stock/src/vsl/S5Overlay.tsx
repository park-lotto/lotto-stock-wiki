/**
 * S5 오버레이 공용 — 사장님이 편집한 영상 위에 **자막 · 애니메이션 · 효과음만** 얹는다.
 *
 * 원칙(2026-08-11 지시):
 *  · 배경은 절대 건드리지 않는다. 확대·이동은 이미 편집본에서 돌고 있다.
 *    여기에 또 줌을 걸면 둘이 싸워서 멀미가 난다. 변형 0, 소리도 편집본 것을 쓴다.
 *  · "심심하지 않게" — 대신 **위에서** 움직인다: 낱말 팝인, 라벨 카드, 전환 훑는 선,
 *    포인트 핀(숫자·기능을 짚는 민트 링), 효과음.
 *
 * 싱크는 whisper 실측 시각(04_자막_타임스탬프/*_words.json) 그대로 쓴다.
 */

import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, OffthreadVideo,
} from 'remotion';
import { KineticWord, BG } from './motion';

export const S5_FPS_O = 30;

export type OCut = {
  /** 오디오 기준 시작(초) — whisper 실측 */
  t: number;
  text: string;
  sfx?: { n: string; at: number; v?: number }[];
};

/* ★사장님 지시(2026-08-11): "그라데이션 금지 / 이거(훑는 선) 하지 말고 자막이랑 효과음만."
   그래서 오버레이에서 전부 걷어냈다 — 훑는 민트 선·섬광·라벨 카드·포인트 핀·진행바.
   자막 바닥의 그라데이션 스크림도 뺐다. 가독성은 **글자 그림자**로만 지킨다
   (그림자는 그라데이션이 아니다). 화면 위에 남는 건 자막과 소리뿐이다. */
const Overlay: React.FC<{ cut: OCut }> = ({ cut }) => (
  <AbsoluteFill>
    <KineticWord text={cut.text} size={58} perWord={1.3} />
    {(cut.sfx ?? []).map((s, i) => (
      <Sequence key={i} from={Math.round(s.at * S5_FPS_O)} layout="none">
        <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.28} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

/** 편집본 + 오버레이 씬을 찍어내는 공장 */
export const makeOverlayScene = (src: string, cuts: OCut[], endSec: number): React.FC => () => {
  return (
    <AbsoluteFill style={{ background: BG }}>
      {/* 베이스 — 사장님 편집본 그대로. 변형 없음, 소리도 이쪽 것 */}
      <OffthreadVideo
        src={staticFile(src)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />
      {cuts.map((cut, i) => {
        const from = Math.round(cut.t * S5_FPS_O);
        const next = cuts[i + 1]?.t ?? endSec;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, Math.round((next - cut.t) * S5_FPS_O))}>
            <Overlay cut={cut} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

/* ══════════ S5-1 — 레퍼런스 랭킹 둘러보기 (31.09s / whisper 8문장) ══════════
   whisper가 받아쓴 오타는 자막에서 바로잡는다: 알짤→알짜일 / 태긴→태깅 / 정열→정렬 */
export const S5_1_CUTS: OCut[] = [
  { t: 0.00, text: '먼저 |레퍼런스 랭킹|으로 들어갑니다.',
    sfx: [{ n: 'whoosh.mp3', at: 0, v: 0.3 }] },
  { t: 2.58, text: '맨 위는 |5대 플랫폼|을 매일 주기적으로 크롤링해서 수집한 영상들입니다.',
    sfx: [{ n: 'click.mp3', at: 0.3, v: 0.26 }, { n: 'ding2.mp3', at: 1.6, v: 0.2 }] },
  { t: 7.40, text: '|속도, 가속, 참여 밀도.| 어떤 영상이 얼마나 빠르게 터지고 있는지 |숫자로 다 보여줍니다.|',
    sfx: [{ n: 'subpoint.mp3', at: 0.4, v: 0.24 }] },
  { t: 13.52, text: '특히 |참여 밀도|를 켜면, 작은 채널에서 |실속 있게 터지는| 영상이 걸러집니다.',
    sfx: [{ n: 'punch.mp3', at: 0.3, v: 0.3 }] },
  { t: 18.14, text: '사실 이쪽이 |알짜일 때가| 훨씬 많거든요.',
    sfx: [{ n: 'ding.wav', at: 0.2, v: 0.26 }] },
  { t: 20.72, text: '진짜 봐야 할 영상, 반응 좋음, 급상승. 이렇게 |자동으로 태깅|까지 해뒀습니다.',
    sfx: [{ n: 'pop.wav', at: 0.3, v: 0.24 }, { n: 'pop.wav', at: 0.9, v: 0.22 }, { n: 'pop.wav', at: 1.5, v: 0.2 }] },
  { t: 26.28, text: '정렬도, 카테고리도, 검색도 |다 됩니다.|',
    sfx: [{ n: 'click.mp3', at: 0.2, v: 0.28 }] },
  { t: 28.44, text: '내 채널에 맞는 걸 |바로 찾으시면 됩니다.|',
    sfx: [{ n: 'ding.wav', at: 0.3, v: 0.3 }] },
];

export const S5_1_END = 31.09;
export const S5_1_FRAMES = Math.round(S5_1_END * S5_FPS_O);
export const S5_1Edit = makeOverlayScene('vsl/s5/edit_s5_1.mp4', S5_1_CUTS, S5_1_END);

/* ══════════ S5-2 — 소재 고르기 + 숏템파워 검색 (수정 편집본 63.46s) ══════════
   자막·라벨은 S5_2_CUTS(whisper 실측)를 그대로 재사용한다. 편집본이 바뀌어도
   내레이션은 같은 mp3라 시각이 안 변한다(63.46s ≒ 63.44s). */
export const S5_2_END_EDIT = 63.46;
export const S5_2_EDIT_FRAMES = Math.round(S5_2_END_EDIT * S5_FPS_O);
