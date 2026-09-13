import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 이름표+상자 자막(환승연애·신서유기): 색 테두리 긴 상자 안에
// [왼쪽 이름표] | [오른쪽 자막]. name/text/color 만 바꾸면 같은 스타일.
export type LilyNameBarProps = {
  name: string;
  text: string;
  color?: string;       // 테두리·구분선·글자 색
  bg?: string;          // 상자 배경
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyNameBar: React.FC<LilyNameBarProps> = ({
  name,
  text,
  color = '#ffffff',
  bg = 'rgba(0,0,0,0.55)',
  fontFamily = 'TmonMonsori',
  fontSize = 44,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const rise = interpolate(frame, [0, 10], [14, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '72%' : '44%';
  const estW = (name.length + text.length) * fontSize * 0.62 + 160;
  const fit = Math.min(1, (width * 0.9) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          opacity,
          transform: `translateY(${rise}px) scale(${fit})`,
          display: 'flex',
          alignItems: 'stretch',
          border: `2px solid ${color}`,
          background: bg,
          fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
        }}
      >
        <div style={{color, fontWeight: 700, fontSize: fontSize * 0.82, padding: '8px 20px', display: 'flex', alignItems: 'center', borderRight: `2px solid ${color}`, whiteSpace: 'nowrap'}}>
          {name}
        </div>
        <div style={{color, fontWeight: 700, fontSize, padding: '8px 36px', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap'}}>
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
