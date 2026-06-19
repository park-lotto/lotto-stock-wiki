/**
 * [샘플 B] 튜토리얼 부분 — 밝은 브라우저 프레임 + 무대 여백 그래픽
 * ⚠️ 화면녹화 위에 그래픽 금지 / 화면 어둡게 금지.
 * 녹화는 밝은 프레임에 담고, 그래픽은 전부 화면 바깥 여백에.
 */

import React from 'react';
import { useCurrentFrame } from 'remotion';
import { Stage, Kicker, Watermark, StepBar, BrowserFrame, MarginCallout, LifeSubBar, LIME } from '../life';

export const KK_SAMPLE_TUT_FRAMES = 240;

const SUBS = [
  { from: 0, to: 120, text: '설치 완료 후 앱을 실행하면, 좌측 상단에 코워크 탭이 보입니다.', accent: '코워크 탭' },
  { from: 120, to: 240, text: '여기예요. 설치는 성공적으로 됐습니다.', accent: '성공' },
];

export const KK_Sample_Tut: React.FC = () => {
  const f = useCurrentFrame();

  return (
    <Stage>
      <Kicker ch="STEP 05" title="CLAUDE SETUP" f={f} />

      {/* 상단 큰 STEP 바 */}
      <StepBar step={5} total={5} label="코워크 탭 확인" f={f} accent={LIME} />

      {/* 밝은 브라우저 프레임 (화면녹화, dim 0) */}
      <BrowserFrame src="kakao/ep1/s05_bg.mp4" scale={0.74} top={150} accent={LIME} />

      {/* 여백 콜아웃 — 화면 바깥에서 가리킴 */}
      <MarginCallout text="좌측 상단 '코워크'" side="left" top={250} f={f} at={30} accent="#FF4455" />

      <LifeSubBar f={f} subs={SUBS} />
      <Watermark />
    </Stage>
  );
};
