import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 팝 단어(#38 ver9/10/11: 머뭇/수줍/???): 대형 글자가
// 흐림(blur)에서 선명해지며 통통 튀어 등장. 감정 단어 강조용.
// word 만 바꾸면 같은 효과.
export type LilyPopProps = {
  word: string;
  color?: string;
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyPop: React.FC<LilyPopProps> = ({
  word,
  color = '#ffffff',
  fontFamily = 'TmonMonsori',
  fontSize = 240,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 11, mass: 0.7, stiffness: 120}});
  const scale = interpolate(s, [0, 1], [0.5, 1]);
  // 등장 초반 강한 블러 → 0
  const blur = interpolate(frame, [0, 10], [26, 0], {extrapolateRight: 'clamp'});
  const opacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '18%' : position === 'bottom' ? '58%' : '32%';
  const estW = word.length * fontSize * 0.66 + 40;
  const fit = Math.min(1, (width * 0.86) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          opacity,
          transform: `scale(${fit * scale})`,
          filter: `blur(${blur}px)`,
          fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
          fontWeight: 900,
          fontSize,
          color,
          letterSpacing: '0.04em',
          textShadow: '0 0 24px rgba(255,255,255,0.55), 0 6px 20px rgba(0,0,0,0.6)',
          whiteSpace: 'nowrap',
        }}
      >
        {word}
      </div>
    </AbsoluteFill>
  );
};
