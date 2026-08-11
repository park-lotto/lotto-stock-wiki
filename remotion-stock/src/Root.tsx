import './index.css';
import './load-font';
import React from 'react';
import { Composition } from 'remotion';
import { MyComposition } from './Composition';
import { LongformComposition } from './LongformComposition';
import { BannerComposition } from './BannerComposition';
// 숏템메이커 VSL(2026-07-30, T1) — 배경 화면녹화를 구간별 배속으로 재생하는 뼈대.
import { VslDemo, VSL_DEMO_FRAMES, VSL_FPS } from './vsl/VslDemo';
// S1 콜드오픈(2026-08-11) — 완성본 쇼츠 10개 고속 전환 + 키네틱 자막. TTS 입고 전 추정 타이밍.
import { S1ColdOpen, S1_FRAMES, S1_FPS } from './vsl/S1ColdOpen';
// S2 페인 씬(2026-08-11) — 탈색/붉은 경고 톤, 마지막 2컷만 민트 복귀.
import { S2Pain, S2_FRAMES, S2_FPS } from './vsl/S2Pain';
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
import { AG01_Timeline } from './agents/AG_S01_Hook_done';
import { AG_S02_Empathy } from './agents/AG_S02_Empathy_done';
import { AG_S03_Declaration } from './agents/AG_S03_Declaration_done';
import { AG_S04_1_Boss }    from './agents/AG_S04_1_Boss_done';
import { AG_S04_3_Supply }  from './agents/AG_S04_3_Supply_done';
import { AG_S04_4_Toppick } from './agents/AG_S04_4_Toppick_done';
import { AG_S04_5_Brief }   from './agents/AG_S04_5_Brief_done';
import { AG_S04_6_Deploy }  from './agents/AG_S04_6_Deploy_done';
import { AG_S04_7_Others }  from './agents/AG_S04_7_Others_done';
import { AG_S04_2_Collect as AG_S04_2_v2 } from './agents/AG_S04_2_Collect_v2_done';
import { AG_S05_Climax }   from './agents/AG_S05_Climax_done';
import { AG_S06_Awareness } from './agents/AG_S06_Awareness_done';
import { AG_S07_Tease }    from './agents/AG_S07_Tease_done';
import { AG_S08_CTA }      from './agents/AG_S08_CTA_done';
import { AG_Full, TOTAL_FRAMES } from './agents/AG_Full';
import { GB01_Hook } from './buildup/GB01_Hook';
import { GB02_Checklist } from './buildup/GB02_Checklist';
import { GB03_Compare } from './buildup/GB03_Compare';
import { GB03_5_RealBenefit } from './buildup/GB03_5_RealBenefit';
import { GB04_Telegram } from './buildup/GB04_Telegram';
import { GB05_StockBrain } from './buildup/GB05_StockBrain';
import { GB06_CTA } from './buildup/GB06_CTA';
import { GB_Full, GB_TOTAL_FRAMES } from './buildup/GB_Full';
import { GB_Thumbnail } from './buildup/GB_Thumbnail';
import { GB_Thumb_A } from './buildup/GB_Thumb_A';
import { GB_Thumb_B } from './buildup/GB_Thumb_B';
import { GB_Thumb_C } from './buildup/GB_Thumb_C';
import { GB_Thumb_D } from './buildup/GB_Thumb_D';
import { GB_Thumb_E } from './buildup/GB_Thumb_E';
import { SDUR } from './constants';
import { JH_Sample, JH_SAMPLE_FRAMES } from './news/JH_Sample';
import { LGcns_Scene, LGCNS_FRAMES } from './news/LGcns_Scene';
import {
  DocumentHighlightScene,
  DocPanScene,
} from './scenes/DocumentHighlightScene';
import { DocHighlight_Demo, DOC_DEMO_FRAMES } from './scenes/DocHighlight_Demo';
import { TechFeedScene, TECHFEED_DEMO_FRAMES } from './scenes/TechFeedScene';
import { FocusZoomScene, FOCUS_ZOOM_FRAMES } from './scenes/FocusZoomScene';
import { FocusZoomDemo, FOCUS_ZOOM_DEMO_FRAMES } from './scenes/FocusZoomDemo';
import { StockBrainIntro, STOCK_BRAIN_INTRO_FRAMES } from './signature/StockBrainIntro';
import { S01_Hook as Kakao_S01_Hook, S01_FRAMES } from './kakao/S01_Hook';
import { S02_PainPoint, S02_FRAMES } from './kakao/S02_PainPoint';
import { S05_ClaudeSetup, S05_FRAMES } from './kakao/S05_ClaudeSetup';
import { S07_PlayMCPConnect, S07_FRAMES } from './kakao/S07_PlayMCPConnect';
import { S01_Hook_AV, S01_AV_FRAMES } from './kakao/S01_Hook_AV';
import { S05_ClaudeSetup_AV, S05_AV_FRAMES } from './kakao/S05_ClaudeSetup_AV';
import { KK_Veo_S1, KK_VEO_S1_FRAMES } from './kakao/KK_Veo_S1';
import { KK_Veo_S2, KK_VEO_S2_FRAMES } from './kakao/KK_Veo_S2';
import { KK_Veo_S3, KK_VEO_S3_FRAMES } from './kakao/KK_Veo_S3';
import { KK_S1_Hooking, KK_S1_HOOKING_FRAMES } from './kakao/KK_S1_Hooking';
import { KK_S1_L30, KK_S1_L30_FRAMES } from './kakao/KK_S1_L30';
import { KK_S2_L30, KK_S2_L30_FRAMES } from './kakao/KK_S2_L30';
import { KK_S3_L30, KK_S3_L30_FRAMES } from './kakao/KK_S3_L30';
import { KK_S5_L30, KK_S5_L30_FRAMES } from './kakao/KK_S5_L30';
import { KK_S6_MCP, KK_S6_FRAMES } from './kakao/KK_S6_MCP';
import { KK_S5_PiP, KK_S5_PIP_FRAMES } from './kakao/KK_S5_PiP';
import { KK_S5_Screenshots, KK_S5_SCREENSHOTS_FRAMES } from './kakao/KK_S5_Screenshots';
import { NV_S01_Intro, NV_S01_FRAMES } from './nvidia/NV_S01_Intro';
import { KK_S5_Activation, KK_S5_ACTIVATION_FRAMES } from './kakao/KK_S5_Activation';
import { KK_S5_ClaudeLive, KK_S5_CLAUDELIVE_FRAMES } from './kakao/KK_S5_ClaudeLive';
import { KK_S3_ClaudeLive, KK_S3_CLAUDELIVE_FRAMES } from './kakao/KK_S3_ClaudeLive';
import { PostFX } from './components/PostFX';

