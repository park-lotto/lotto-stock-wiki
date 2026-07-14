import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export const SwipeLeft: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames, width} = useVideoConfig();
  // 화면 밖(오른쪽)에서 들어와 왼쪽으로 빠지는 밝은 바
  const x = interpolate(frame, [0, durationInFrames], [width, -width * 0.3]);
  return (
    <AbsoluteFill style={{backgroundColor: 'transparent'}}>
      <div style={{position: 'absolute', left: x, top: 0, width: width * 0.35,
        height: '100%', background: 'linear-gradient(90deg,rgba(255,255,255,0),#fff,rgba(255,255,255,0))',
        filter: 'blur(2px)', opacity: 0.9}} />
    </AbsoluteFill>
  );
};
