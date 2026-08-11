/**
 * S2Pain — 동일시 + 진짜 페인. 기획서 `영상제작/00_기획/S2_장면설계.md` 구현.
 *
 * S1과 정반대 원칙: **자랑하지 않는다.** 여기서 화려하면 "또 파는 놈"이 된다.
 * 그래서 화면은 탈색·붉은 경고로 눌러두고, 마지막 2컷에서만 민트가 돌아온다(ColorReturn).
 *
 * 타이밍: s2.mp3 실측 83.23초 / whisper 43세그먼트에서 컷 경계를 뽑았다.
 */

import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';
import { BlackCard, Flash, ProgressBar, CountPunch, useKick, SliceWipe, WhipPan } from './motion';
import {
  Desat, ScreenScroll, ThumbWall, StepChain, ColorReturn, StillPan, PainWord,
  RED, MINT2, GREY_BG,
} from './motion2';

export const S2_FPS = 30;

type Body =
  | { m: 'black' }
  | { m: 'screen'; src: string; at: number; speed?: number }
  | { m: 'wall'; offsets?: number[]; xAt?: number[]; label?: string }
  | { m: 'steps'; appearAt: number[] }
  | { m: 'count'; from: number; to: number; suffix?: string; label?: string; src?: string; at?: number }
  | { m: 'still'; src: string; dir?: 1 | -1 }
  | { m: 'slice'; src: string; at: number }
  | { m: 'whip'; src: string; at: number; dir?: 1 | -1 };

type Sfx = { n: string; at: number; v?: number };
type Cut = { text: string; d: number; big?: boolean; center?: boolean; mint?: boolean; sfx?: Sfx[] } & Body;

const S = {
  whoosh: (at = 0, v = 0.32): Sfx => ({ n: 'whoosh.mp3', at, v }),
  boom: (at = 0, v = 0.32): Sfx => ({ n: 'boom.mp3', at, v }),
  punch: (at = 0, v = 0.34): Sfx => ({ n: 'punch.mp3', at, v }),
  click: (at = 0, v = 0.30): Sfx => ({ n: 'click.mp3', at, v }),
  ding: (at = 0, v = 0.30): Sfx => ({ n: 'ding.wav', at, v }),
  sub: (at = 0, v = 0.22): Sfx => ({ n: 'subpoint.mp3', at, v }),
  pop: (at = 0, v = 0.24): Sfx => ({ n: 'pop.wav', at, v }),
};

