import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 도장 자막(#41 REJECTED 등): 색 이중 테두리 사각 + 굵은 글자, 기울어짐, '쾅' 찍히는 등장.
// text/color 만 바꾸면 같은 스탬프로 나온다.
export type LilyStampProps = {
  text: string;
  color?: string;
  rotate?: number;
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyStamp: React.FC<LilyStampProps> = ({
  text,
  color = '#e01d1d',
  rotate = -11,
  fontFamily = 'TmonMonsori',
  fontSize = 96,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  // 쾅: 크게 시작 → 순간 축소하며 찍힘 + 초반 흔들림
  const stamp = spring({frame, fps, config: {damping: 8, stiffness: 260, mass: 0.8}});
  const scale = interpolate(stamp, [0, 1], [2.4, 1]);
  const opacity = interpolate(frame, [0, 3], [0, 1], {extrapolateRight: 'clamp'});
  const shake = frame < 12 ? Math.sin(frame * 3) * (1 - frame / 12) * 3 : 0;
  const marginTop = position === 'top' ? '16%' : position === 'bottom' ? '66%' : '40%';
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          opacity,
          transform: `scale(${scale}) rotate(${rotate + shake}deg)`,
          border: `6px solid ${color}`,
          outline: `2px solid ${color}`,
          outlineOffset: 6,
          padding: '10px 30px',
          display: 'inline-block',
        }}
      >
        <div
          style={{
            fontFamily: `"${fontFamily}", "Arial Black", sans-serif`,
            fontWeight: 900,
            fontSize,
            color,
            letterSpacing: '0.04em',
            whiteSpace: 'nowrap',
            textShadow: `0 0 2px ${color}`,
          }}
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
