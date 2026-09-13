import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 2줄형 자막(심플 등): 위에 작은 부제(회색) + 아래 큰 본문(흰색).
// sub·text 만 바꾸면 같은 구조로 나온다. 박스·글로우 없이 깔끔한 스타일.
export type LilyStackProps = {
  sub?: string;         // 위 작은 줄
  text: string;         // 아래 큰 줄
  subColor?: string;
  color?: string;
  fontFamily?: string;
  position?: 'top' | 'mid' | 'bottom';
  fontSize?: number;
};

export const LilyStack: React.FC<LilyStackProps> = ({
  sub = '',
  text,
  subColor = '#bdbdbd',
  color = '#ffffff',
  fontFamily = 'TmonMonsori',
  position = 'bottom',
  fontSize = 72,
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const rise = interpolate(frame, [0, 10], [16, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '72%' : '42%';
  const estW = text.length * fontSize * 0.62 + 80;
  const fit = Math.min(1, (width * 0.86) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `translateY(${rise}px)`, textAlign: 'center'}}>
        {sub ? (
          <div
            style={{
              fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
              fontWeight: 700,
              fontSize: fontSize * 0.42,
              color: subColor,
              marginBottom: 6,
              textShadow: '0 2px 8px rgba(0,0,0,0.6)',
            }}
          >
            {sub}
          </div>
        ) : null}
        <div
          style={{
            fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
            fontWeight: 900,
            fontSize: fontSize * fit,
            color,
            whiteSpace: 'nowrap',
            textShadow: '0 3px 12px rgba(0,0,0,0.75)',
          }}
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
