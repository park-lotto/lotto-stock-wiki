/**
 * DocHighlight_Demo.tsx — DocumentHighlightScene 실제 동작 데모
 *
 * 소스: news_headlines.png (네이버 "국민성장펀드 완판" 검색결과)
 *
 * 씬 흐름 (총 300프레임 = 10초):
 *   0~120f  — 1헤드라인 줌인 + "이르면 8월 출시" 형광펜
 *   120~300f — 아래 기사로 팬 + "이억원 2차분 출시" 형광펜
 */
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { DocPanScene } from './DocumentHighlightScene';

export const DOC_DEMO_FRAMES = 300;

export const DocHighlight_Demo: React.FC = () => (
  <AbsoluteFill>
    <DocPanScene
      imageSrc="images/news_headlines.png"
      tag={{ text: '네이버 뉴스', sub: '국민성장펀드 완판 검색' }}
      segments={[
        {
          startFrame: 0,
          endFrame: 120,
          // 첫 번째 기사 헤드라인 영역 줌인
          // (이미지 상단 24%~47%, 좌측 10%~62% 구간)
          crop: { top: 24, right: 38, bottom: 53, left: 10 },
          highlights: [
            {
              // "이르면 8월 출시" — 헤드라인 텍스트 뒷부분
              // 팝업 내 헤드라인은 세로 22~46% 위치, 가로는 38~80% 지점
              top: 22, left: 38, width: 42, height: 22,
              color: '#FFE500', delay: 45, animDur: 20,
            },
          ],
          caption: '국민성장펀드 2차 — 이르면 8월 출시 공식화',
        },
        {
          startFrame: 120,
          endFrame: 300,
          // 세 번째 기사 (매일경제) 영역으로 팬다운
          crop: { top: 60, right: 38, bottom: 20, left: 10 },
          highlights: [
            {
              // "'조기 완판'" 강조 — 제목 앞부분
              top: 10, left: 0, width: 22, height: 20,
              color: '#FF6B35', delay: 145, animDur: 16,
            },
            {
              // "2차분 출시할 것" 강조 — 제목 뒷부분
              top: 10, left: 52, width: 36, height: 20,
              color: '#FFE500', delay: 168, animDur: 16,
            },
          ],
          caption: '이억원 금융위원장 — 2차분 출시 공식 선언',
        },
      ]}
    />
  </AbsoluteFill>
);