// ── 카카오EP1 v2 (오푸스 전면 재작성) ──
import { KK_ChannelSting, KK_CHANNELSTING_FRAMES } from './kakao/KK_ChannelSting';
import { KK_EndSting, KK_ENDSTING_FRAMES } from './kakao/KK_EndSting';
import { KK_ColdOpen, KK_COLDOPEN_FRAMES } from './kakao/KK_ColdOpen';
import { KK_S2_PiP, KK_S2_PIP_FRAMES } from './kakao/KK_S2_PiP';
import { KK_S4_Roadmap, KK_S4_ROADMAP_FRAMES } from './kakao/KK_S4_Roadmap';
import { KK_S7_PiP, KK_S7_PIP_FRAMES } from './kakao/KK_S7_PiP';
import { KK_S8_PiP, KK_S8_PIP_FRAMES } from './kakao/KK_S8_PiP';
import { KK_S9_PiP, KK_S9_PIP_FRAMES } from './kakao/KK_S9_PiP';
import { KK_S10_PiP, KK_S10_PIP_FRAMES } from './kakao/KK_S10_PiP';
import { KK_S11_Apply, KK_S11_APPLY_FRAMES } from './kakao/KK_S11_Apply';
import { KK_Veo_Intro, KK_VEO_INTRO_FRAMES } from './kakao/KK_Veo_Intro';
import { KK_Veo_Outro, KK_VEO_OUTRO_FRAMES } from './kakao/KK_Veo_Outro';
import { KK_EP1_Full, KK_EP1_FULL_FRAMES } from './kakao/KK_EP1_Full';

// ── LIFE 3.0 디자인 샘플 3종 ──
import { KK_Sample_AI, KK_SAMPLE_AI_FRAMES } from './kakao/samples/KK_Sample_AI';
import { KK_Sample_Tut, KK_SAMPLE_TUT_FRAMES } from './kakao/samples/KK_Sample_Tut';
import { KK_Sample_Solo, KK_SAMPLE_SOLO_FRAMES } from './kakao/samples/KK_Sample_Solo';

