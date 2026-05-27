// "내가 사면 늘 고점에서 물리는 이유" — 60초 10장면
import { Series } from 'remotion';
import { SDUR } from './constants';
import { FadeWrapper } from './components/FadeWrapper';
import { BH01 } from './scenes/BH01';
import { BH02 } from './scenes/BH02';
import { BH03 } from './scenes/BH03';
import { BH04 } from './scenes/BH04';
import { BH05 } from './scenes/BH05';
import { BH06 } from './scenes/BH06';
import { BH07 } from './scenes/BH07';
import { BH08 } from './scenes/BH08';
import { BH09 } from './scenes/BH09';
import { BH10 } from './scenes/BH10';

export const BuyHighVideo = () => (
  <Series>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH01 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH02 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH03 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH04 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH05 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH06 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH07 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH08 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH09 /></FadeWrapper></Series.Sequence>
    <Series.Sequence durationInFrames={SDUR}><FadeWrapper><BH10 /></FadeWrapper></Series.Sequence>
  </Series>
);
