/**
 * S1ColdOpen v3 — 기획서 `영상제작/00_기획/S1_장면설계.md`의 컷 시트를 그대로 구현.
 *
 * v2에서 뭐가 문제였나: 레이아웃은 5종인데 **모션이 사실상 1종**(스케일 팝 + 켄번즈)이라
 * 화면이 계속 바뀌는데도 단조로웠다. v3는 모션 어휘 8종(motion.tsx)을 문장마다 배정해
 * "결과물이 쏟아진다"는 주장 자체를 화면 문법으로 만든다.
 *
 * 타이밍: 나레이션 s1.mp3(실측 57.0초) 기준. CUTS[].d는 whisper 문장 타임스탬프에서
 * 뽑은 값으로 갈아끼운다(04_자막_타임스탬프/s1_words.json → tools로 생성).
 */

import React from 'react';
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import {
  BG, Clip, GridBloom, PickZoom, SliceWipe, WhipPan, CardStack,
  KineticWord, CountPunch, BlackCard, Reel, BlurBed, useKick, Flash, ProgressBar,
} from './motion';

export const S1_FPS = 30;

/* ── 재료(ffprobe 실측 2026-08-11) — 카톡 신규 5 + 기존 final 4 ───────── */
export const S1_CLIPS: Clip[] = [
  { src: 'vsl/s1/KakaoTalk_20260811_100239161.mp4', dur: 32.5 },
  { src: 'vsl/s1/KakaoTalk_20260811_100723116.mp4', dur: 25.4 },
  { src: 'vsl/s1/KakaoTalk_20260811_103115345.mp4', dur: 34.5 },
  { src: 'vsl/s1/KakaoTalk_20260811_104842839.mp4', dur: 30.1 },
  { src: 'vsl/s1/KakaoTalk_20260811_105318092.mp4', dur: 31.5 },
  { src: 'vsl/s1/final_31b394c4685d.mp4', dur: 27.5 },
  { src: 'vsl/s1/final_63d8494f99e3.mp4', dur: 28.3 },
  { src: 'vsl/s1/final_8b7facca37a8.mp4', dur: 24.1 },
  { src: 'vsl/s1/final_e22413db7460.mp4', dur: 17.5 },
];
const C = (i: number) => S1_CLIPS[i % S1_CLIPS.length];

/* ── 컷 시트 ─────────────────────────────────────────────────
   m = 모션 어휘, d = 길이(초), text = 자막(|구간|은 민트 스탬프) */
type Motion =
  | { m: 'grid'; clips: number[] }
  | { m: 'pick'; hero: number; others?: number[] }
  | { m: 'slice'; clip: number; from?: 'top' | 'bottom' }
  | { m: 'whip'; clip: number; dir?: 1 | -1 }
  | { m: 'stack'; clips: number[] }
  | { m: 'count'; from: number; to: number; suffix?: string; label?: string; clip: number }
  | { m: 'black' }
  | { m: 'quote'; clip: number };

/** 효과음 한 방 — n=public/vsl/sfx 파일명, at=컷 시작 기준 초, v=볼륨(나레이션이 주인공이라 낮게) */
type Sfx = { n: string; at: number; v?: number };
type Cut = { text: string; sub?: string; d: number; big?: boolean; sfx?: Sfx[] } & Motion;

/** 자주 쓰는 조합 — 손으로 매번 적으면 볼륨이 제각각이 된다(같은 소리가 컷마다 다른 크기로 들리는 게
 *  '아마추어 티'의 대표 증상). 여기서 한 번만 정하고 전 컷이 이걸 쓴다. */
const SFX = {
  whoosh: (at = 0, v = 0.34): Sfx => ({ n: 'whoosh.mp3', at, v }),
  pop: (at = 0, v = 0.30): Sfx => ({ n: 'pop.wav', at, v }),
  pop2: (at = 0, v = 0.26): Sfx => ({ n: 'pop2.wav', at, v }),
  boom: (at = 0, v = 0.30): Sfx => ({ n: 'boom.mp3', at, v }),
  punch: (at = 0, v = 0.40): Sfx => ({ n: 'punch.mp3', at, v }),
  click: (at = 0, v = 0.42): Sfx => ({ n: 'click.mp3', at, v }),
  ding: (at = 0, v = 0.30): Sfx => ({ n: 'ding.wav', at, v }),
  ding2: (at = 0, v = 0.22): Sfx => ({ n: 'ding2.mp3', at, v }),
  key: (at = 0, v = 0.34): Sfx => ({ n: 'keyboard.mp3', at, v }),
  sub: (at = 0, v = 0.24): Sfx => ({ n: 'subpoint.mp3', at, v }),
};

