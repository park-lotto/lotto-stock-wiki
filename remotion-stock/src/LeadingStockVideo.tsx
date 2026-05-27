// "왜 주도주를 사야하는가?" — 60초 10장면
import { Series } from 'remotion';
import { SDUR } from './constants';
import { FadeWrapper } from './components/FadeWrapper';
import { LS01 } from './scenes/LS01';
import { LS02 } from './scenes/LS02';
import { LS03 } from './scenes/LS03';
import { LS04 } from './scenes/LS04';
import { LS05 } from './scenes/LS05';
import { LS06 } from './scenes/LS06';
import { LS07 } from './scenes/LS07';
import { LS08 } from './scenes/LS08';
import { LS09 } from './scenes/LS09';
import { LS10 } from './scenes/LS10';

export const LeadingStockVideo = () => (
  <Series>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS01 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS02 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS03 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS04 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS05 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS06 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS07 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS08 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS09 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><LS10 /></FadeWrapper></Series.Sequence>
  </Series>
);
