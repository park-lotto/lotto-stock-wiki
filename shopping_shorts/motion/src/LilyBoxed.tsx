import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 테두리 박스형 자막(크리스마스 등): 얇은 색 테두리 사각 + 그 안 이탤릭 글자.
// text 만 바꾸면 같은 박스 스타일로 나온다. 색은 프리셋 파라미터.
export type LilyBoxedProps = {
  text: string;
  color?: string;       // 글자·테두리 색
  fontFamily?: string;
  italic?: number;
  position?: 'top' | 'mid' | 'bottom';
  glow?: string;
  fontSize?: number;
};

export const LilyBoxed: React.FC<LilyBoxedProps> = ({
  text,
  color = '#e8b73a',
  fontFamily = 'TmonMonsori',
  italic = 8,
  position = 'bottom',
  glow = 'rgba(232,183,58,0.35)',
  fontSize = 66,
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  // 테두리가 좌→우로 그려지는 등장(간단): 박스 폭을 0→100%
  const boxW = interpolate(frame, [2, 14], [0.2, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '12%' : position === 'bottom' ? '76%' : '44%';
  const estW = text.length * fontSize * 0.62 + 120;
  const fit = Math.min(1, (width * 0.86) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          opacity,
          transform: `scaleX(${boxW})`,
          border: `3px solid ${color}`,
          padding: '14px 40px',
          display: 'inline-block',
          boxShadow: `0 0 18px ${glow}`,
        }}
      >
        <div
          style={{
            transform: `scaleX(${1 / boxW}) ${italic ? `skewX(-${italic}deg)` : ''}`,
            fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
            fontWeight: 900,
            fontSize: fontSize * fit,
            color,
            whiteSpace: 'nowrap',
            textShadow: `0 0 12px ${glow}`,
            letterSpacing: '0.01em',
          }}
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
