import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 별폭발 컷(#28 이건아니지! / #42 별폭발): 뾰족뾰족 폭발 도형 배경 +
// 2줄 큰 글자. 만화 강조컷. text(\n 2줄)/burstColor 만 바꾸면 같은 스타일.
export type LilyBurstProps = {
  text: string;         // \n 으로 2줄
  burstColor?: string;  // 폭발 도형 색
  textColor?: string;
  strokeColor?: string;
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

// 12꼭짓점 별폭발 폴리곤
const BURST = (() => {
  const pts: string[] = [];
  const n = 14;
  for (let i = 0; i < n * 2; i++) {
    const a = (Math.PI * i) / n;
    const r = i % 2 === 0 ? 50 : 33;
    const x = 50 + Math.cos(a) * r;
    const y = 50 + Math.sin(a) * r;
    pts.push(`${x.toFixed(1)}% ${y.toFixed(1)}%`);
  }
  return `polygon(${pts.join(',')})`;
})();

export const LilyBurst: React.FC<LilyBurstProps> = ({
  text,
  burstColor = '#e23a3a',
  textColor = '#ffffff',
  strokeColor = '#1a1a1a',
  fontFamily = 'TmonMonsori',
  fontSize = 92,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 9, stiffness: 200, mass: 0.8}});
  const scale = interpolate(s, [0, 1], [0.3, 1]);
  const opacity = interpolate(frame, [0, 4], [0, 1], {extrapolateRight: 'clamp'});
  const spin = interpolate(frame, [0, 30], [-6, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '12%' : position === 'bottom' ? '52%' : '28%';
  const lines = text.split(/\\n|\n/);
  const longest = Math.max(...lines.map((l) => l.length));
  const box = longest * fontSize * 0.62 + fontSize * 2.4;
  const size = Math.min(width * 0.9, box);
  const ff = `"${fontFamily}", "Malgun Gothic", sans-serif`;

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `scale(${scale}) rotate(${spin}deg)`, width: size, height: size, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        {/* 흰 테두리 폭발(살짝 큰) */}
        <div style={{position: 'absolute', inset: 0, background: '#ffffff', clipPath: BURST}} />
        {/* 색 폭발 */}
        <div style={{position: 'absolute', inset: '4%', background: burstColor, clipPath: BURST}} />
        <div style={{position: 'relative', textAlign: 'center', fontFamily: ff, fontWeight: 900, fontSize, color: textColor, WebkitTextStroke: `${Math.round(fontSize * 0.06)}px ${strokeColor}`, paintOrder: 'stroke fill', lineHeight: 1.05, textShadow: '0 3px 8px rgba(0,0,0,0.4)'}}>
          {lines.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      </div>
    </AbsoluteFill>
  );
};
