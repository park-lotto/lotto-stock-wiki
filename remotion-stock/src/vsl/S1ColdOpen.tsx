/**
 * S1ColdOpen — VSL 1회차 콜드오픈(2026-08-11 사장님 지시 "속도감 있게 전환하면서").
 *
 * 구조: 대본 한 줄 = 한 섹션. 섹션마다 레이아웃(triptych/single/duo/quote/black)을
 * 바꿔가며 완성본 쇼츠 10개를 빠르게 순환한다 — "결과물이 계속 쏟아진다"는 인상이 S1의 논지.
 *
 * ★타이밍은 TTS 입고 전의 **추정치**다(CAPS[].dur, 합 ≈ 67초). S1.mp3가 오면
 *   faster-whisper 단어 타임스탬프로 start/dur만 갈아끼운다 — 레이아웃 코드는 그대로.
 *
 * 재료: 바탕화면 영상제작/02_장면소재/S1_완성쇼츠들 → public/vsl/s1/ (git 미추적,
 *   .gitignore: remotion-stock/public/**\/*.mp4 — 다른 PC에선 같은 폴더에서 다시 복사).
 */

import React from 'react';
import {
  AbsoluteFill, Loop, OffthreadVideo, Sequence, interpolate,
  spring, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';

/* ── 재료: ffprobe 실측 길이(2026-08-11) ─────────────────────── */
type Clip = { src: string; dur: number };
export const S1_CLIPS: Clip[] = [
  { src: 'vsl/s1/final_31b394c4685d.mp4', dur: 27.5 },
  { src: 'vsl/s1/final_4115571b6c67.mp4', dur: 25.5 },
  { src: 'vsl/s1/final_4f3a7a9b5e35.mp4', dur: 13.2 },
  { src: 'vsl/s1/final_63d8494f99e3.mp4', dur: 28.3 },
  { src: 'vsl/s1/final_8b7facca37a8.mp4', dur: 24.1 },
  { src: 'vsl/s1/final_a0157a0ed29d.mp4', dur: 31.1 },
  { src: 'vsl/s1/final_bb9db3a5f759.mp4', dur: 22.3 },
  { src: 'vsl/s1/final_ddccf1efabd4.mp4', dur: 22.3 },
  { src: 'vsl/s1/final_df9b54de557d.mp4', dur: 23.4 },
  { src: 'vsl/s1/final_e22413db7460.mp4', dur: 17.5 },
];

/* ── 대본 → 섹션 표. text의 |는 강조 하이라이트 구간 ───────────── */
type Layout = 'triptych' | 'single' | 'duo' | 'quote' | 'black';
type Cap = {
  text: string; dur: number; layout: Layout;
  clips: number[];          // S1_CLIPS 인덱스
  sub?: string;             // 작은 보조줄
};
export const S1_CAPS: Cap[] = [
  { text: '지금 보시는 |이 쇼츠들.|', dur: 3.0, layout: 'triptych', clips: [0, 1, 3] },
  { text: '제가 직접 손으로 만든 게 |아닙니다.|', dur: 3.4, layout: 'triptych', clips: [0, 1, 3] },
  { text: '키보드, 단 한 번도 안 쳤습니다.', sub: '그냥 버튼만 눌렀습니다', dur: 5.2, layout: 'single', clips: [4] },
  { text: '하나에 |십 분.|', sub: '자막·성우·편집 전부 버튼으로만', dur: 5.4, layout: 'single', clips: [2] },
  { text: '|이 퀄리티| 보십시오.', sub: '숙련자 2~3시간 수작업보다 낫습니다', dur: 5.6, layout: 'duo', clips: [5, 6] },
  { text: '대본과 장면이 |딱딱| 맞습니다.', sub: '놀랍지 않습니까?', dur: 4.6, layout: 'single', clips: [7] },
  { text: '쇼츠와 관련 없는 지인들께 먼저 드려봤습니다.', dur: 4.0, layout: 'triptych', clips: [8, 9, 2] },
  { text: '"와, 이게 |이렇게까지| 된다고?"', dur: 3.2, layout: 'quote', clips: [9] },
  { text: '시중 자동화 프로그램, 내 돈 주고 다 뜯어봤습니다.', dur: 4.2, layout: 'single', clips: [1] },
  { text: '하나같이 |구멍투성이.|', dur: 2.6, layout: 'black', clips: [] },
  { text: '답답해서, 결국 |제가 직접| 만들었습니다.', dur: 3.6, layout: 'single', clips: [3] },
  { text: '말로만 하지 않겠습니다.', dur: 2.4, layout: 'black', clips: [] },
  { text: '이 영상에서 |처음부터 끝까지| 하나를 실제로 만들어 보여드립니다.', dur: 5.6, layout: 'duo', clips: [0, 8] },
  { text: '제가 하는 건 |마우스 클릭.| 그것뿐.', dur: 3.4, layout: 'single', clips: [6] },
  { text: '목표는 하나. |60대 어머니도| 직접 할 수 있게.', dur: 4.4, layout: 'single', clips: [5] },
  { text: '왜 어머니였는지는… |마지막에| 말씀드리겠습니다.', dur: 3.2, layout: 'black', clips: [] },
  { text: '소문나기 전에, |빨리| 보시길 바랍니다.', dur: 3.0, layout: 'quote', clips: [4] },
];

export const S1_FPS = 30;
export const S1_FRAMES = Math.round(S1_CAPS.reduce((a, c) => a + c.dur, 0) * S1_FPS);

const BG = '#08110E';
const MINT = '#3DF0B2';
const FONT = "'Pretendard','Archivo',sans-serif";

/* 세로 9:16 릴 팬 — 시작점을 중반부로 밀어 각 컷이 다른 장면을 보여준다 */
const Pane: React.FC<{ clip: Clip; w: number; h: number; seed: number; radius?: number }> = ({
  clip, w, h, seed, radius = 16,
}) => {
  const { fps } = useVideoConfig();
  const offset = (clip.dur * 0.25 * ((seed % 3) + 1)) % Math.max(1, clip.dur - 4);
  const usable = Math.max(1.5, clip.dur - offset);
  return (
    // ★position:relative 필수 — <Loop>는 내부에서 absolute-fill <Sequence>를 만든다.
    //   static이면 앵커가 바깥 전체화면 AbsoluteFill로 잡혀 영상이 액자를 뚫고 풀스크린이 된다
    //   (2026-08-11 v1 렌더 프레임 실측으로 발견).
    <div style={{ position: 'relative', width: w, height: h, overflow: 'hidden', borderRadius: radius,
      background: '#000', boxShadow: '0 18px 48px rgba(0,0,0,0.55)' }}>
      <Loop durationInFrames={Math.max(1, Math.floor(usable * fps))}>
        <OffthreadVideo src={staticFile(clip.src)} trimBefore={Math.round(offset * fps)}
          volume={0} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </Loop>
    </div>
  );
};

/* 흐린 배경 채움 — 같은 클립을 크게 깔고 블러 */
const BlurBg: React.FC<{ clip: Clip; seed: number }> = ({ clip, seed }) => {
  const { fps } = useVideoConfig();
  const offset = (clip.dur * 0.3 * ((seed % 2) + 1)) % Math.max(1, clip.dur - 4);
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Loop durationInFrames={Math.max(1, Math.floor((clip.dur - offset) * fps))}>
        <OffthreadVideo src={staticFile(clip.src)} trimBefore={Math.round(offset * fps)} volume={0}
          style={{ width: '100%', height: '100%', objectFit: 'cover',
            filter: 'blur(42px) brightness(0.35) saturate(1.2)', transform: 'scale(1.15)' }} />
      </Loop>
    </AbsoluteFill>
  );
};

