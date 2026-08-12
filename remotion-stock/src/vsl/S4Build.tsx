/**
 * S4Build — 탄생 + 원리. s4.mp3 실측 59.14초 / whisper 22세그먼트.
 *
 * 색: S1과 같은 민트다. S2에서 회색으로 눌러 놓은 뒤라 여기서 색이 완전히 돌아오면
 * "문제 → 해결"의 곡선이 씬 단위로 완성된다(S2 기획서 §2의 연장).
 *
 * 증거 우선: 앞부분(탄생)은 지어낸 그래픽 대신 **실제 repo 통계·커밋 메시지**를 쓴다.
 * 뒷부분(원리)은 촬영본이 없어도 되는 4단계 도식 — 화면녹화 3개와 교대로 배치했다.
 */

import React from 'react';
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import {
  BlackCard, Flash, ProgressBar, KineticWord, useKick, SliceWipe, WhipPan, MINT, BG,
} from './motion';
import {
  CommitRain, StatBig, NightHeatmap, FlowDiagram, BrandReveal, Screen4, BUILD,
} from './motion3';

export const S4_FPS = 30;

type Body =
  | { m: 'black' }
  | { m: 'rain'; speed?: number }
  | { m: 'stat'; to: number; label: string; sub?: string; suffix?: string; rain?: boolean }
  | { m: 'night' }
  | { m: 'brand' }
  | { m: 'flow'; activeAt?: number[]; allOn?: boolean }
  | { m: 'screen'; src: string; at?: number; speed?: number }
  | { m: 'slice'; src: string; at?: number }
  | { m: 'whip'; src: string; at?: number; dir?: 1 | -1 };

type Sfx = { n: string; at: number; v?: number };
type Cut = { text: string; d: number; big?: boolean; center?: boolean; sfx?: Sfx[] } & Body;

const S = {
  whoosh: (at = 0, v = 0.32): Sfx => ({ n: 'whoosh.mp3', at, v }),
  boom: (at = 0, v = 0.30): Sfx => ({ n: 'boom.mp3', at, v }),
  punch: (at = 0, v = 0.38): Sfx => ({ n: 'punch.mp3', at, v }),
  click: (at = 0, v = 0.30): Sfx => ({ n: 'click.mp3', at, v }),
  ding: (at = 0, v = 0.32): Sfx => ({ n: 'ding.wav', at, v }),
  ding2: (at = 0, v = 0.22): Sfx => ({ n: 'ding2.mp3', at, v }),
  key: (at = 0, v = 0.30): Sfx => ({ n: 'keyboard.mp3', at, v }),
  sub: (at = 0, v = 0.22): Sfx => ({ n: 'subpoint.mp3', at, v }),
  pop: (at = 0, v = 0.26): Sfx => ({ n: 'pop.wav', at, v }),
};

