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
import { DakkakA_Dial } from './dakkak/DakkakA_Dial';
import { DakkakB_UICollage } from './dakkak/DakkakB_UICollage';
import { DakkakC_Pictogram } from './dakkak/DakkakC_Pictogram';
import { DakkakD_DataFlow } from './dakkak/DakkakD_DataFlow';
import { B1_Telegram } from './dakkak/B1_Telegram';
import { B2_Claude } from './dakkak/B2_Claude';
import { B3_Wiki } from './dakkak/B3_Wiki';
import { B4_Dashboard } from './dakkak/B4_Dashboard';
import { S01_Hook } from './dakkak/S01_Hook';
import { S02_Chaos } from './dakkak/S02_Chaos';
import { AG01_Timeline } from './agents/AG01_Timeline';
import { AG02_Agents } from './agents/AG02_Agents';
import { AG03_Awareness } from './agents/AG03_Awareness';
import { AG04_Tease } from './agents/AG04_Tease';
import { AG05_CTA } from './agents/AG05_CTA';
import { AG06_Delivery } from './agents/AG06_Delivery';
import { AG_S02_Empathy } from './agents/AG_S02_Empathy';
import { AG_S03_Declaration } from './agents/AG_S03_Declaration';
import { AG_S04_1_Boss }    from './agents/AG_S04_1_Boss';
import { AG_S04_2_Collect } from './agents/AG_S04_2_Collect';
import { AG_S04_3_Supply }  from './agents/AG_S04_3_Supply';
import { AG_S04_4_Toppick } from './agents/AG_S04_4_Toppick';
import { AG_S04_5_Brief }   from './agents/AG_S04_5_Brief';
import { AG_S04_6_Deploy }  from './agents/AG_S04_6_Deploy';
import { AG_S04_7_Others }  from './agents/AG_S04_7_Others';
import { GB01_Hook } from './buildup/GB01_Hook';
import { GB02_Checklist } from './buildup/GB02_Checklist';
import { GB03_Compare } from './buildup/GB03_Compare';
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

      {/* ─── "딸깍" 2강 — 4가지 시각 방향 샘플 (각 8초/240프레임) ─── */}
      <Composition
        id="DakkakA-Dial"
        component={DakkakA_Dial}
        durationInFrames={240}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="DakkakB-UICollage"
        component={DakkakB_UICollage}
        durationInFrames={240}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="DakkakC-Pictogram"
        component={DakkakC_Pictogram}
        durationInFrames={240}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="DakkakD-DataFlow"
        component={DakkakD_DataFlow}
        durationInFrames={240}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ─── B 진화 버전 — UI 콜라주 사실적 4컷 (각 12초/360프레임) ─── */}
      <Composition
        id="B1-Telegram"
        component={B1_Telegram}
        durationInFrames={360}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="B2-Claude"
        component={B2_Claude}
        durationInFrames={360}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="B3-Wiki"
        component={B3_Wiki}
        durationInFrames={360}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="B4-Dashboard"
        component={B4_Dashboard}
        durationInFrames={360}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ─── 딸깍 자동화 시스템 영상 — 씬별 컴포지션 ─── */}
      <Composition
        id="S01-Hook"
        component={S01_Hook}
        durationInFrames={600}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="S02-Chaos"
        component={S02_Chaos}
        durationInFrames={1350}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ─── AI 직원 10명 영상 — 씬별 컴포지션 ─── */}
      <Composition
        id="AG01-Timeline-Hook"
        component={() => <AG01_Timeline mode="hook" />}
        durationInFrames={630}  // 씬1 수정 녹음 19.98초 + 여백 1초
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG01-Timeline-Climax"
        component={() => <AG01_Timeline mode="climax" />}
        durationInFrames={750}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG02-Agents"
        component={AG02_Agents}
        durationInFrames={600}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG03-Awareness"
        component={AG03_Awareness}
        durationInFrames={1200}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG04-Tease"
        component={AG04_Tease}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG05-CTA"
        component={AG05_CTA}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG06-Delivery"
        component={AG06_Delivery}
        durationInFrames={750}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG-S02-Empathy"
        component={AG_S02_Empathy}
        durationInFrames={1009}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="AG-S03-Declaration"
        component={AG_S03_Declaration}
        durationInFrames={562}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition id="AG-S04-1-Boss"    component={AG_S04_1_Boss}    durationInFrames={442}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-2-Collect" component={AG_S04_2_Collect} durationInFrames={1690} fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-3-Supply"  component={AG_S04_3_Supply}  durationInFrames={755}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-4-Toppick" component={AG_S04_4_Toppick} durationInFrames={580}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-5-Brief"   component={AG_S04_5_Brief}   durationInFrames={667}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-6-Deploy"  component={AG_S04_6_Deploy}  durationInFrames={617}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-7-Others"  component={AG_S04_7_Others}  durationInFrames={716}  fps={30} width={1920} height={1080} />

      {/* ─── 국민성장펀드 빌드업 영상 — 씬1~3 ─── */}
      <Composition
        id="GB01-Hook"
        component={GB01_Hook}
        durationInFrames={569}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB02-Checklist"
        component={GB02_Checklist}
        durationInFrames={463}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB03-Compare"
        component={GB03_Compare}
        durationInFrames={2700}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
