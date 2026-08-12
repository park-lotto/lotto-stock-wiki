/**
 * S5-2 — 소재 고르기 + 숏템파워 검색 (63.40s / whisper 24세그먼트)
 *
 * S1~S10과 성격이 다르다. 여기는 **데모**다. 화면이 주인공이고 말은 해설이다.
 * 그래서 배경을 깔지 않는다 — 녹화본을 풀프레임으로 두고, 자막은 아래에만 둔다.
 *
 * 싱크 방법(추측 없음):
 *  1) whisper로 s5-2.mp3의 문장 시각을 뜬다 → 04_자막_타임스탬프/s5-2_words.json
 *  2) 녹화본(175.4s)에서 그 말이 가리키는 구간을 골라 **배속으로 눌러** 말 길이에 맞춘다
 *     말은 63.4초인데 화면은 175초다. 그대로 붙이면 말이 끝나도 화면이 남는다.
 *  3) 배속은 컷마다 다르다 — 설명이 촘촘한 구간은 느리게, 스크롤만 하는 구간은 빠르게.
 *
 * 녹화본 구조(프레임 확인): 0~50 레퍼런스 랭킹(댓글순) / 55~140 렌즈 유사영상
 *                          143~175 샤오홍슈 원본
 */

import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, OffthreadVideo,
  useCurrentFrame, useVideoConfig, interpolate, spring, Easing,
} from 'remotion';
import { KineticWord, ProgressBar, MINT, BG, FONT } from './motion';

export const S5_FPS = 30;
const SRC = 'vsl/s5/rec2.mp4';

type Cut = {
  /** 오디오 기준 시작(초) — whisper 실측값 그대로 */
  t: number;
  /** 녹화본에서 가져올 시작 지점(초) */
  at: number;
  /** 배속 — 말 길이에 화면을 맞춘다 */
  rate: number;
  /** 자막(|…|은 민트 강조, 덩어리로 안 쪼개진다) */
  text: string;
  /** 화면 왼쪽 아래 라벨 카드 — 말이 짚는 것을 글자로 한 번 더 박는다 */
  chip?: string;
  sfx?: { n: string; at: number; v?: number }[];
};

/* whisper 24세그먼트를 화면 흐름에 맞춰 12컷으로 묶었다.
   (문장마다 컷을 갈면 화면이 정신없다 — 화면이 바뀌는 지점에서만 자른다) */
export const S5_2_CUTS: Cut[] = [
  { t: 0.00, at: 1.5, rate: 1.35, text: '실제로 |얼마나 간단한지| 보시죠.',
    sfx: [{ n: 'whoosh.mp3', at: 0, v: 0.28 }] },
  { t: 2.22, at: 6.0, rate: 1.30, text: '|댓글 순으로 정렬|한 뒤, 레시피 영상으로 만들어 보겠습니다.',
    chip: '레퍼런스 랭킹 · 댓글순',
    sfx: [{ n: 'click.mp3', at: 0.2, v: 0.26 }] },
  { t: 5.94, at: 12.0, rate: 1.25, text: '지금 보시는 건 |48시간 이내|, 인스타에서 댓글이 많은 순입니다.',
    chip: '48시간 이내' },
  { t: 10.04, at: 17.5, rate: 1.20, text: '이건 댓글이 |4천 개|가 넘고, 이건 |3천 개|가 넘습니다.',
    sfx: [{ n: 'ding2.mp3', at: 0.6, v: 0.24 }, { n: 'ding2.mp3', at: 2.0, v: 0.24 }] },
  { t: 13.48, at: 22.0, rate: 1.25, text: '이틀 만에 말이죠. |속도를 눌러보겠습니다.|',
    chip: '이틀 만에',
    sfx: [{ n: 'click.mp3', at: 1.4, v: 0.28 }] },
  { t: 16.04, at: 26.5, rate: 1.20, text: '|시간당 댓글이 192개|씩 올라간다는 뜻입니다.',
    chip: '시간당 192개',
    sfx: [{ n: 'punch.mp3', at: 0.3, v: 0.3 }] },
  { t: 19.36, at: 31.0, rate: 1.15, text: '재미있는 건, 이 두 영상이 |같은 원본을 썼다|는 겁니다.',
    chip: '같은 원본',
    sfx: [{ n: 'boom.mp3', at: 0, v: 0.26 }] },
  { t: 22.70, at: 35.0, rate: 1.20, text: '하나는 19시간 전에 2천 개, 다른 하나는 34시간 전에 2천5백 개.' },
  { t: 27.50, at: 41.0, rate: 1.15, text: '열어보시면 |똑같은 장면|이 나옵니다. 감이 좀 잡히시나요?',
    sfx: [{ n: 'ding.wav', at: 1.6, v: 0.26 }] },
  { t: 31.28, at: 45.5, rate: 1.10, text: '해외 영상을 짜깁기 위해서 |장면 순서를 바꾸고|, 음성과 대본만 새로 얹은 겁니다.',
    chip: '순서 교체 + 새 대본' },
  { t: 36.22, at: 51.0, rate: 1.10, text: '잘 되는 영상들, |그게 전부입니다.|' },
  { t: 38.62, at: 55.0, rate: 1.20, text: '지금 터진 걸 |누가 더 빨리 벤치마킹하느냐|, 그 싸움이라는 거죠.',
    sfx: [{ n: 'subpoint.mp3', at: 0.4, v: 0.24 }] },
  { t: 42.60, at: 62.0, rate: 1.45, text: '이제 썸네일 아래, |숏템파워 검색|을 눌러보겠습니다.',
    chip: '숏템파워 검색',
    sfx: [{ n: 'click.mp3', at: 0.5, v: 0.3 }, { n: 'whoosh.mp3', at: 1.2, v: 0.24 }] },
  { t: 45.94, at: 100.0, rate: 1.30, text: '나오는 화면들이 |하나같이 다 똑같지| 않습니까?',
    chip: '유사 영상',
    sfx: [{ n: 'ding2.mp3', at: 0.8, v: 0.22 }] },
  { t: 48.90, at: 112.0, rate: 1.20, text: '|썸네일까지 똑같네요.|',
    sfx: [{ n: 'punch.mp3', at: 0.2, v: 0.3 }] },
  { t: 50.06, at: 143.5, rate: 1.30, text: '|샤오홍슈|에서도 한번 보겠습니다.',
    chip: '샤오홍슈',
    sfx: [{ n: 'whoosh.mp3', at: 0, v: 0.28 }] },
  { t: 52.34, at: 148.0, rate: 1.25, text: '역시 |원본 영상|이 있습니다.' },
  { t: 54.04, at: 152.0, rate: 1.25, text: '|담기 버튼만| 누르면 그대로 가져옵니다. 이게 답니다.',
    chip: '담기 한 번',
    sfx: [{ n: 'click.mp3', at: 0.6, v: 0.32 }, { n: 'ding.wav', at: 1.6, v: 0.28 }] },
  { t: 57.34, at: 160.0, rate: 1.20, text: '이제 승부는 |딱 하나에서| 갈립니다.',
    sfx: [{ n: 'boom.mp3', at: 0, v: 0.3 }] },
  { t: 59.30, at: 166.0, rate: 1.10, text: '대본과 스토리를, 장면에 |얼마나 퀄리티 있게 내 것으로| 만드느냐.',
    sfx: [{ n: 'subpoint.mp3', at: 0.5, v: 0.26 }] },
];

