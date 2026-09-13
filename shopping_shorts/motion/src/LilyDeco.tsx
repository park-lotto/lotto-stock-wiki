import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 예능 데코 단어(#10 예능데코 / #28 일부 / #42 밈):
// ㅋㅋㅋ, ???, !@#$, 우와아아앙!!!, 빗금 등. 큰 글자가 흔들리거나 튀며 강조.
// word 만 바꾸면 같은 효과. anim: shake(부들부들) / pop(통통) / drop(위에서 쾅).
export type LilyDecoProps = {
  word: string;
  color?: string;
  strokeColor?: string;
  strokeW?: number;
  anim?: 'shake' | 'pop' | 'drop';
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyDeco: React.FC<LilyDecoProps> = ({
  word,
  color = '#ffffff',
  strokeColor = '',
  strokeW = 0,
  anim = 'shake',
  fontFamily = 'TmonMonsori',
  fontSize = 150,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 5], [0, 1], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '16%' : position === 'bottom' ? '58%' : '34%';
  // shake는 좌우로 흔들리므로 여백을 더 준다(안 그러면 화면 밖으로 나감)
  const estW = word.length * fontSize * 0.66 + (anim === 'shake' ? 160 : 60);
  const fit = Math.min(1, (width * 0.82) / estW);

  let extra = '';
  if (anim === 'shake') {
    const amp = interpolate(frame, [0, 20], [10, 4], {extrapolateRight: 'clamp'});
    extra = `translate(${Math.sin(frame * 1.6) * amp}px, ${Math.cos(frame * 1.9) * amp * 0.5}px) rotate(${Math.sin(frame * 1.2) * 2}deg)`;
  } else if (anim === 'pop') {
    const s = spring({frame, fps, config: {damping: 10, stiffness: 140, mass: 0.6}});
    extra = `scale(${interpolate(s, [0, 1], [0.4, 1])})`;
  } else {
    // drop: 위에서 떨어져 쾅
    const s = spring({frame, fps, config: {damping: 9, stiffness: 200, mass: 0.9}});
    const y = interpolate(s, [0, 1], [-180, 0]);
    extra = `translateY(${y}px)`;
  }

  const stroke = strokeColor && strokeW
    ? {WebkitTextStroke: `${strokeW}px ${strokeColor}`, paintOrder: 'stroke fill' as const}
    : {};

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          opacity,
          transform: `scale(${fit}) ${extra}`,
          fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
          fontWeight: 900,
          fontSize,
          color,
          ...stroke,
          letterSpacing: '0.03em',
          textShadow: '0 4px 16px rgba(0,0,0,0.65)',
          whiteSpace: 'nowrap',
        }}
      >
        {word}
      </div>
    </AbsoluteFill>
  );
};
