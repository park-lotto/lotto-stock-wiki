/**
 * JH_Sample.tsx — 젠슨황 방한 30초 샘플
 * 이미지: public/images/jh/gen_s01~05.jpeg (Gemini 생성)
 */

import React from 'react';
import { AbsoluteFill, Series, useCurrentFrame, interpolate, Easing } from 'remotion';
import { ImgHeroScene, ImgSplitScene } from '../scenes/ImgScene';
import { C, FONT } from '../constants';

const SDUR = 180; // 6초

const SubBar: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [10, 28], [0, 1], { extrapolateRight: 'clamp' });
  const y  = interpolate(f, [10, 28], [12, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0, height: 90,
      background: 'linear-gradient(to top, rgba(0,0,0,0.9) 0%, transparent 100%)',
      display: 'flex', alignItems: 'center', paddingInline: 80,
      opacity: op, transform: `translateY(${y}px)`,
    }}>
      <div style={{
        borderLeft: `4px solid ${C.main}`, paddingLeft: 18,
        color: C.textPrimary, fontSize: 32, fontWeight: 700,
        fontFamily: FONT, lineHeight: 1.5,
        textShadow: '0 2px 8px rgba(0,0,0,0.9)',
      }}>
        {text}
      </div>
    </div>
  );
};

export const JH_Sample: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg, fontFamily: FONT }}>
    <Series>

      {/* 씬1 — 젠슨황 무대: 오프닝 */}
      <Series.Sequence durationInFrames={SDUR}>
        <AbsoluteFill>
          <ImgHeroScene
            img="images/jh/gen_s01.jpeg"
            label="⚡ 2026 방한"
            line1="젠슨황"
            line2="다시 한국"
            caption="GTC 타이베이 마치고 곧장 한국행 — 9개월 만"
          />
          <SubBar text="젠슨황이 다시 한국에 옵니다. 9개월 만입니다." />
        </AbsoluteFill>
      </Series.Sequence>

      {/* 씬2 — 깐부회동 기억 환기 */}
      <Series.Sequence durationInFrames={SDUR}>
        <AbsoluteFill>
          <ImgSplitScene
            img="images/jh/gen_s02.jpeg"
            imgPos="center center"
            label="🍗 1차 깐부회동"
            title={`그날\n기억하세요?`}
            points={[
              '이재용 · 정의선과 삼겹살 회동 (2025.10)',
              '회동 직후 삼성전자 · 현대차 폭등',
              '이번엔 4명으로 확대',
            ]}
            caption="1차 깐부회동 이후 뭐가 올랐는지 기억하세요?"
          />
          <SubBar text="1차 깐부회동 이후 삼성·현대차 폭등했습니다." />
        </AbsoluteFill>
      </Series.Sequence>

      {/* 씬3 — 주가 차트 + 다음 타자 */}
      <Series.Sequence durationInFrames={SDUR}>
        <AbsoluteFill>
          <ImgSplitScene
            img="images/jh/gen_s03.jpeg"
            imgPos="center center"
            label="📈 방한 소식 하루 만에"
            title={`LG전자\n+29%`}
            points={[
              '5월 29일 단 하루 역대급 급등',
              '현대차 · 네이버도 동반 상승',
              '"이미 오른 거" 말고 다음 타자는?',
            ]}
            caption="이미 오른 종목 말고, 아직 안 오른 곳을 찾아야 합니다."
          />
          <SubBar text="이미 오른 종목 말고, 아직 안 오른 곳을 찾아야 합니다." />
        </AbsoluteFill>
      </Series.Sequence>

      {/* 씬4 — 피지컬 AI 로보틱스 */}
      <Series.Sequence durationInFrames={SDUR}>
        <AbsoluteFill>
          <ImgSplitScene
            img="images/jh/gen_s04.jpeg"
            imgPos="center center"
            label="🤖 피지컬 AI"
            title={`다음 타자\n로보틱스`}
            points={[
              '한국 로보틱스 투자 검토 공식 발언',
              '삼성 · SK · 현대차 · LG · 두산 전방위',
              'GTC 서울 개최 가능성 언급',
            ]}
            caption="5일 성수동 4인 회동 — 최태원 · 정의선 · 구광모 · 이해진"
          />
          <SubBar text="5일 성수동 4인 회동. 회동 결과에 따라 주가 움직입니다." />
        </AbsoluteFill>
      </Series.Sequence>

      {/* 씬5 — 서울 야경: 클로징 */}
      <Series.Sequence durationInFrames={SDUR}>
        <AbsoluteFill>
          <ImgHeroScene
            img="images/jh/gen_s05.jpeg"
            label="🎯 다음 영상 예고"
            line1="코스피"
            line2="9천피 목전"
            caption="수급빈집 × 주도 조건 종목 — 다음 영상에서 공개"
          />
          <SubBar text="다음 영상에서 수급빈집 종목 공개합니다. 구독 눌러두세요." />
        </AbsoluteFill>
      </Series.Sequence>

    </Series>
  </AbsoluteFill>
);

export const JH_SAMPLE_FRAMES = SDUR * 5; // 900프레임 = 30초
