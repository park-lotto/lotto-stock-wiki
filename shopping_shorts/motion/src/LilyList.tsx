import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 리스트 자막(#42 신서유기 강호동 3등): 상단 헤드라인(일부 강조) +
// 아래 "- 항목" 여러 줄이 순서대로 등장. head/items/색만 바꾸면 같은 스타일.
// 항목 안 **단어**는 강조색으로 칠한다.
export type LilyListProps = {
  head: string;         // 예: "강호동 [3등]으로 도착!" ([] 안이 강조)
  items: string[];      // 예: ["[천하장사] 출신", "대한민국 [국민MC]", "특기 : [잘먹기]"]
  color?: string;       // 기본 글자색
  hlColor?: string;     // [] 강조색
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

const paint = (s: string, color: string, hl: string, ff: string, size: number, weight: number) => {
  const parts = s.split(/(\[[^\]]*\])/g).filter(Boolean);
  return parts.map((p, i) =>
    p.startsWith('[') && p.endsWith(']')
      ? <span key={i} style={{color: hl}}>{p.slice(1, -1)}</span>
      : <span key={i} style={{color}}>{p}</span>
  );
};

export const LilyList: React.FC<LilyListProps> = ({
  head,
  items,
  color = '#ffffff',
  hlColor = '#ffb000',
  fontFamily = 'TmonMonsori',
  fontSize = 56,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 7], [0, 1], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '12%' : position === 'bottom' ? '52%' : '28%';
  const ff = `"${fontFamily}", "Malgun Gothic", sans-serif`;
  const allLen = Math.max(head.length, ...items.map((s) => s.length + 2));
  const estW = allLen * fontSize * 0.6 + 60;
  const fit = Math.min(1, (width * 0.86) / estW);

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `scale(${fit})`, textAlign: 'left', fontFamily: ff, textShadow: '0 3px 10px rgba(0,0,0,0.6)'}}>
        <div style={{fontWeight: 900, fontSize: fontSize * 1.15, marginBottom: 18}}>{paint(head, color, hlColor, ff, fontSize, 900)}</div>
        {items.map((it, i) => {
          const rise = interpolate(frame, [6 + i * 5, 14 + i * 5], [16, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const op = interpolate(frame, [6 + i * 5, 14 + i * 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <div key={i} style={{fontWeight: 800, fontSize, opacity: op, transform: `translateY(${rise}px)`, marginBottom: 8}}>
              <span style={{color: hlColor}}>–&nbsp;</span>{paint(it, color, hlColor, ff, fontSize, 800)}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
