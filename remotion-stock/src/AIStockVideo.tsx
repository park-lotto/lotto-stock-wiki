import { Series } from 'remotion';
import { SDUR } from './constants';
import { FadeWrapper } from './components/FadeWrapper';
import { Scene01 } from './scenes/Scene01';
import { Scene02 } from './scenes/Scene02';
import { Scene03 } from './scenes/Scene03';
import { Scene04 } from './scenes/Scene04';
import { Scene05 } from './scenes/Scene05';
import { Scene06 } from './scenes/Scene06';
import { Scene07 } from './scenes/Scene07';
import { Scene08 } from './scenes/Scene08';
import { Scene09 } from './scenes/Scene09';
import { Scene10 } from './scenes/Scene10';

// 60초 × 30fps = 1800프레임 / 장면당 SDUR(180프레임) = 10장면
export const AIStockVideo = () => (
  <Series>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene01 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene02 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene03 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene04 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene05 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene06 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene07 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene08 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene09 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><Scene10 /></FadeWrapper></Series.Sequence>
  </Series>
);
