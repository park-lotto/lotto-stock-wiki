import {Composition} from 'remotion';
import {SwipeLeft} from './SwipeLeft';
import {Sparkle} from './Sparkle';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="SwipeLeft" component={SwipeLeft} durationInFrames={18} fps={30} width={720} height={1280} />
    <Composition id="Sparkle" component={Sparkle} durationInFrames={30} fps={30} width={300} height={300} />
  </>
);