/** 오디오 실측 길이 — 마지막 컷은 여기까지 끌고 간다 */
export const S5_2_END = 63.40;

/** 화면 — 풀프레임. 우리 화면이라 탈색하지 않는다(어둡게 깔 이유가 없다) */
const Shot: React.FC<{ at: number; rate: number }> = ({ at, rate }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const z = interpolate(frame, [0, durationInFrames], [1.0, 1.035]);
  return (
    <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
      <OffthreadVideo
        src={staticFile(SRC)}
        trimBefore={Math.round(at * fps)}
        playbackRate={rate}
        volume={0}
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${z})` }}
      />
    </AbsoluteFill>
  );
};

/** 라벨 카드 — 말이 짚는 것을 글자로 한 번 더 박는다 */
const Chip: React.FC<{ label: string }> = ({ label }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - 4, fps, config: { damping: 14, stiffness: 190 } });
  return (
    <div style={{
      position: 'absolute', left: 56, top: 48,
      transform: `translateX(${interpolate(p, [0, 1], [-40, 0])}px)`, opacity: p,
      padding: '14px 24px', borderRadius: 14,
      background: 'rgba(5,19,14,0.86)', border: `2px solid ${MINT}88`,
      boxShadow: `0 0 34px ${MINT}44`,
      fontFamily: FONT, fontWeight: 900, fontSize: 34, color: MINT,
    }}>{label}</div>
  );
};

const CutView: React.FC<{ cut: Cut }> = ({ cut }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // 컷이 바뀔 때 아주 옅은 흰 섬광 — 붙인 자리를 '전환'으로 읽히게 한다
  const flash = interpolate(frame, [0, 4], [0.16, 0], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Shot at={cut.at} rate={cut.rate} />
      {cut.chip ? <Chip label={cut.chip} /> : null}
      {/* 자막 바닥 — 화면이 밝아서 이게 없으면 흰 글자가 사라진다 */}
      <AbsoluteFill style={{
        background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.45) 14%, rgba(0,0,0,0) 30%)',
        pointerEvents: 'none',
      }} />
      <KineticWord text={cut.text} size={58} perWord={1.4} hi="plate" mode="calm" />
      <AbsoluteFill style={{ background: '#fff', opacity: flash, pointerEvents: 'none' }} />
      <ProgressBar p={frame / durationInFrames} />
      {(cut.sfx ?? []).map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * S5_FPS)} layout="none">
          <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.28} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const S5_2Demo: React.FC = () => (
  <AbsoluteFill style={{ background: BG }}>
    <Audio src={staticFile('vsl/s5-2.mp3')} />
    {S5_2_CUTS.map((cut, i) => {
      const from = Math.round(cut.t * S5_FPS);
      const next = S5_2_CUTS[i + 1]?.t ?? S5_2_END;
      return (
        <Sequence key={i} from={from} durationInFrames={Math.max(1, Math.round((next - cut.t) * S5_FPS))}>
          <CutView cut={cut} />
        </Sequence>
      );
    })}
  </AbsoluteFill>
);

export const S5_2_FRAMES = Math.round(S5_2_END * S5_FPS);