/* 킥 — 섹션 진입 시 화면 전체 펀치(스케일+미세 회전) & 민트 플래시 */
const useKick = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 14, stiffness: 190, mass: 0.6 } });
  const scale = interpolate(pop, [0, 1], [1.08, 1]);
  const flash = interpolate(frame, [0, 5], [0.55, 0], { extrapolateRight: 'clamp' });
  return { scale, flash };
};

/* 강조 파싱: |구간|을 민트 하이라이트로 */
const Rich: React.FC<{ text: string; size: number }> = ({ text, size }) => {
  const parts = text.split('|');
  return (
    <span style={{ fontFamily: FONT, fontWeight: 900, fontSize: size, lineHeight: 1.22,
      color: '#fff', textShadow: '0 8px 34px rgba(0,0,0,0.75)', wordBreak: 'keep-all' }}>
      {parts.map((p, i) => i % 2 === 1
        ? <span key={i} style={{ color: MINT, textShadow: `0 0 34px ${MINT}55` }}>{p}</span>
        : <span key={i}>{p}</span>)}
    </span>
  );
};

/* 자막 블록 — 단어 계단식 팝인 */
const Caption: React.FC<{ cap: Cap; big?: boolean; center?: boolean }> = ({ cap, big, center }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const up = spring({ frame, fps, config: { damping: 15, stiffness: 170 } });
  const y = interpolate(up, [0, 1], [46, 0]);
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: center ? 'center' : 'flex-end',
      paddingBottom: center ? 0 : 96, pointerEvents: 'none' }}>
      <div style={{ transform: `translateY(${y}px)`, opacity: up, textAlign: 'center', maxWidth: 1560 }}>
        <Rich text={cap.text} size={big ? 96 : 72} />
        {cap.sub ? (
          <div style={{ marginTop: 18, fontFamily: FONT, fontWeight: 700, fontSize: 40,
            color: 'rgba(255,255,255,0.82)', textShadow: '0 4px 20px rgba(0,0,0,0.7)' }}>
            {cap.sub}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

const REEL_W = 560, REEL_H = 996;

const Section: React.FC<{ cap: Cap; idx: number }> = ({ cap, idx }) => {
  const { scale, flash } = useKick();
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  // 켄번즈 — 홀수 섹션은 줌인, 짝수는 줌아웃(단조로움 방지)
  const drift = interpolate(frame, [0, durationInFrames], idx % 2 ? [1, 1.06] : [1.06, 1]);
  const clips = cap.clips.map((i) => S1_CLIPS[i]);

  let body: React.ReactNode = null;
  if (cap.layout === 'triptych') {
    body = (
      <AbsoluteFill style={{ flexDirection: 'row', gap: 22, alignItems: 'center', justifyContent: 'center' }}>
        {clips.map((c, i) => <Pane key={i} clip={c} w={REEL_W} h={REEL_H} seed={idx + i} />)}
      </AbsoluteFill>
    );
  } else if (cap.layout === 'duo') {
    body = (
      <>
        <BlurBg clip={clips[0]} seed={idx} />
        <AbsoluteFill style={{ flexDirection: 'row', gap: 60, alignItems: 'center', justifyContent: 'center' }}>
          {clips.map((c, i) => <Pane key={i} clip={c} w={520} h={924} seed={idx + i + 1} />)}
        </AbsoluteFill>
      </>
    );
  } else if (cap.layout === 'single' || cap.layout === 'quote') {
    body = (
      <>
        <BlurBg clip={clips[0]} seed={idx} />
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
          <Pane clip={clips[0]} w={588} h={1044} seed={idx + 2} radius={20} />
        </AbsoluteFill>
      </>
    );
  }
  // black은 body 없음(암전 카드)

  const quote = cap.layout === 'quote';
  const black = cap.layout === 'black';
  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill style={{ transform: `scale(${scale * drift})` }}>{body}</AbsoluteFill>
      {/* 자막 가독용 하단 그라데이션(암전 카드 제외) */}
      {!black && (
        <AbsoluteFill style={{ background: quote
          ? 'rgba(0,0,0,0.45)'
          : 'linear-gradient(to top, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0) 34%)' }} />
      )}
      <Caption cap={cap} big={quote || black} center={quote || black} />
      {/* 진입 플래시 — 민트 킥 */}
      <AbsoluteFill style={{ background: MINT, opacity: flash * 0.35, pointerEvents: 'none' }} />
      <AbsoluteFill style={{ background: '#fff', opacity: flash * 0.25, pointerEvents: 'none' }} />
      {/* 진행 바 — 위쪽 얇은 민트 라인(섹션 내 진행) */}
      <div style={{ position: 'absolute', top: 0, left: 0, height: 6,
        width: `${(frame / durationInFrames) * 100}%`, background: MINT, opacity: 0.8 }} />
    </AbsoluteFill>
  );
};

export const S1ColdOpen: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      {S1_CAPS.map((cap, i) => {
        const from = Math.round(at * S1_FPS);
        at += cap.dur;
        return (
          <Sequence key={i} from={from} durationInFrames={Math.round(cap.dur * S1_FPS)}>
            <Section cap={cap} idx={i} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
