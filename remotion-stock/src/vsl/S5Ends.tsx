/**
 * S5-0 데모 진입 / S5-12 마무리 — 화면 촬영본이 없는 두 씬. (2026-08-12)
 *
 * S5의 나머지는 사장님 편집본 위에 자막만 얹지만, 이 둘은 **말만 있고 화면이 없다.**
 * 그래서 S6~S10과 같은 방식으로 화면을 만든다(배경 + 가운데 자막).
 *
 * 싱크: whisper 실측 — s5-0 25.31s(9문장) / s5-12 30.59s(9문장)
 *   ★s5-0의 TTS 파일명은 `s5.mp3`다(s5-0.mp3가 아니다). 내용을 열어 확인했다.
 *
 * 배경 배정 (기획서 배경설계.md 문법)
 *   S5-0  질문·고민 = 검정 / "강의에서는…" = **남의 화면(pain)** / 해소 = 검정 /
 *         "지금부터 시작" = 우리 페이지(work) — 말이 화면으로 넘어가는 다리
 *   S5-12 꾸준함 = 인스타 실화면(결과물) / 소름·자부 = 검정 /
 *         "직접 만들어 보여드렸습니다" = 우리 페이지
 */

import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';
import { KineticWord, BlackCard, BG } from './motion';
import { RichBed } from './motion4';

export const S5E_FPS = 30;

type ECut = {
  t: number;
  text: string;
  big?: boolean;
  /** 배경 — black=검정 카드, 나머지는 RichBed kind */
  bg: 'black' | 'pain' | 'work' | 'insta' | 'aura';
  sfx?: { n: string; at: number; v?: number }[];
};

const Body: React.FC<{ cut: ECut }> = ({ cut }) => (
  <AbsoluteFill style={{ background: BG }}>
    {cut.bg === 'black' ? <BlackCard /> : <RichBed kind={cut.bg} />}
    <KineticWord text={cut.text} center size={cut.big ? 82 : 62} perWord={1.4} />
    {(cut.sfx ?? []).map((s, i) => (
      <Sequence key={i} from={Math.round(s.at * S5E_FPS)} layout="none">
        <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.28} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

const makeEndScene = (audio: string, cuts: ECut[], endSec: number): React.FC => () => (
  <AbsoluteFill style={{ background: BG }}>
    <Audio src={staticFile(audio)} />
    {cuts.map((cut, i) => {
      const from = Math.round(cut.t * S5E_FPS);
      const next = cuts[i + 1]?.t ?? endSec;
      return (
        <Sequence key={i} from={from} durationInFrames={Math.max(1, Math.round((next - cut.t) * S5E_FPS))}>
          <Body cut={cut} />
        </Sequence>
      );
    })}
  </AbsoluteFill>
);

/* ══════════ S5-0 데모 진입 (25.31s) ══════════ */
export const S5_0_CUTS: ECut[] = [
  { t: 0.00, bg: 'black', big: true, text: '영상 만들 때, 제일 답답한 게 뭔지 아십니까.',
    sfx: [{ n: 'boom.mp3', at: 0, v: 0.26 }] },
  { t: 3.60, bg: 'black', big: true, text: '"오늘은 뭘 만들지." |이겁니다.|',
    sfx: [{ n: 'punch.mp3', at: 0.6, v: 0.32 }] },
  { t: 5.86, bg: 'pain', text: '강의에서는, 잘되는 채널들을 미리 팔로우해 놓고,' },
  { t: 8.96, bg: 'pain', text: '매일 들여다보면서 떡상 영상을 찾아 |저장해 두라고 하죠.|' },
  { t: 12.88, bg: 'pain', text: '매일 관리하는 것도 번거롭지만…' },
  { t: 14.72, bg: 'pain', text: '뭘 만들지 그 막막한 고민이, |제일 지긋지긋한 스트레스입니다.|',
    sfx: [{ n: 'subpoint.mp3', at: 1.6, v: 0.24 }] },
  { t: 19.40, bg: 'black', big: true, text: '그래서 그 첫 단계부터 |아예 없앴습니다.|',
    sfx: [{ n: 'boom.mp3', at: 0, v: 0.34 }] },
  { t: 22.32, bg: 'work', big: true, text: '|지금부터 시작입니다.|',
    sfx: [{ n: 'whoosh.mp3', at: 0, v: 0.32 }] },
  { t: 23.98, bg: 'work', text: '집중해 주시기 바랍니다.' },
];
export const S5_0_END = 25.31;
export const S5_0_FRAMES = Math.round(S5_0_END * S5E_FPS);
export const S5_0Scene = makeEndScene('vsl/s5-0.mp3', S5_0_CUTS, S5_0_END);

/* ══════════ S5-12 마무리 (30.59s) ══════════
   ★여기서 사람 냄새가 나야 판다(대본 지시). 그래서 소름·자부 대목은 화면을 비운다. */
export const S5_12_CUTS: ECut[] = [
  { t: 0.00, bg: 'insta', text: '서두에 말씀드렸죠. 쇼핑쇼츠, 매일 꾸준히 올리는 게 |제일 힘들다고.|',
    sfx: [{ n: 'whoosh.mp3', at: 0, v: 0.28 }] },
  { t: 4.36, bg: 'insta', text: '근데 만드는 데 |십 분이면|, 하루에 몇 개든 뽑습니다.',
    sfx: [{ n: 'ding2.mp3', at: 0.4, v: 0.24 }] },
  { t: 7.48, bg: 'insta', big: true, text: '이제 꾸준함이, |더 이상 힘든 일이 아닙니다.|',
    sfx: [{ n: 'ding.wav', at: 0.2, v: 0.28 }] },
  { t: 10.22, bg: 'black', text: '이거 완성하고 처음 돌려봤을 때… |솔직히 소름이 쫙 돋았습니다.|',
    sfx: [{ n: 'boom.mp3', at: 0, v: 0.26 }] },
  { t: 14.74, bg: 'black', big: true, text: '"이게… |진짜 되네?|"',
    sfx: [{ n: 'punch.mp3', at: 0.3, v: 0.32 }] },
  { t: 16.66, bg: 'aura', text: '다른 데선 "이렇게 하세요"까지만 말합니다.' },
  { t: 18.92, bg: 'work', text: '숏템메이커는, 말이 아니라 |방금 눈앞에서 직접 만들어 보여드렸습니다.|',
    sfx: [{ n: 'subpoint.mp3', at: 1.2, v: 0.26 }] },
  { t: 23.68, bg: 'black', big: true, text: '|더 이상 비싼 강의에 휘둘리지 마십시오.|',
    sfx: [{ n: 'boom.mp3', at: 0, v: 0.34 }] },
  { t: 26.20, bg: 'black', big: true, text: '숏템메이커는, 현존 쇼핑쇼츠 자동화 |최고의 도구라 자부합니다.|',
    sfx: [{ n: 'ding.wav', at: 0.4, v: 0.32 }] },
];
export const S5_12_END = 30.59;
export const S5_12_FRAMES = Math.round(S5_12_END * S5E_FPS);
export const S5_12Scene = makeEndScene('vsl/s5-12.mp3', S5_12_CUTS, S5_12_END);