// PostFX 래퍼 컴포넌트 — Composition component 에 직접 람다 못 쓰므로 별도 정의
const StockBrainIntroFX   = () => <PostFX><StockBrainIntro /></PostFX>;
const Kakao_S01_FX = () => <PostFX grain={0.06} vignette={0.50} light><Kakao_S01_Hook /></PostFX>;
const Kakao_S02_Dark_FX   = () => <PostFX><S02_PainPoint variant="dark"  /></PostFX>;
const Kakao_S02_Light_FX  = () => <PostFX grain={0.06} vignette={0.50} light><S02_PainPoint variant="light" /></PostFX>;
const Kakao_S05_FX = () => <PostFX><S05_ClaudeSetup /></PostFX>;
const Kakao_S07_FX = () => <PostFX><S07_PlayMCPConnect /></PostFX>;
// ── 아바타 영상 버전 래퍼 ──
const Kakao_S01_AV_FX = () => <S01_Hook_AV />;
const Kakao_S05_AV_FX = () => <S05_ClaudeSetup_AV />;
// ── Veo AI 아바타 씬 ──
const KK_Veo_S1_FX = () => <KK_Veo_S1 />;
const KK_Veo_S2_FX = () => <KK_Veo_S2 />;
const KK_Veo_S3_FX = () => <KK_Veo_S3 />;
// ── 후킹 스타일 씬 ──
const KK_S1_Hooking_FX = () => <KK_S1_Hooking />;
// ── LIFE 3.0 오버레이 씬 ──
const KK_S1_L30_FX = () => <KK_S1_L30 />;
const KK_S2_L30_FX = () => <KK_S2_L30 />;
const KK_S3_L30_FX = () => <KK_S3_L30 />;
const KK_S5_L30_FX = () => <KK_S5_L30 />;
const KK_S5_PiP_FX         = () => <KK_S5_PiP />;
const KK_S5_Screenshots_FX = () => <KK_S5_Screenshots />;
const NV_S01_FX = () => <NV_S01_Intro />;
const KK_S5_Activation_FX = () => <KK_S5_Activation />;
const KK_S5_ClaudeLive_FX = () => <KK_S5_ClaudeLive />;
const KK_S3_ClaudeLive_FX = () => <KK_S3_ClaudeLive />;
export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* ════════ LIFE 3.0 디자인 샘플 3종 (모드 A/B/C) ════════ */}
      <Composition id="KKEP1-SAMPLE-A-AI" component={KK_Sample_AI} durationInFrames={KK_SAMPLE_AI_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-SAMPLE-B-TUT" component={KK_Sample_Tut} durationInFrames={KK_SAMPLE_TUT_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-SAMPLE-C-SOLO" component={KK_Sample_Solo} durationInFrames={KK_SAMPLE_SOLO_FRAMES} fps={30} width={1920} height={1080} />

      {/* ════════ 카카오EP1 v2 — 전체 + 씬별 (오푸스 재작성) ════════ */}
      <Composition id="KKEP1-00-Full" component={KK_EP1_Full} durationInFrames={KK_EP1_FULL_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-Sting" component={KK_ChannelSting} durationInFrames={KK_CHANNELSTING_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-VeoIntro" component={KK_Veo_Intro} durationInFrames={KK_VEO_INTRO_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-ColdOpen" component={KK_ColdOpen} durationInFrames={KK_COLDOPEN_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S2" component={KK_S2_PiP} durationInFrames={KK_S2_PIP_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S3" component={KK_S3_L30} durationInFrames={KK_S3_L30_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S4" component={KK_S4_Roadmap} durationInFrames={KK_S4_ROADMAP_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S5" component={KK_S5_PiP} durationInFrames={KK_S5_PIP_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S6" component={KK_S6_MCP} durationInFrames={KK_S6_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S7" component={KK_S7_PiP} durationInFrames={KK_S7_PIP_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S8" component={KK_S8_PiP} durationInFrames={KK_S8_PIP_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S9" component={KK_S9_PiP} durationInFrames={KK_S9_PIP_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S10" component={KK_S10_PiP} durationInFrames={KK_S10_PIP_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-S11" component={KK_S11_Apply} durationInFrames={KK_S11_APPLY_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-VeoOutro" component={KK_Veo_Outro} durationInFrames={KK_VEO_OUTRO_FRAMES} fps={30} width={1920} height={1080} />
      <Composition id="KKEP1-EndSting" component={KK_EndSting} durationInFrames={KK_ENDSTING_FRAMES} fps={30} width={1920} height={1080} />

      {/* ── STOCK BRAIN 시그니처 인트로 (PostFX 적용) ── */}
      <Composition
        id="StockBrain-Intro"
        component={StockBrainIntroFX}
        durationInFrames={STOCK_BRAIN_INTRO_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── Veo AI 아바타 씬 S1~S3 ── */}
      <Composition
        id="Kakao-Veo-S1"
        component={KK_Veo_S1_FX}
        durationInFrames={KK_VEO_S1_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Kakao-Veo-S2"
        component={KK_Veo_S2_FX}
        durationInFrames={KK_VEO_S2_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="Kakao-Veo-S3"
        component={KK_Veo_S3_FX}
        durationInFrames={KK_VEO_S3_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── 후킹 스타일 S1 ── */}
      <Composition
        id="Kakao-S1-Hooking"
        component={KK_S1_Hooking_FX}
        durationInFrames={KK_S1_HOOKING_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── LIFE 3.0 오버레이 S1 (프레젠터 영상 + L30 그래픽) ── */}
      <Composition
        id="Kakao-S1-L30"
        component={KK_S1_L30_FX}
        durationInFrames={KK_S1_L30_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── LIFE 3.0 오버레이 S2 (페인포인트 씬 + L30 그래픽) ── */}
      <Composition
        id="Kakao-S2-L30"
        component={KK_S2_L30_FX}
        durationInFrames={KK_S2_L30_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── LIFE 3.0 오버레이 S3 (AI신화파괴 + 진짜이유) ── */}
      <Composition
        id="Kakao-S3-L30"
        component={KK_S3_L30_FX}
        durationInFrames={KK_S3_L30_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── LIFE 3.0 오버레이 S5 (클로드 설치 + 유료 플랜) ── */}
      <Composition
        id="Kakao-S5-L30"
        component={KK_S5_L30_FX}
        durationInFrames={KK_S5_L30_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── S5 PiP 레이아웃 (발표자 우측 9:16 + 좌측 화면 녹화) ── */}
      <Composition
        id="Kakao-S5-PiP"
        component={KK_S5_PiP_FX}
        durationInFrames={KK_S5_PIP_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── S5 스크린샷 버전 (실화면 캡쳐 + AI PiP 우하단 이동) ── */}
      <Composition
        id="Kakao-S5-Screenshots"
        component={KK_S5_Screenshots_FX}
        durationInFrames={KK_S5_SCREENSHOTS_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── S3 Claude Live — AI 신화파괴 + 진짜이유 ── */}
      <Composition
        id="KK-S3-ClaudeLive"
        component={KK_S3_ClaudeLive_FX}
        durationInFrames={KK_S3_CLAUDELIVE_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── S5 Claude Live — 클로드 CI/BI 역동·다채 테마 (신규) ── */}
      <Composition
        id="KK-S5-ClaudeLive"
        component={KK_S5_ClaudeLive_FX}
        durationInFrames={KK_S5_CLAUDELIVE_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── S5 Activation — Activation 디자인 테마 ── */}
      <Composition
        id="KK-S5-Activation"
        component={KK_S5_Activation_FX}
        durationInFrames={KK_S5_ACTIVATION_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── NVIDIA Scene01: 레퍼런스 프레임 기반 팟캐스트 하이라이트 ── */}
      <Composition
        id="NV-S01-Intro"
        component={NV_S01_FX}
        durationInFrames={NV_S01_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── S6 MCP 개념 설명 ── */}
      <Composition
        id="Kakao-S6-MCP"
        component={KK_S6_MCP}
        durationInFrames={KK_S6_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── 카카오클로드 S01 훅 (흰 배경, PostFX 라이트) ── */}
      <Composition
        id="Kakao-S01"
        component={Kakao_S01_FX}
        durationInFrames={S01_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── 카카오클로드 S02 페인포인트 — 다크 (PostFX 적용) ── */}
      <Composition
        id="Kakao-S02-Dark"
        component={Kakao_S02_Dark_FX}
        durationInFrames={S02_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── 카카오클로드 S02 페인포인트 — 라이트 (PostFX 적용) ── */}
      <Composition
        id="Kakao-S02-Light"
        component={Kakao_S02_Light_FX}
        durationInFrames={S02_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── 카카오클로드 S05 — Claude 설치 (PostFX 적용) ── */}
      <Composition
        id="Kakao-S05"
        component={Kakao_S05_FX}
        durationInFrames={S05_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* ── 카카오클로드 S07 — PlayMCP 연결 (PostFX 적용) ── */}
      <Composition
        id="Kakao-S07"
        component={Kakao_S07_FX}
        durationInFrames={S07_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ══ 아바타 영상 버전 (실제 아바타 MP4 + 화면녹화 합성) ══════════ */}
      {/* avatar_s01.mp4 준비 후 확인 */}
      <Composition
        id="Kakao-AV-S01"
        component={Kakao_S01_AV_FX}
        durationInFrames={S01_AV_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* avatar_s05.mp4 + screen_s05.mp4 준비 후 확인 */}
      <Composition
        id="Kakao-AV-S05"
        component={Kakao_S05_AV_FX}
        durationInFrames={S05_AV_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── TechFeed 데모 (배경 dim + 한국어 오버레이 + FocusCard + 줌인) ── */}
      <Composition
        id="TechFeed-Demo"
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        component={TechFeedScene as any}
        durationInFrames={TECHFEED_DEMO_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── FocusZoom 순수 Remotion 데모 (이미지 불필요, SpaceX 장면 재현) ── */}
      <Composition
        id="FocusZoom-SpaceX"
        component={FocusZoomDemo}
        durationInFrames={FOCUS_ZOOM_DEMO_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── FocusZoom 데모 (SpaceX: 한국어 텍스트 박스 강조 + 줌인) ── */}
      <Composition
        id="FocusZoom-Demo"
        component={() => (
          <FocusZoomScene
            imageSrc="images/spacex_demo.png"
            focusBox={{ top: 665, left: 222, width: 1476, height: 124 }}
            zoomScale={2.5}
            overlayDark={0.80}
            dimStart={0}
            zoomStart={38}
          />
        )}
        durationInFrames={FOCUS_ZOOM_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── DocHighlight 데모 (뉴스 헤드라인 팬+형광펜) ── */}
      <Composition
        id="DocHighlight-Demo"
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        component={DocHighlight_Demo as any}
        durationInFrames={DOC_DEMO_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── DocumentHighlight 단일 크롭 테스트 ── */}
      <Composition
        id="DocHighlight-Test"
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        component={DocumentHighlightScene as any}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          imageSrc: 'images/report_sample.png',
          crop: { top: 30, right: 5, bottom: 40, left: 5 },
          highlights: [
            { top: 48, left: 8, width: 58, height: 12, delay: 45, animDur: 18 },
          ],
          caption: '2Q26 OPM 13.2% — 컨센서스 대비 +2.1%p 상회',
          tag: { text: '삼성전기 실적발표', sub: '2026.06.13' },
        }}
      />

      {/* ── DocPanScene 멀티 세그먼트 팬 테스트 ── */}
      <Composition
        id="DocPan-Test"
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        component={DocPanScene as any}
        durationInFrames={270}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          imageSrc: 'images/report_sample.png',
          segments: [
            {
              startFrame: 0,
              endFrame: 120,
              crop: { top: 10, right: 5, bottom: 60, left: 5 },
              highlights: [{ top: 45, left: 5, width: 50, height: 14, delay: 45 }],
              caption: '수주 잔고 2.8조 — 역대 최대',
            },
            {
              startFrame: 120,
              endFrame: 270,
              crop: { top: 55, right: 5, bottom: 10, left: 5 },
              highlights: [{ top: 40, left: 10, width: 65, height: 12, delay: 135, color: '#FF6B35' }],
              caption: 'OPM 13.2% — 분기 최고치 경신',
            },
          ],
          tag: { text: '하나증권 리포트', sub: '2026.06.13' },
        }}
      />

      {/* 깐부회동 + LG차트 하이브리드 씬 */}
      <Composition
        id="LGcns-Hybrid"
        component={LGcns_Scene}
        durationInFrames={LGCNS_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* 젠슨황 방한 30초 샘플 */}
      <Composition
        id="Jensen-Korea-2026"
        component={JH_Sample}
        durationInFrames={JH_SAMPLE_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
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

      {/* ─── AI 직원 10명 영상 — 전체 합본 ─── */}
      <Composition id="AG-Full" component={AG_Full} durationInFrames={TOTAL_FRAMES} fps={30} width={1920} height={1080} />

      {/* ─── AI 직원 10명 영상 — 씬별 컴포지션 ─── */}
      {/* 씬1 훅 */}
      <Composition
        id="AG-S01-Hook-done"
        component={() => <AG01_Timeline mode="hook" />}
        durationInFrames={630}
        fps={30}
        width={1920}
        height={1080}
      />
      {/* 씬2~3 */}
      <Composition id="AG-S02-Empathy-done"    component={AG_S02_Empathy}    durationInFrames={1009} fps={30} width={1920} height={1080} />
      <Composition id="AG-S03-Declaration-done" component={AG_S03_Declaration} durationInFrames={562}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-1-Boss-done"    component={AG_S04_1_Boss}    durationInFrames={442}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-2-Collect-done" component={AG_S04_2_v2}      durationInFrames={1720} fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-3-Supply-done"  component={AG_S04_3_Supply}  durationInFrames={755}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-4-Toppick-done" component={AG_S04_4_Toppick} durationInFrames={580}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-5-Brief-done"   component={AG_S04_5_Brief}   durationInFrames={667}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-6-Deploy-done"  component={AG_S04_6_Deploy}  durationInFrames={617}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S04-7-Others-done"  component={AG_S04_7_Others}  durationInFrames={716}  fps={30} width={1920} height={1080} />
      <Composition id="AG-S05-Climax-done"    component={AG_S05_Climax}    durationInFrames={682} fps={30} width={1920} height={1080} />
      <Composition id="AG-S06-Awareness-done" component={AG_S06_Awareness} durationInFrames={570} fps={30} width={1920} height={1080} />
      <Composition id="AG-S07-Tease-done"     component={AG_S07_Tease}     durationInFrames={548} fps={30} width={1920} height={1080} />
      <Composition id="AG-S08-CTA-done"       component={AG_S08_CTA}       durationInFrames={562} fps={30} width={1920} height={1080} />


      {/* ─── 국민성장펀드 썸네일 (1280×720 정적) ─── */}
      <Composition id="GB-Thumbnail"   component={GB_Thumbnail} durationInFrames={1} fps={30} width={1280} height={720} />
      <Composition id="GB-Thumb-A"     component={GB_Thumb_A}   durationInFrames={1} fps={30} width={1280} height={720} />
      <Composition id="GB-Thumb-B"     component={GB_Thumb_B}   durationInFrames={1} fps={30} width={1280} height={720} />
      <Composition id="GB-Thumb-C"     component={GB_Thumb_C}   durationInFrames={1} fps={30} width={1280} height={720} />
      <Composition id="GB-Thumb-D"     component={GB_Thumb_D}   durationInFrames={1} fps={30} width={1280} height={720} />
      <Composition id="GB-Thumb-E"     component={GB_Thumb_E}   durationInFrames={1} fps={30} width={1280} height={720} />

      {/* ─── 국민성장펀드 빌드업 — 전체 합본 ─── */}
      <Composition
        id="GB-Full"
        component={GB_Full}
        durationInFrames={GB_TOTAL_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ─── 국민성장펀드 빌드업 영상 — 씬1~3 ─── */}
      <Composition
        id="GB01-Hook-done"
        component={GB01_Hook}
        durationInFrames={806}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB02-Checklist-pending"
        component={GB02_Checklist}
        durationInFrames={1830}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB03-Compare-done"
        component={GB03_Compare}
        durationInFrames={1616}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB03-5-RealBenefit-done"
        component={GB03_5_RealBenefit}
        durationInFrames={5529}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB04-Telegram-pending"
        component={GB04_Telegram}
        durationInFrames={1500}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB05-StockBrain-done"
        component={GB05_StockBrain}
        durationInFrames={1245}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="GB06-CTA-done"
        component={GB06_CTA}
        durationInFrames={600}
        fps={30}
        width={1920}
        height={1080}
      />

      {/* ── 숏템메이커 VSL (2026-07-30) ──────────────────────────────
          T1 검증용. 테스트 클립엔 프레임 번호가 찍혀 있어 배속이 실제로
          걸렸는지 눈으로 보인다(숫자가 뛰는 속도가 구간마다 달라짐).
          실촬영 후에는 segments를 anchors.json에서 자동 생성한다(T3). */}
      <Composition
        id="VSL-S1-ColdOpen"
        component={S1ColdOpen}
        durationInFrames={S1_FRAMES}
        fps={S1_FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="VSL-S2-Pain"
        component={S2Pain}
        durationInFrames={S2_FRAMES}
        fps={S2_FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="VSL-Demo-T1"
        component={VslDemo}
        durationInFrames={VSL_DEMO_FRAMES}
        fps={VSL_FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};
