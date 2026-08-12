/**
 * 세로 쇼츠 (1080×1920) — 2026-08-12
 *
 * 원칙: 가로 마스터를 자르지 않는다. **같은 씬을 세로 캔버스에 다시 그린다.**
 *   자막 줄바꿈은 캔버스 폭을 따라가므로(motion.tsx wrapWidth) 손댈 게 없다.
 *
 * 두 종류가 있고, 배경 소재가 세로냐 가로냐로 갈린다.
 *
 *  ① 배경이 세로(완성 쇼츠·인스타 재생화면) → 씬을 그대로 세로로 렌더한다. 잘리지 않는다.
 *     예: S1 콜드오픈, S6 증거
 *
 *  ② 배경이 가로(화면 녹화 데모) → 크롭하면 브라우저 UI가 잘려 뜻이 사라진다.
 *     그래서 **위쪽에 녹화본을 통째로 앉히고(contain) 아래를 자막 자리로 비운다.**
 *     쇼츠에서 흔한 '위 영상 / 아래 큰 자막' 배치이고, 화면이 안 잘린다.
 */

import React from 'react';
import {
  AbsoluteFill, Audio, Sequence, staticFile, OffthreadVideo,
  useCurrentFrame, useVideoConfig, interpolate, spring,
} from 'remotion';
import { KineticWord, MINT, BG, FONT } from './motion';
import { S5_2_CUTS, S5_FPS } from './S5_2';

/* ══════════ 쇼츠 끝에 붙이는 롱폼 안내 카드 ══════════
   쇼츠는 "다 보여주는" 자리가 아니다. 궁금한 채로 끊고 롱폼으로 넘긴다. */

export const SHORT_OUTRO_FRAMES = Math.round(2.6 * 30);

export const ShortOutro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 14, stiffness: 190 } });
  const y = interpolate(p, [0, 1], [40, 0]);
  // 아래에서 위로 흐르는 얇은 민트 선 — 정지 화면이 아니라는 표시만
  const line = interpolate(frame, [0, 24], [0, 100], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ background: '#05100C', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{
        position: 'absolute', left: 0, right: 0, top: `${line}%`, height: 3,
        background: MINT, opacity: 0.35,
      }} />
      <div style={{
        transform: `translateY(${y}px)`, opacity: p, textAlign: 'center',
        fontFamily: FONT, fontWeight: 900, letterSpacing: '-1px',
      }}>
        <div style={{ fontSize: 62, color: '#fff', marginBottom: 26 }}>자세한 건</div>
        <div style={{
          fontSize: 92, color: '#05130E', background: MINT,
          padding: '10px 34px', borderRadius: 18, display: 'inline-block',
          boxShadow: `0 0 60px ${MINT}55`,
        }}>롱폼 영상에서 확인!</div>
      </div>
      <Audio src={staticFile('vsl/sfx/whoosh.mp3')} volume={0.3} />
    </AbsoluteFill>
  );
};

/* ══════════ ② 가로 녹화본을 세로 틀에 앉히는 쇼츠 ══════════ */

const BASE = 'vsl/s5/capcut_s5_2.mp4';

/** 잘라 쓸 구간 — S5-2에서 "이 두 영상이 같은 원본" 폭로 대목 (whisper 실측 시각) */
export const SHORT_S5_2_FROM = 19.36;
export const SHORT_S5_2_TO = 38.62;
export const SHORT_S5_2_FRAMES = Math.round((SHORT_S5_2_TO - SHORT_S5_2_FROM) * S5_FPS);

/** 이 구간에 걸리는 컷만 골라 0초 기준으로 다시 센다 */
const SEG = S5_2_CUTS
  .filter((c) => c.t >= SHORT_S5_2_FROM && c.t < SHORT_S5_2_TO)
  .map((c, i, arr) => ({
    ...c,
    rel: c.t - SHORT_S5_2_FROM,
    dur: (arr[i + 1]?.t ?? SHORT_S5_2_TO) - c.t,
  }));

/** 상단 배지 — 무슨 화면을 보고 있는지 한 줄로 못 박는다 */
const TopTag: React.FC<{ label: string }> = ({ label }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, 6], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, top: 116, textAlign: 'center', opacity: o,
    }}>
      <span style={{
        display: 'inline-block', padding: '12px 26px', borderRadius: 12,
        background: 'rgba(5,19,14,0.9)', border: `2px solid ${MINT}99`,
        fontFamily: FONT, fontWeight: 900, fontSize: 40, color: MINT,
      }}>{label}</span>
    </div>
  );
};

export const ShortS5_2: React.FC = () => (
  <AbsoluteFill style={{ background: BG }}>
    {/* 녹화본 — 세로 화면 위쪽에 통째로. 크롭하지 않는다(브라우저 UI가 뜻이다) */}
    <div style={{
      position: 'absolute', left: 0, right: 0, top: 300, height: 608, background: '#000',
    }}>
      <OffthreadVideo
        src={staticFile(BASE)}
        trimBefore={Math.round(SHORT_S5_2_FROM * S5_FPS)}
        trimAfter={Math.round(SHORT_S5_2_TO * S5_FPS)}
        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
      />
    </div>
    <TopTag label="레퍼런스 랭킹 · 실화면" />
    {SEG.map((cut, i) => (
      <Sequence key={i} from={Math.round(cut.rel * S5_FPS)}
        durationInFrames={Math.max(1, Math.round(cut.dur * S5_FPS))}>
        {/* 자막은 아래 빈 공간 한가운데. 영상 위에 안 겹친다.
            ★AbsoluteFill에 top만 주면 아래로 밀려 잘린다(실측) — 자리를 직접 잡는다 */}
        <div style={{
          position: 'absolute', left: 0, right: 0, top: 930, height: 640,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <KineticWord text={cut.text} center size={62} perWord={1.3} hi="underline" />
        </div>
        {(cut.sfx ?? []).map((s, k) => (
          <Sequence key={k} from={Math.round(s.at * S5_FPS)} layout="none">
            <Audio src={staticFile(`vsl/sfx/${s.n}`)} volume={s.v ?? 0.28} />
          </Sequence>
        ))}
      </Sequence>
    ))}
  </AbsoluteFill>
);
