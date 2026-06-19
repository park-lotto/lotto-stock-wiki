/**
 * KK_EP1_Full — 카카오EP1 전체 타임라인 (마스터)
 *
 * 구조: 스팅 → Veo인트로 → 스팅 → [콜드오픈+S2~S11] → 스팅 → Veo아웃트로 → 엔드스팅
 * 영상배경 씬(S2·S3·S5~S10)은 에셋 도착 전 플레이스홀더로 표시됨.
 */

import React from 'react';
import { Series } from 'remotion';

import { KK_ChannelSting, KK_CHANNELSTING_FRAMES } from './KK_ChannelSting';
import { KK_Veo_Intro, KK_VEO_INTRO_FRAMES } from './KK_Veo_Intro';
import { KK_ColdOpen, KK_COLDOPEN_FRAMES } from './KK_ColdOpen';
import { KK_S2_PiP, KK_S2_PIP_FRAMES } from './KK_S2_PiP';
import { KK_S3_L30, KK_S3_L30_FRAMES } from './KK_S3_L30';
import { KK_S4_Roadmap, KK_S4_ROADMAP_FRAMES } from './KK_S4_Roadmap';
import { KK_S5_PiP, KK_S5_PIP_FRAMES } from './KK_S5_PiP';
import { KK_S6_MCP, KK_S6_FRAMES } from './KK_S6_MCP';
import { KK_S7_PiP, KK_S7_PIP_FRAMES } from './KK_S7_PiP';
import { KK_S8_PiP, KK_S8_PIP_FRAMES } from './KK_S8_PiP';
import { KK_S9_PiP, KK_S9_PIP_FRAMES } from './KK_S9_PiP';
import { KK_S10_PiP, KK_S10_PIP_FRAMES } from './KK_S10_PiP';
import { KK_S11_Apply, KK_S11_APPLY_FRAMES } from './KK_S11_Apply';
import { KK_Veo_Outro, KK_VEO_OUTRO_FRAMES } from './KK_Veo_Outro';
import { KK_EndSting, KK_ENDSTING_FRAMES } from './KK_EndSting';

export const KK_EP1_FULL_FRAMES =
  KK_CHANNELSTING_FRAMES +
  KK_VEO_INTRO_FRAMES +
  KK_CHANNELSTING_FRAMES +
  KK_COLDOPEN_FRAMES +
  KK_S2_PIP_FRAMES +
  KK_S3_L30_FRAMES +
  KK_S4_ROADMAP_FRAMES +
  KK_S5_PIP_FRAMES +
  KK_S6_FRAMES +
  KK_S7_PIP_FRAMES +
  KK_S8_PIP_FRAMES +
  KK_S9_PIP_FRAMES +
  KK_S10_PIP_FRAMES +
  KK_S11_APPLY_FRAMES +
  KK_CHANNELSTING_FRAMES +
  KK_VEO_OUTRO_FRAMES +
  KK_ENDSTING_FRAMES;

export const KK_EP1_Full: React.FC = () => (
  <Series>
    <Series.Sequence durationInFrames={KK_CHANNELSTING_FRAMES}><KK_ChannelSting /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_VEO_INTRO_FRAMES}><KK_Veo_Intro /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_CHANNELSTING_FRAMES}><KK_ChannelSting /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_COLDOPEN_FRAMES}><KK_ColdOpen /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S2_PIP_FRAMES}><KK_S2_PiP /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S3_L30_FRAMES}><KK_S3_L30 /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S4_ROADMAP_FRAMES}><KK_S4_Roadmap /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S5_PIP_FRAMES}><KK_S5_PiP /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S6_FRAMES}><KK_S6_MCP /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S7_PIP_FRAMES}><KK_S7_PiP /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S8_PIP_FRAMES}><KK_S8_PiP /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S9_PIP_FRAMES}><KK_S9_PiP /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S10_PIP_FRAMES}><KK_S10_PiP /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_S11_APPLY_FRAMES}><KK_S11_Apply /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_CHANNELSTING_FRAMES}><KK_ChannelSting /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_VEO_OUTRO_FRAMES}><KK_Veo_Outro /></Series.Sequence>
    <Series.Sequence durationInFrames={KK_ENDSTING_FRAMES}><KK_EndSting /></Series.Sequence>
  </Series>
);
