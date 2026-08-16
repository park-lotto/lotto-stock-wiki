/**
 * 로고 스팅 전용 엔트리 — ★크기는 1080x608(16:9)이다.
 * 파이프라인이 모든 조각을 '영상 창'(1080x608)에 넣고 위아래를 템플릿으로 채우므로,
 * 스팅만 9:16(1080x1920)으로 만들면 창 밖으로 밀려 로고가 엉뚱한 자리에 뜬다
 * (2026-08-15 실측: 로고가 하단 채널명과 겹쳐 나왔다). — 큰 Root.tsx를 건드리지 않고 이것만 번들한다.
 * (Root.tsx에는 컴포지션이 수십 개라 스팅 하나 뽑자고 전부 번들할 이유가 없다.)
 */
import '../index.css';
import '../load-font';
import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { LogoSting, STING_FPS, STING_FRAMES } from './LogoSting';

const Root: React.FC = () => (
  <Composition
    id="LogoSting"
    component={LogoSting}
    durationInFrames={STING_FRAMES}
    fps={STING_FPS}
    width={1080}
    height={608}
    defaultProps={{ channel: '로또의 스탁브레인', logo: undefined, accent: '#F5C451' }}
  />
);

registerRoot(Root);
