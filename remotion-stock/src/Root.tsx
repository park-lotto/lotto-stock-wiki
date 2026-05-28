import './index.css';
import './load-font';
import React from 'react';
import { Composition } from 'remotion';
import { MyComposition } from './Composition';
import { LongformComposition } from './LongformComposition';
import { BannerComposition } from './BannerComposition';
import { VIDEO } from './theme';
import { AIStockVideo } from './AIStockVideo';
import { BuyHighVideo } from './BuyHighVideo';
import { LeadingStockVideo } from './LeadingStockVideo';
import { DataDetectiveVideo, DATA_DETECTIVE_FRAMES } from './DataDetectiveVideo';
import { KosdaqPolicyVideo, KOSDAQ_POLICY_FRAMES } from './KosdaqPolicyVideo';
import { LoseReasonVideo, LOSE_REASON_FRAMES } from './LoseReasonVideo';
import { ShipyardVideo } from './ShipyardVideo';
import { ChartScene } from './scenes/ChartScene';
import { SDUR } from './constants';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 쇼츠 포맷 (9:16) */}
      <Composition
        id="StockShorts"
        component={MyComposition}
        durationInFrames={VIDEO.duration}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />

      {/* 롱폼 포맷 (16:9) — 5초 훅 + 34장면 × 540프레임 = 10분 17초 */}
      <Composition
        id="LongformSample"
        component={LongformComposition}
        durationInFrames={18510}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 유튜브 채널 배너 — 2048×1152 */}
      <Composition
        id="BannerImage"
        component={BannerComposition}
        durationInFrames={1}
        fps={30}
        width={2048}
        height={1152}
      />

      {/* AI 샘플 영상 60초 — 10장면 × 6초 (v2 가이드 적용) */}
      <Composition
        id="AIStockVideo"
        component={AIStockVideo}
        durationInFrames={SDUR * 10}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 고점 매수 영상 60초 — "내가 사면 늘 고점에서 물리는 이유" */}
      <Composition
        id="BuyHighVideo"
        component={BuyHighVideo}
        durationInFrames={SDUR * 10}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 주도주 영상 60초 — "왜 주도주를 사야하는가?" */}
      <Composition
        id="LeadingStockVideo"
        component={LeadingStockVideo}
        durationInFrames={SDUR * 10}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 데이터 탐정 — 28장면 × 12초 = 5분 36초 */}
      <Composition
        id="DataDetectiveVideo"
        component={DataDetectiveVideo}
        durationInFrames={DATA_DETECTIVE_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 코스닥 대변혁 — 28장면 × 12초 = 5분 36초 */}
      <Composition
        id="KosdaqPolicyVideo"
        component={KosdaqPolicyVideo}
        durationInFrames={KOSDAQ_POLICY_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 개미가 지는 구조 — 28장면 × 12초 = 5분 36초 */}
      <Composition
        id="LoseReasonVideo"
        component={LoseReasonVideo}
        durationInFrames={LOSE_REASON_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* 차트 분석 씬 — KODEX 조선 ETF (12초) */}
      <Composition
        id="ChartScene"
        component={ChartScene}
        durationInFrames={360}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 조선 섹터 브리핑 — 이미지 활용 데모 (3장면 × 6초) */}
      <Composition
        id="ShipyardVideo"
        component={ShipyardVideo}
        durationInFrames={SDUR * 3}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
