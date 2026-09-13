import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 타이핑 자막(#34): 글자가 한 글자씩 나타나며 끝에 커서가 깜빡인다.
// text 만 바꾸면 같은 타이핑 효과. 색·정렬은 파라미터.
export type LilyTypingProps = {
  text: string;
  color?: string;
  fontFamily?: string;
  fontSize?: number;
  cps?: number;         // 초당 글자 수
  align?: 'center' | 'left';
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyTyping: React.FC<LilyTypingProps> = ({
  text,
  color = '#ffffff',
  fontFamily = 'TmonMonsori',
  fontSize = 70,
  cps = 14,
  align = 'center',
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const shown = Math.min(text.length, Math.floor((frame / fps) * cps));
  const done = shown >= text.length;
  // 커서: 타이핑 중엔 항상 보이고, 끝나면 깜빡임
  const cursorOn = !done || Math.floor(frame / 8) % 2 === 0;
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '72%' : '44%';
  const estW = text.length * fontSize * 0.62 + 40;
  const fit = Math.min(1, (width * 0.9) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: align === 'center' ? 'center' : 'flex-start', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          marginLeft: align === 'left' ? '7%' : 0,
          transform: `scale(${fit})`,
          transformOrigin: align === 'left' ? 'left center' : 'center',
          fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
          fontWeight: 900,
          fontSize,
          color,
          whiteSpace: 'nowrap',
          textShadow: '0 3px 10px rgba(0,0,0,0.7)',
        }}
      >
        {text.slice(0, shown)}
        <span style={{opacity: cursorOn ? 1 : 0}}>|</span>
      </div>
    </AbsoluteFill>
  );
};