/** ★d는 whisper 실측(s1_words.json, 22세그먼트)에서 뽑은 값이다 — 합 57.00초 = mp3 길이.
 *  손으로 어림하지 않는다: 자막이 반 박자 어긋나면 "AI가 만든 티"가 바로 난다. */
export const S1_CUTS: Cut[] = [
  { text: '지금 보시는 |이 쇼츠들.|', d: 1.90, m: 'grid', clips: [0, 1, 2, 3, 4, 5, 6, 7, 8],
    sfx: [SFX.pop(0), SFX.pop(0.12, 0.24), SFX.pop(0.24, 0.2), SFX.sub(0.9)] },
  { text: '제가 직접 손으로 만든 게 |아닙니다.|', d: 1.60, m: 'pick', hero: 2, others: [0, 4],
    sfx: [SFX.whoosh(0), SFX.ding2(0.9)] },
  // 아이러니 한 방: "키보드요?"에 키보드 타건음을 깔고 "안 쳤습니다"에서 두둥으로 끊는다.
  { text: '키보드요? 단 한 번도 |안 쳤습니다.|', d: 2.10, m: 'black', big: true,
    sfx: [SFX.key(0), SFX.boom(0.95, 0.34)] },
  { text: '그냥 |버튼만| 눌렀습니다.', d: 1.44, m: 'slice', clip: 3,
    sfx: [SFX.whoosh(0), SFX.click(0.55)] },
  { text: '', d: 2.06, m: 'count', from: 180, to: 10, suffix: '분', label: '하나 만드는 데', clip: 1,
    sfx: [SFX.whoosh(0, 0.26), SFX.punch(0.85)] },   // 0.85s = CountPunch 착지 시점
  { text: '자막도, 성우도, 편집도 |전부 버튼으로만.|', d: 2.86, m: 'stack', clips: [5, 0, 6],
    sfx: [SFX.pop2(0.05), SFX.pop2(0.18), SFX.pop2(0.31), SFX.sub(1.5)] },
  { text: '|이 퀄리티| 보십시오.', d: 1.48, m: 'pick', hero: 4, others: [7, 1],
    sfx: [SFX.ding(0, 0.28)] },
  { text: '숙련된 제작자가 |두세 시간| 꼬박 수작업한 것보다 낫습니다.', d: 4.42, m: 'whip', clip: 6, dir: 1,
    sfx: [SFX.whoosh(0), SFX.sub(1.4)] },
  { text: '대본이랑 영상 장면이 |딱딱| 맞습니다.', d: 2.42, m: 'slice', clip: 7, from: 'bottom',
    sfx: [SFX.whoosh(0), SFX.click(1.05, 0.32), SFX.click(1.22, 0.32)] },   // '딱딱'에 두 번
  { text: '정말, |놀랍지 않습니까?|', d: 1.58, m: 'pick', hero: 8, others: [2, 5],
    sfx: [SFX.ding2(0.15)] },
  { text: '쇼츠와 전혀 관련 없는 지인 몇 분께 먼저 드려봤거든요.', d: 4.52, m: 'grid', clips: [1, 3, 5, 7, 0, 4],
    sfx: [SFX.pop(0), SFX.pop(0.12, 0.24), SFX.pop(0.24, 0.2)] },
  { text: '하나같이 |그러시더군요.|', d: 1.60, m: 'whip', clip: 3, dir: -1,
    sfx: [SFX.whoosh(0)] },
  { text: '"와, 이게 |이렇게까지| 된다고?"', d: 2.30, m: 'quote', clip: 0, big: true,
    sfx: [SFX.ding(0, 0.34)] },
  { text: '시중 자동화 프로그램, |내 돈 주고| 통째로 다 뜯어봤습니다.', d: 4.24, m: 'whip', clip: 5, dir: 1,
    sfx: [SFX.whoosh(0)] },
  { text: '근데 하나같이 |구멍투성이더군요.|', d: 2.50, m: 'black', big: true,
    sfx: [SFX.boom(0, 0.36)] },
  { text: '답답해서, 결국 |제가 직접| 만들었습니다.', d: 2.56, m: 'pick', hero: 6, others: [3, 8],
    sfx: [SFX.whoosh(0), SFX.sub(1.0)] },
  { text: '말로만 하지 않겠습니다.', d: 1.30, m: 'black', big: true,
    sfx: [SFX.boom(0, 0.26)] },
  { text: '이 영상 안에서 |처음부터 끝까지| 하나를 실제로 만들어 보여드립니다.', d: 5.16, m: 'stack', clips: [2, 7, 4],
    sfx: [SFX.pop2(0.05), SFX.pop2(0.18), SFX.pop2(0.31), SFX.sub(1.9)] },
  // "마우스 클릭, 그것뿐" — 클릭음 3연타가 대사를 그대로 증명한다.
  { text: '', d: 3.10, m: 'count', from: 0, to: 1, label: '제가 화면에서 하는 건 마우스 클릭. 그것뿐.', clip: 8,
    sfx: [SFX.click(0.2), SFX.click(0.5), SFX.click(0.8), SFX.punch(0.85, 0.3)] },
  { text: '설계 목표는 |딱 하나|였습니다.', d: 2.02, m: 'slice', clip: 4, from: 'bottom',
    sfx: [SFX.whoosh(0), SFX.sub(0.85)] },
  { text: '우리 |육십 대 어머니도| 직접 할 수 있게.', d: 2.54, m: 'pick', hero: 1, others: [6, 0],
    sfx: [SFX.ding2(0.1)] },
  { text: '왜 하필 어머니였는지는… |마지막에| 말씀드리겠습니다.', d: 3.30, m: 'black', big: true,
    sfx: [SFX.boom(0, 0.32)] },
];

