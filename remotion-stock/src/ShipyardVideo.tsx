/**
 * ShipyardVideo.tsx — 조선 섹터 브리핑 영상 (이미지 활용 데모)
 * 3장면 × 6초 = 18초
 *
 * S1: ImgHeroScene  — 컨테이너선 배경 "도크가 없다 / 삼각축 호황"
 * S2: ImgSplitScene — LNG탱커 왼쪽 + 수주잔고 데이터 오른쪽
 * S3: ImgSplitScene — 조선소 크레인 왼쪽 + 핵심 종목 오른쪽
 */
import React from 'react';
import { Series } from 'remotion';
import { SDUR } from './constants';
import { FadeWrapper } from './components/FadeWrapper';
import { ImgHeroScene, ImgSplitScene } from './scenes/ImgScene';

export const ShipyardVideo: React.FC = () => (
  <Series>

    {/* S1 — 히어로: 컨테이너선 전체 배경 + 켄번스 줌 */}
    <Series.Sequence durationInFrames={SDUR}>
      <FadeWrapper>
        <ImgHeroScene
          img="images/ship_hero.jpg"
          label="조선 섹터 · 2026"
          line1="도크가 없다"
          line2="삼각축 호황"
          caption="수주잔고 89조 · 신조선가 184pt · MASGA · AI 전력"
        />
      </FadeWrapper>
    </Series.Sequence>

    {/* S2 — 스플릿: LNG탱커 이미지 + 수주/선가 데이터 */}
    <Series.Sequence durationInFrames={SDUR}>
      <FadeWrapper>
        <ImgSplitScene
          img="images/lng_tanker.jpg"
          imgPos="center 40%"
          label="LNG 톤마일 폭증"
          title={"중동→미주\n거리 1.5~2.5배"}
          points={[
            "호르무즈 봉쇄 → 가용 선대 급감",
            "미국 LNG FID 연속 → 추가 수주 20척+",
            "중고선가 208pt > 신조 184pt 역전",
            "2029년 수요 131척 vs 가용 60~65척",
          ]}
          caption="선가가 오를 수밖에 없는 구조적 공급 부족"
        />
      </FadeWrapper>
    </Series.Sequence>

    {/* S3 — 스플릿: 조선소 크레인 + 핵심 종목 */}
    <Series.Sequence durationInFrames={SDUR}>
      <FadeWrapper>
        <ImgSplitScene
          img="images/ship_hero.jpg"
          imgPos="center 70%"
          label="탑픽 종목"
          title={"수급 빈집 +\n삼각축 교집합"}
          points={[
            "HD현대중공업 — TP 870K · 힘쎈엔진",
            "대한조선 — 마진 27% · PER 9.8배",
            "HD현대마린솔루션 — MRO·AI 구조성장",
            "한화오션 — Austal USA · MASGA 직결",
          ]}
          caption="빈집 + 삼각축 교집합 종목이 탑픽 조건 충족"
        />
      </FadeWrapper>
    </Series.Sequence>

  </Series>
);