/** whisper 43세그먼트를 20컷으로 묶었다(합 83.23초 = mp3 길이). */
export const S2_CUTS: Cut[] = [
  { text: '쇼핑쇼츠가 돈 된다. |진짜일까요?|', d: 2.40, m: 'black', big: true, center: true,
    sfx: [S.boom(0, 0.28)] },
  { text: '하도 떠들어대서 이미 |소문 다 난| 부업 콘텐츠죠.', d: 3.34, m: 'screen', src: 'vsl/s2/rec3.mp4', at: 44, speed: 1.8,
    sfx: [S.whoosh(0)] },
  { text: '근데 왜 다들 |중간에 포기할까요?|', d: 2.12, m: 'slice', src: 'vsl/s2/rec1.mp4', at: 6,
    sfx: [S.whoosh(0), S.sub(0.9)] },
  { text: '이유는 아주 단순합니다.', d: 1.22, m: 'black', center: true },
  { text: '그냥, |만들기가 어렵습니다.|', d: 1.92, m: 'black', big: true, center: true,
    sfx: [S.boom(0, 0.3)] },
  { text: '보기엔 쉬워도, 해야 할 과정이 |지독하게 많거든요.|', d: 2.90, m: 'screen', src: 'vsl/s2/rec2.mp4', at: 8, speed: 1.6,
    sfx: [S.whoosh(0)] },
  { text: '더 솔직히 말씀드리겠습니다.', d: 1.58, m: 'black', center: true },
  { text: '매일 꾸준히 올려야 하는데…', d: 1.82, m: 'still', src: 'vsl/s2/cap1.png', dir: 1 },
  { text: '수익 날 때까지 버티는 게, |제일 지옥입니다.|', d: 2.78, m: 'black', big: true, center: true,
    sfx: [S.boom(0, 0.34)] },
  { text: '저도 그랬습니다. 작년부터 강의를 |닥치는 대로| 다 들었습니다.', d: 4.14, m: 'screen', src: 'vsl/s2/rec3.mp4', at: 8, speed: 1.5,
    sfx: [S.whoosh(0), S.sub(1.6)] },
  // 어그로 썸네일 벽 — ✕가 순서대로 박힌다
  { text: '"월 천만 원을 벌었다." "AI가 해주니 |복붙만| 하면 된다."', d: 3.76, m: 'wall',
    offsets: [4, 14, 24, 34, 44, 54], xAt: [1.6, 2.0, 2.4, 2.8, 3.1, 3.4], label: '유튜브 검색 결과',
    sfx: [S.pop(0), S.punch(1.6, 0.3), S.punch(2.0, 0.26), S.punch(2.4, 0.24)] },
  { text: '근데 끝까지 보면 결론은 하나예요. |"자세한 건 무료강의에서."| 또 링크죠.', d: 4.98, m: 'screen', src: 'vsl/s2/rec3.mp4', at: 30, speed: 1.4,
    sfx: [S.whoosh(0), S.sub(2.2)] },
  { text: '속는 셈 치고 무료강의도 듣고…', d: 2.14, m: 'still', src: 'vsl/s2/cap2.png', dir: -1 },
  { text: '', d: 3.62, m: 'count', from: 0, to: 300, suffix: '만원', label: '결국 제일 좋다는 유료강의까지', src: 'vsl/s2/rec3.mp4', at: 20,
    sfx: [S.whoosh(0, 0.24), S.punch(1.5, 0.4)] },
  { text: '"이것만 들으면 나도 된다." 딱 |그 심리만| 교묘하게 건드립니다.', d: 3.76, m: 'black', center: true,
    sfx: [S.boom(0, 0.26)] },
  { text: '근데 다 들어봐도, 꾸준히 수익 내는 사람은 |극소수더군요.|', d: 3.90, m: 'wall',
    offsets: [10, 20, 30, 40, 50, 58], xAt: [0.4, 0.7, 1.0, 1.3, 1.6, 1.9],
    sfx: [S.punch(0.4, 0.26), S.punch(1.0, 0.22), S.punch(1.6, 0.2)] },
  { text: '그게… 이 시장의 |씁쓸한 비밀입니다.|', d: 2.42, m: 'black', big: true, center: true,
    sfx: [S.boom(0, 0.3)] },
  { text: '그래서 AI만 있으면 다 될 것 같죠? |AI는 요술 지팡이가 아닙니다.|', d: 4.24, m: 'black', big: true, center: true,
    sfx: [S.boom(0.9, 0.36)] },
  { text: '유튜브에선 |잘된 편집만| 보여줄 뿐이고요.', d: 2.42, m: 'whip', src: 'vsl/s2/rec2.mp4', at: 20, dir: 1,
    sfx: [S.whoosh(0)] },
  { text: '그 퀄리티를 뽑으려면, 결국 |많은 과정을 갈아 넣어야| 합니다.', d: 3.68, m: 'screen', src: 'vsl/s2/rec1.mp4', at: 2, speed: 1.5,
    sfx: [S.whoosh(0)] },
  // 6단계 체인 — 대사가 단계를 부를 때마다 하나씩 딸깍
  { text: '', d: 6.00, m: 'steps', appearAt: [0.0, 0.96, 1.78, 3.38, 4.40, 5.10],
    sfx: [S.click(0.0), S.click(0.96), S.click(1.78), S.click(3.38), S.click(4.40), S.click(5.10)] },
  { text: '', d: 1.80, m: 'count', from: 0, to: 3, suffix: '시간', label: '영상 하나에 기본', src: 'vsl/s2/rec2.mp4', at: 30,
    sfx: [S.punch(0.85, 0.42)] },
  { text: '해보신 분들은 |다 아십니다.|', d: 1.68, m: 'black', center: true },
  { text: '하루 종일 붙잡아 겨우 하나 올려도, |조회수는 얼마 안 나옵니다.|', d: 3.62, m: 'screen', src: 'vsl/s2/rec3.mp4', at: 52, speed: 1.3,
    sfx: [S.whoosh(0), S.sub(1.8)] },
  { text: '남들은 하루에 몇 개씩 뽑아낸다는데, 나만 |답답하게 제자리죠.|', d: 3.78, m: 'black', big: true, center: true,
    sfx: [S.boom(0, 0.32)] },
  // ★여기서부터 색이 돌아온다 — 문제 구간의 끝
  { text: '지금까지 들으시고 |고개를 끄덕이셨다면…|', d: 2.44, m: 'still', src: 'vsl/s2/cap1.png', dir: 1, mint: true,
    sfx: [S.ding(0, 0.3)] },
  { text: '여러분은 이미 저와 |같은 문제로| 답답하셨던 거고,', d: 3.00, m: 'screen', src: 'vsl/s2/rec1.mp4', at: 12, speed: 1.2, mint: true },
  { text: '|해결책을 찾을 준비가| 된 겁니다.', d: 1.77, m: 'black', big: true, center: true, mint: true,
    sfx: [S.ding(0, 0.36)] },
];

