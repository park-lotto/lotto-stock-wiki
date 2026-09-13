import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 질문형 자막(#14 Q.): 왼쪽 큰 'Q.' + 오른쪽 질문 텍스트(1~2줄).
// text 만 바꾸면 같은 질문 스타일. boxed: 회색 박스 안에 넣을지.
export type LilyQuestionProps = {
  text: string;
  mark?: string;        // 'Q.' 등
  color?: string;
  boxed?: boolean;
  boxBg?: string;
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyQuestion: React.FC<LilyQuestionProps> = ({
  text,
  mark = 'Q.',
  color = '#ffffff',
  boxed = false,
  boxBg = 'rgba(30,30,30,0.9)',
  fontFamily = 'TmonMonsori',
  fontSize = 60,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 9], [0, 1], {extrapolateRight: 'clamp'});
  const rise = interpolate(frame, [0, 12], [14, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '70%' : '42%';
  const estW = text.length * fontSize * 0.6 + fontSize * 2 + 100;
  const fit = Math.min(1, (width * 0.88) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop, opacity, transform: `translateY(${rise}px) scale(${fit})`,
          display: 'flex', alignItems: 'flex-start', gap: 14,
          background: boxed ? boxBg : 'transparent',
          padding: boxed ? '12px 26px' : 0,
          fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
        }}
      >
        <div style={{fontFamily: 'Georgia, serif', fontStyle: 'italic', fontWeight: 700, fontSize: fontSize * 1.35, color, lineHeight: 1, textShadow: '0 2px 8px rgba(0,0,0,0.6)'}}>{mark}</div>
        <div style={{fontWeight: 700, fontSize, color, lineHeight: 1.25, maxWidth: width * 0.7, textShadow: '0 2px 10px rgba(0,0,0,0.7)', wordBreak: 'keep-all', paddingTop: fontSize * 0.15}}>
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
