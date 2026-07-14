import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export const Sparkle: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 8}});
  const rot = interpolate(frame, [0, 30], [0, 45]);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{fontSize: 180, transform: `scale(${s}) rotate(${rot}deg)`}}>✨</div>
    </AbsoluteFill>
  );
};
