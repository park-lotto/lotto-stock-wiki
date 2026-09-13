import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 말풍선 첨자(#11 첨자 자막): 위에 둥근 말풍선 라벨(꼬리 有) +
// 아래 본문(일부 단어 강조색). label/text/highlight/색만 바꾸면 같은 스타일.
export type LilyBubbleProps = {
  label: string;        // 위 말풍선 안 글자(예: "첨자 자리 입니당!")
  text: string;         // 본문
  highlight?: string;   // 본문 중 강조할 단어
  labelBg?: string;     // 말풍선 배경
  labelColor?: string;
  color?: string;       // 본문 기본색
  hlColor?: string;     // 강조색
  strokeColor?: string; // 본문 외곽선
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyBubble: React.FC<LilyBubbleProps> = ({
  label,
  text,
  highlight = '',
  labelBg = '#ff7ab8',
  labelColor = '#ffffff',
  color = '#ffffff',
  hlColor = '#ff5fb0',
  strokeColor = '#ffffff',
  fontFamily = 'TmonMonsori',
  fontSize = 66,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 12, stiffness: 130, mass: 0.7}});
  const opacity = interpolate(frame, [0, 7], [0, 1], {extrapolateRight: 'clamp'});
  const labelPop = interpolate(s, [0, 1], [0.6, 1]);
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '62%' : '38%';
  const estW = text.length * fontSize * 0.66 + 80;
  const fit = Math.min(1, (width * 0.88) / estW);

  // 본문 강조 분해
  let parts: {t: string; hl: boolean}[] = [{t: text, hl: false}];
  if (highlight && text.includes(highlight)) {
    const i = text.indexOf(highlight);
    parts = [
      {t: text.slice(0, i), hl: false},
      {t: highlight, hl: true},
      {t: text.slice(i + highlight.length), hl: false},
    ].filter((p) => p.t.length);
  }
  const ff = `"${fontFamily}", "Malgun Gothic", sans-serif`;
  const strokeStyle = {WebkitTextStroke: `${Math.round(fontSize * 0.09)}px ${strokeColor}`, paintOrder: 'stroke fill' as const};

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `scale(${fit})`, textAlign: 'center', fontFamily: ff}}>
        {/* 말풍선 라벨 */}
        <div style={{display: 'inline-block', position: 'relative', transform: `scale(${labelPop})`, marginBottom: 18}}>
          <div style={{background: labelBg, color: labelColor, fontWeight: 800, fontSize: fontSize * 0.52, padding: '8px 24px', borderRadius: 999, boxShadow: '0 4px 12px rgba(0,0,0,0.25)', whiteSpace: 'nowrap'}}>{label}</div>
          {/* 꼬리 */}
          <div style={{position: 'absolute', left: '50%', bottom: -10, width: 0, height: 0, borderLeft: '10px solid transparent', borderRight: '10px solid transparent', borderTop: `14px solid ${labelBg}`, transform: 'translateX(-50%)'}} />
        </div>
        {/* 본문 */}
        <div style={{fontWeight: 900, fontSize, whiteSpace: 'nowrap', textShadow: '0 3px 10px rgba(0,0,0,0.5)', ...strokeStyle}}>
          {parts.map((p, i) => (
            <span key={i} style={{color: p.hl ? hlColor : color}}>{p.t}</span>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