/** whisper 22세그먼트 → 18컷 (합 59.14초 = mp3 길이) */
export const S4_CUTS: Cut[] = [
  { text: '그래서 그냥, |제가 만들기로| 했습니다.', d: 2.08, m: 'black', big: true, center: true,
    sfx: [S.boom(0, 0.28)] },
  // 여기서부터 '증거' — 실제 커밋 메시지가 쏟아진다
  { text: '한 달간, 시중 프로그램을 하나도 빼놓지 않고 |전부 뜯어봤습니다.|', d: 3.96, m: 'rain', speed: 1.1,
    sfx: [S.whoosh(0), S.key(1.4, 0.24)] },
  { text: '그리고 |직접 만들었습니다.|', d: 1.62, m: 'screen', src: 'vsl/s4/rec1.mp4', at: 2, speed: 1.5,
    sfx: [S.whoosh(0)] },
  { text: '제가 수작업으로 쇼츠 만들면서 힘들었고, 귀찮았고…', d: 3.64, m: 'screen', src: 'vsl/s4/rec1.mp4', at: 10, speed: 1.3 },
  { text: '막혔던 그 병목들, |하나하나 다 뜯어고쳤습니다.|', d: 3.14, m: 'stat', to: BUILD.total,
    label: '숏템메이커 커밋', sub: `${BUILD.first} ~ ${BUILD.last} · ${BUILD.days}일`, rain: true,
    sfx: [S.whoosh(0, 0.26), S.punch(1.1, 0.4)] },
  { text: '아니, |지금도 매일| 진화하고 있습니다.', d: 2.14, m: 'night',
    sfx: [S.pop(0), S.pop(0.25, 0.2), S.pop(0.5, 0.18)] },
  { text: '그렇게 나온 게 이겁니다…', d: 1.80, m: 'black', center: true,
    sfx: [S.boom(0, 0.24)] },
  { text: '', d: 1.08, m: 'brand',
    sfx: [S.ding(0, 0.4)] },
  { text: '원리는 |간단합니다.|', d: 1.24, m: 'black', big: true, center: true },
  // 원리 1 — 실제 랭킹 화면
  { text: '지금 이 순간, 제일 터지고 있는 영상들을 |바로 찾아줍니다.|', d: 3.66, m: 'screen', src: 'vsl/s4/rec2.mp4', at: 3, speed: 1.3,
    sfx: [S.whoosh(0), S.sub(1.6)] },
  { text: '그리고 검증된 떡상 영상으로 |바로 벤치마킹|하는 거죠.', d: 3.36, m: 'whip', src: 'vsl/s4/rec3.mp4', at: 4, dir: 1,
    sfx: [S.whoosh(0)] },
  // 원리 도식 — 단계가 하나씩 켜진다
  { text: '떡상 영상을 토대로, |동일한 원본 영상들도| 자동으로 수집합니다.', d: 4.20, m: 'flow', activeAt: [0.0, 1.6, 99, 99],
    sfx: [S.click(0.0), S.click(1.6)] },
  { text: '대본은 내 제품에 맞게 |S급으로 새로| 씁니다.', d: 3.22, m: 'flow', activeAt: [-1, -1, 0.4, 99],
    sfx: [S.click(0.4)] },
  { text: '그리고 영상 장면에 |딱딱 맞게| 배치합니다.', d: 2.54, m: 'flow', activeAt: [-1, -1, -1, 0.3],
    sfx: [S.click(0.3), S.click(0.55)] },
  { text: '그냥 베끼는 게 아닙니다. |터지는 트렌드만, 내 걸로| 가져오는 겁니다.', d: 3.98, m: 'flow', allOn: true,
    sfx: [S.ding2(0.2), S.sub(1.8)] },
  { text: '제가 내린 결론은 이겁니다.', d: 1.98, m: 'black', center: true },
  { text: '쇼핑쇼츠는, 어느 정도만 만들면 일반인들은 |다 비슷하게 봅니다.|', d: 4.16, m: 'slice', src: 'vsl/s4/rec2.mp4', at: 14,
    sfx: [S.whoosh(0)] },
  { text: '|진짜 승부는 여기서| 갈립니다.', d: 1.96, m: 'black', big: true, center: true,
    sfx: [S.boom(0, 0.36)] },
  { text: '지금 터지는 영상을 얼마나 더 빠르고 트렌디하게, 스토리를 넣은 대본으로 |내 것처럼| 벤치마킹해서 뿌리느냐.', d: 6.90, m: 'flow', allOn: true,
    sfx: [S.sub(0.4), S.sub(3.4, 0.18)] },
  { text: '숏템메이커는, |그걸 전부 자동으로| 합니다.', d: 2.48, m: 'brand',
    sfx: [S.ding(0, 0.42)] },
];

export const S4_FRAMES = Math.round(S4_CUTS.reduce((a, c) => a + c.d, 0) * S4_FPS);

const CutView: React.FC<{ cut: Cut; idx: number }> = ({ cut, idx }) => {
  const { scale, flash } = useKick();
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  let body: React.ReactNode = null;
  switch (cut.m) {
    case 'black': body = <BlackCard />; break;
    case 'rain': body = <CommitRain speed={cut.speed} />; break;
    case 'stat':
      body = (
        <AbsoluteFill>
          {cut.rain ? <CommitRain speed={0.7} dim={0.74} /> : <BlackCard />}
          <StatBig to={cut.to} label={cut.label} sub={cut.sub} suffix={cut.suffix} />
        </AbsoluteFill>
      );
      break;
    case 'night': body = <NightHeatmap />; break;
    case 'brand': body = <BrandReveal />; break;
    case 'flow': body = <FlowDiagram activeAt={cut.activeAt ?? [0, 0.9, 1.8, 2.7]} allOn={cut.allOn} />; break;
    case 'screen': body = <Screen4 src={cut.src} at={cut.at} speed={cut.speed} />; break;
    case 'slice': body = <SliceWipe><Screen4 src={cut.src} at={cut.at} speed={1.3} /></SliceWipe>; break;
    case 'whip': body = <WhipPan dir={cut.dir ?? 1}><Screen4 src={cut.src} at={cut.at} speed={1.3} /></WhipPan>; break;
  }

  // 도식·통계·브랜드는 이미 중앙 구성이라 자막을 하단에 두면 겹치지 않는다.
  const centered = cut.center;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>{body}</AbsoluteFill>
      {!centered && (
        <AbsoluteFill style={{
          background: 'linear-gradient(to top, rgba(0,0,0,0.80) 0%, rgba(0,0,0,0) 30%)',
          pointerEvents: 'none',
        }} />
      )}
      {cut.text ? (
        <KineticWord hi="underline" text={cut.text} center={centered} size={cut.big ? 92 : 66} />
      ) : null}
      <Flash v={flash} />
      <ProgressBar p={frame / durationInFrames} />
      {(cut.sfx ?? []).map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * S4_FPS)} layout="none">
          <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.3} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const S4Build: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Audio src={staticFile('vsl/s4.mp3')} />
      {S4_CUTS.map((cut, i) => {
        const from = Math.round(at * S4_FPS);
        at += cut.d;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.round(cut.d * S4_FPS)}>
            <CutView cut={cut} idx={i} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
