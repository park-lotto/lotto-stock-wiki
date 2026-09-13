import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 밑줄형 자막(#14): 위 작은 부제 + 밑줄 + 아래 본문. 또는 본문 아래 밑줄.
// underlineGrow: 밑줄이 좌→우로 그려지는 등장.
export type LilyUnderlineProps = {
  sub?: string;
  text: string;
  color?: string;
  subColor?: string;
  lineColor?: string;
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyUnderline: React.FC<LilyUnderlineProps> = ({
  sub = '',
  text,
  color = '#ffffff',
  subColor = '#cfcfcf',
  lineColor = '#ffffff',
  fontFamily = 'TmonMonsori',
  fontSize = 68,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 9], [0, 1], {extrapolateRight: 'clamp'});
  const lineW = interpolate(frame, [3, 16], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '70%' : '42%';
  const estW = text.length * fontSize * 0.62 + 60;
  const fit = Math.min(1, (width * 0.86) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `scale(${fit})`, textAlign: 'center', fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, display: 'inline-block'}}>
        {sub ? (
          <div style={{fontWeight: 500, fontSize: fontSize * 0.5, color: subColor, marginBottom: 10, textShadow: '0 2px 8px rgba(0,0,0,0.6)'}}>{sub}</div>
        ) : null}
        <div style={{fontWeight: 900, fontSize, color, whiteSpace: 'nowrap', textShadow: '0 3px 12px rgba(0,0,0,0.7)'}}>{text}</div>
        {/* 밑줄: 글자 폭 전체를 좌→우로 채운다(overflow로 lineW% 만큼만 보임) */}
        <div style={{height: 5, marginTop: 12, overflow: 'hidden', width: `${lineW}%`, marginLeft: 'auto', marginRight: 'auto'}}>
          <div style={{height: 5, background: lineColor, width: '100%', boxShadow: '0 1px 6px rgba(0,0,0,0.5)', borderRadius: 2}} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
