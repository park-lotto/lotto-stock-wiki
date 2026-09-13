import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 인용구형 자막(#14 감성): 위·아래 큰 따옴표(" ") + 2줄 텍스트. 감성적 톤.
// sub/text 만 바꾸면 같은 인용구 스타일. quotePos: 따옴표 위치(both/wrap).
export type LilyQuoteProps = {
  sub?: string;         // 위 작은 줄
  text: string;         // 큰 줄(강조)
  color?: string;
  subColor?: string;
  quoteColor?: string;
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyQuote: React.FC<LilyQuoteProps> = ({
  sub = '',
  text,
  color = '#ffffff',
  subColor = '#cfcfcf',
  quoteColor = '#dcdcdc',
  fontFamily = 'TmonMonsori',
  fontSize = 68,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 10], [0, 1], {extrapolateRight: 'clamp'});
  const rise = interpolate(frame, [0, 12], [16, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '68%' : '40%';
  const estW = text.length * fontSize * 0.62 + 120;
  const fit = Math.min(1, (width * 0.86) / estW);
  const q = {fontFamily: 'Georgia, serif', color: quoteColor, fontSize: fontSize * 1.5, lineHeight: 0.6, fontWeight: 700} as const;

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `translateY(${rise}px) scale(${fit})`, textAlign: 'center'}}>
        <div style={{...q, marginBottom: 4}}>&ldquo;</div>
        {sub ? (
          <div style={{fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, fontWeight: 500, fontSize: fontSize * 0.5, color: subColor, textShadow: '0 2px 8px rgba(0,0,0,0.6)'}}>
            {sub}
          </div>
        ) : null}
        <div style={{fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, fontWeight: 900, fontSize, color, letterSpacing: '0.06em', whiteSpace: 'nowrap', textShadow: '0 3px 12px rgba(0,0,0,0.7)'}}>
          {text}
        </div>
        <div style={{...q, marginTop: 4}}>&rdquo;</div>
      </div>
    </AbsoluteFill>
  );
};
