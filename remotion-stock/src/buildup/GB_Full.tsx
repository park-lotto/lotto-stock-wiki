// GB_Full — 국민성장펀드 빌드업 영상 전체 (씬1~씬6 연결)
// 총 13,126프레임 / 약 7분 17초

import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { GB01_Hook }           from './GB01_Hook';
import { GB02_Checklist }      from './GB02_Checklist';
import { GB03_Compare }        from './GB03_Compare';
import { GB03_5_RealBenefit }  from './GB03_5_RealBenefit';
import { GB04_Telegram }       from './GB04_Telegram';
import { GB05_StockBrain }     from './GB05_StockBrain';
import { GB06_CTA }            from './GB06_CTA';

const D = {
  gb01:  806,
  gb02: 1830,
  gb03: 1616,
  gb035: 5529,
  gb04: 1500,
  gb05: 1245,
  gb06:  600,
};

const O = (() => {
  const keys = Object.keys(D) as (keyof typeof D)[];
  let acc = 0;
  const out: Partial<Record<keyof typeof D, number>> = {};
  for (const k of keys) { out[k] = acc; acc += D[k]; }
  return out as Record<keyof typeof D, number>;
})();

export const GB_TOTAL_FRAMES = Object.values(D).reduce((a, b) => a + b, 0); // 13,126

export const GB_Full: React.FC = () => (
  <AbsoluteFill style={{ background: '#000000' }}>
    <Sequence from={O.gb01}  durationInFrames={D.gb01}><GB01_Hook /></Sequence>
    <Sequence from={O.gb02}  durationInFrames={D.gb02}><GB02_Checklist /></Sequence>
    <Sequence from={O.gb03}  durationInFrames={D.gb03}><GB03_Compare /></Sequence>
    <Sequence from={O.gb035} durationInFrames={D.gb035}><GB03_5_RealBenefit /></Sequence>
    <Sequence from={O.gb04}  durationInFrames={D.gb04}><GB04_Telegram /></Sequence>
    <Sequence from={O.gb05}  durationInFrames={D.gb05}><GB05_StockBrain /></Sequence>
    <Sequence from={O.gb06}  durationInFrames={D.gb06}><GB06_CTA /></Sequence>
  </AbsoluteFill>
);