export const S2_FRAMES = Math.round(S2_CUTS.reduce((a, c) => a + c.d, 0) * S2_FPS);

const CutView: React.FC<{ cut: Cut; idx: number }> = ({ cut, idx }) => {
  const { scale, flash } = useKick();
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  let body: React.ReactNode = null;
  switch (cut.m) {
    case 'black': body = <BlackCard />; break;
    case 'screen': body = <ScreenScroll src={cut.src} startSec={cut.at} speed={cut.speed ?? 1.6} />; break;
    case 'wall': body = <ThumbWall src="vsl/s2/rec3.mp4" offsets={cut.offsets} xAt={cut.xAt} label={cut.label} />; break;
    case 'steps': body = <><AbsoluteFill style={{ background: GREY_BG }} /><StepChain appearAt={cut.appearAt} /></>; break;
    case 'still': body = <StillPan src={cut.src} dir={cut.dir} />; break;
    case 'slice':
      body = <SliceWipe><ScreenScroll src={cut.src} startSec={cut.at} speed={1.5} /></SliceWipe>; break;
    case 'whip':
      body = <WhipPan dir={cut.dir ?? 1}><ScreenScroll src={cut.src} startSec={cut.at} speed={1.4} /></WhipPan>; break;
    case 'count':
      body = (
        <AbsoluteFill>
          {cut.src ? <ScreenScroll src={cut.src} startSec={cut.at ?? 0} speed={1.3} /> : <BlackCard />}
          <AbsoluteFill style={{ background: 'rgba(0,0,0,0.62)' }} />
          <CountPunch from={cut.from} to={cut.to} suffix={cut.suffix} label={cut.label} color={RED} />
        </AbsoluteFill>
      );
      break;
  }

  // 색 규칙: 페인 구간은 탈색, mint 컷만 색이 돌아온다.
  // ★steps/count/wall은 자체가 붉은 UI라 탈색을 씌우면 붉은기가 죽는다 — 통과시킨다.
  const rawUI = cut.m === 'steps' || cut.m === 'count' || cut.m === 'wall' || cut.m === 'black';
  const painted = cut.mint
    ? <ColorReturn>{body}</ColorReturn>
    : rawUI ? body : <Desat>{body}</Desat>;

  return (
    <AbsoluteFill style={{ background: GREY_BG }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>{painted}</AbsoluteFill>
      {!cut.center && (
        <AbsoluteFill style={{
          background: 'linear-gradient(to top, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0) 34%)',
          pointerEvents: 'none',
        }} />
      )}
      {cut.text ? (
        <PainWord text={cut.text} center={cut.center} size={cut.big ? 92 : 74}
          accent={cut.mint ? MINT2 : RED} />
      ) : null}
      <Flash v={flash * 0.6} />
      <ProgressBar p={frame / durationInFrames} color={cut.mint ? MINT2 : RED} />
      {(cut.sfx ?? []).map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * S2_FPS)} layout="none">
          <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.3} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const S2Pain: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: GREY_BG }}>
      <Audio src={staticFile('vsl/s2.mp3')} />
      {S2_CUTS.map((cut, i) => {
        const from = Math.round(at * S2_FPS);
        at += cut.d;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.round(cut.d * S2_FPS)}>
            <CutView cut={cut} idx={i} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
