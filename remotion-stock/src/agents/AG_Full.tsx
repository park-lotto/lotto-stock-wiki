// AG_Full — 에이전트직원 영상 전체 (씬1~씬8 연결)
// 총 10,060프레임 / 약 5분 35초

import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { AG01_Timeline }    from './AG_S01_Hook_done';
import { AG_S02_Empathy }   from './AG_S02_Empathy_done';
import { AG_S03_Declaration } from './AG_S03_Declaration_done';
import { AG_S04_1_Boss }    from './AG_S04_1_Boss_done';
import { AG_S04_2_Collect as AG_S04_2_v2 } from './AG_S04_2_Collect_v2_done';
import { AG_S04_3_Supply }  from './AG_S04_3_Supply_done';
import { AG_S04_4_Toppick } from './AG_S04_4_Toppick_done';
import { AG_S04_5_Brief }   from './AG_S04_5_Brief_done';
import { AG_S04_6_Deploy }  from './AG_S04_6_Deploy_done';
import { AG_S04_7_Others }  from './AG_S04_7_Others_done';
import { AG_S05_Climax }    from './AG_S05_Climax_done';
import { AG_S06_Awareness } from './AG_S06_Awareness_done';
import { AG_S07_Tease }     from './AG_S07_Tease_done';
import { AG_S08_CTA }       from './AG_S08_CTA_done';

const D = {
  s01:  630,
  s02: 1009,
  s03:  562,
  s041: 442,
  s042: 1720,
  s043: 755,
  s044: 580,
  s045: 667,
  s046: 617,
  s047: 716,
  s05:  682,
  s06:  570,
  s07:  548,
  s08:  562,
};

// 누적 오프셋
const O = (() => {
  const keys = Object.keys(D) as (keyof typeof D)[];
  let acc = 0;
  const out: Partial<Record<keyof typeof D, number>> = {};
  for (const k of keys) { out[k] = acc; acc += D[k]; }
  return out as Record<keyof typeof D, number>;
})();

export const TOTAL_FRAMES = Object.values(D).reduce((a, b) => a + b, 0); // 10,060

export const AG_Full: React.FC = () => (
  <AbsoluteFill style={{ background: '#080c14' }}>
    <Sequence from={O.s01}  durationInFrames={D.s01}><AG01_Timeline mode="hook" /></Sequence>
    <Sequence from={O.s02}  durationInFrames={D.s02}><AG_S02_Empathy /></Sequence>
    <Sequence from={O.s03}  durationInFrames={D.s03}><AG_S03_Declaration /></Sequence>
    <Sequence from={O.s041} durationInFrames={D.s041}><AG_S04_1_Boss /></Sequence>
    <Sequence from={O.s042} durationInFrames={D.s042}><AG_S04_2_v2 /></Sequence>
    <Sequence from={O.s043} durationInFrames={D.s043}><AG_S04_3_Supply /></Sequence>
    <Sequence from={O.s044} durationInFrames={D.s044}><AG_S04_4_Toppick /></Sequence>
    <Sequence from={O.s045} durationInFrames={D.s045}><AG_S04_5_Brief /></Sequence>
    <Sequence from={O.s046} durationInFrames={D.s046}><AG_S04_6_Deploy /></Sequence>
    <Sequence from={O.s047} durationInFrames={D.s047}><AG_S04_7_Others /></Sequence>
    <Sequence from={O.s05}  durationInFrames={D.s05}><AG_S05_Climax /></Sequence>
    <Sequence from={O.s06}  durationInFrames={D.s06}><AG_S06_Awareness /></Sequence>
    <Sequence from={O.s07}  durationInFrames={D.s07}><AG_S07_Tease /></Sequence>
    <Sequence from={O.s08}  durationInFrames={D.s08}><AG_S08_CTA /></Sequence>
  </AbsoluteFill>
);
