/**
 * Triptych — S1 콜드오픈 배경. 완성본 쇼츠 3개를 16:9 화면에 나란히.
 *
 * 왜 이 형태인가: S1의 주장은 "이 쇼츠들, 제가 손으로 만든 게 아닙니다"다. 말보다 **결과물
 * 세 개가 동시에 돌아가는 화면**이 증거가 된다. 한 개면 우연으로 보이고, 세 개면 시스템으로 보인다.
 *
 * 재료: 제작소가 실제로 뽑은 완성본(서버 mix_jobs/*/final.mp4). 촬영이 필요 없다.
 *   ★git에 안 넣는다(.gitignore: remotion-stock/public/**\/*.mp4). 다시 받으려면:
 *     scp ubuntu@<서버>:/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs/<job>/final.mp4 \
 *         public/vsl/reel_<job>.mp4
 *
 * 레이아웃: 세로 9:16을 1080 높이에 맞추면 607px → 3개 = 1821px, 1920 안에 들어간다.
 * 나레이션(S1은 61초)이 릴스(15~18초)보다 길어서 <Loop>로 반복한다. 시작점을 서로
 * 어긋나게 줘(stagger) 세 개가 똑같이 움직이는 티를 없앤다.
 */

import React from 'react';
import { AbsoluteFill, Loop, OffthreadVideo, staticFile } from 'remotion';

export type ReelSpec = {
  /** public/ 기준 경로 */
  src: string;
  /** 이 클립의 길이(초) — Loop 주기 계산에 쓴다 */
  durationSec: number;
  /** 시작 오프셋(초). 세 개가 동시에 같은 장면을 보여주지 않게 어긋낸다 */
  offsetSec?: number;
};

/** 2026-07-30 서버에서 받은 실제 완성본 3개(ffprobe 실측 길이) */
export const S1_REELS: ReelSpec[] = [
  { src: 'vsl/reel_e9e74aea275f.mp4', durationSec: 18.36, offsetSec: 0 },
  { src: 'vsl/reel_125c74e5abff.mp4', durationSec: 18.03, offsetSec: 4 },
  { src: 'vsl/reel_9d03ee741492.mp4', durationSec: 14.7, offsetSec: 8 },
];

const GAP = 24;
const REEL_W = 607;   // 1080 × 9/16
const REEL_H = 1080;

const ReelPane: React.FC<{ reel: ReelSpec; fps: number }> = ({ reel, fps }) => {
  // Loop 주기는 오프셋을 뺀 나머지 — 오프셋을 넘겨 재생하면 검은 화면이 나온다.
  const usable = Math.max(1, reel.durationSec - (reel.offsetSec ?? 0));
  const loopFrames = Math.max(1, Math.floor(usable * fps));
  return (
    <div
      style={{
        width: REEL_W, height: REEL_H, overflow: 'hidden',
        borderRadius: 14, background: '#000',
        boxShadow: '0 18px 48px rgba(0,0,0,0.55)',
      }}
    >
      <Loop durationInFrames={loopFrames}>
        <OffthreadVideo
          src={staticFile(reel.src)}
          trimBefore={Math.round((reel.offsetSec ?? 0) * fps)}
          // 배경이므로 소리는 죽인다 — 오디오는 나레이션 트랙이 기준이다.
          volume={0}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </Loop>
    </div>
  );
};

export const Triptych: React.FC<{
  reels?: ReelSpec[];
  fps: number;
  /** 중앙 자막을 얹을 때 화면을 눌러준다. 훅 구간 기본 0.5 */
  dim?: number;
}> = ({ reels = S1_REELS, fps, dim = 0 }) => (
  <AbsoluteFill style={{ background: '#08110E' }}>
    <AbsoluteFill
      style={{
        flexDirection: 'row', alignItems: 'center',
        justifyContent: 'center', gap: GAP,
      }}
    >
      {reels.map((r) => (
        <ReelPane key={r.src} reel={r} fps={fps} />
      ))}
    </AbsoluteFill>
    {dim > 0 ? <AbsoluteFill style={{ background: `rgba(0,0,0,${dim})` }} /> : null}
  </AbsoluteFill>
);