export const S1_FRAMES = Math.round(S1_CUTS.reduce((a, c) => a + c.d, 0) * S1_FPS);

/* ── 컷 하나 렌더 ───────────────────────────────────────────── */
const CutView: React.FC<{ cut: Cut; idx: number }> = ({ cut, idx }) => {
  const { scale, flash } = useKick();
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  let body: React.ReactNode = null;
  switch (cut.m) {
    case 'grid':
      body = <GridBloom clips={cut.clips.map(C)} cols={cut.clips.length > 6 ? 3 : 3} />;
      break;
    case 'pick':
      body = <PickZoom hero={C(cut.hero)} others={(cut.others ?? []).map(C)} seed={idx} />;
      break;
    case 'slice':
      body = (
        <SliceWipe from={cut.from ?? 'top'}>
          <PickZoom hero={C(cut.clip)} seed={idx} />
        </SliceWipe>
      );
      break;
    case 'whip':
      body = (
        <WhipPan dir={cut.dir ?? 1}>
          <PickZoom hero={C(cut.clip)} seed={idx} />
        </WhipPan>
      );
      break;
    case 'stack':
      body = <CardStack clips={cut.clips.map(C)} seed={idx} />;
      break;
    case 'count':
      body = (
        <AbsoluteFill>
          <BlurBed clip={C(cut.clip)} seed={idx} />
          <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
            <Reel clip={C(cut.clip)} w={470} h={836} seed={idx} dim={0.55} />
          </AbsoluteFill>
          <CountPunch from={cut.from} to={cut.to} suffix={cut.suffix} label={cut.label} />
        </AbsoluteFill>
      );
      break;
    case 'quote':
      body = (
        <AbsoluteFill>
          <BlurBed clip={C(cut.clip)} seed={idx} />
          <AbsoluteFill style={{ background: 'rgba(0,0,0,0.42)' }} />
        </AbsoluteFill>
      );
      break;
    case 'black':
      body = <BlackCard />;
      break;
  }

  const centered = cut.m === 'black' || cut.m === 'quote';
  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>{body}</AbsoluteFill>
      {/* 자막 가독 그라데이션 — 암전·인용 카드엔 필요 없다 */}
      {!centered && (
        <AbsoluteFill style={{
          background: 'linear-gradient(to top, rgba(0,0,0,0.76) 0%, rgba(0,0,0,0) 32%)',
          pointerEvents: 'none',
        }} />
      )}
      {cut.text ? (
        <KineticWord hi="underline" text={cut.text} sub={cut.sub} center={centered}
          size={cut.big ? 92 : 74} />
      ) : null}
      <Flash v={flash} />
      <ProgressBar p={frame / durationInFrames} />
      {/* 효과음 — 컷 안의 자기 시점에서 한 번만 울린다.
          ★<Sequence>로 감싸는 이유: <Audio>는 시퀀스 시작 프레임에 재생을 맞춘다.
          그냥 얹으면 컷이 시작하는 순간 전부 동시에 터져 '뭉개진 한 방'이 된다. */}
      {(cut.sfx ?? []).map((s, i) => (
        <Sequence key={i} from={Math.round(s.at * S1_FPS)} layout="none">
          <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.3} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const S1ColdOpen: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      {/* 나레이션 — 이 트랙이 타이밍의 기준선이다 */}
      <Audio src={staticFile('vsl/s1.mp3')} />
      {S1_CUTS.map((cut, i) => {
        const from = Math.round(at * S1_FPS);
        at += cut.d;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.round(cut.d * S1_FPS)}>
            <CutView cut={cut} idx={i} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
