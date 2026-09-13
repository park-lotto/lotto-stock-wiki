import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 기본 자막(P1 보강): 정보영상·브이로그의 표준 기본 자막.
// variant:
//  'box'    = 반투명 검은 박스 + 흰 글자 (정보영상 표준, 가독성 최고)
//  'pill'   = 둥근 알약 박스 (부드러운 톤)
//  'marker' = 형광펜 하이라이트(강조 단어 뒤에 색 밴드)
//  'plain'  = 박스 없이 흰 글자 + 그림자 (심플)
// text/highlight/align/색만 바꾸면 같은 스타일. 강조어는 [] 로 감싸도 인식.
export type LilyBasicProps = {
  variant?: 'box' | 'pill' | 'marker' | 'plain';
  text: string;
  highlight?: string;
  bg?: string;          // 박스 배경
  color?: string;
  hlColor?: string;     // 강조 글자색
  markerColor?: string; // 형광펜 밴드색
  align?: 'center' | 'left';
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyBasic: React.FC<LilyBasicProps> = ({
  variant = 'box',
  text,
  highlight = '',
  bg = 'rgba(15,15,18,0.78)',
  color = '#ffffff',
  hlColor = '#ffe14d',
  markerColor = 'rgba(255,225,77,0.55)',
  align = 'center',
  fontFamily = 'TmonMonsori',
  fontSize = 62,
  position = 'bottom',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const rise = interpolate(frame, [0, 11], [12, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '15%' : position === 'bottom' ? '74%' : '44%';
  const ff = `"${fontFamily}", "Malgun Gothic", sans-serif`;
  const estW = text.length * fontSize * 0.62 + 120;
  const fit = Math.min(1, (width * 0.9) / estW);

  // 강조 분해: [] 우선, 없으면 highlight 문자열
  let parts: {t: string; hl: boolean}[];
  if (text.includes('[')) {
    parts = text.split(/(\[[^\]]*\])/g).filter(Boolean).map((p) =>
      p.startsWith('[') && p.endsWith(']') ? {t: p.slice(1, -1), hl: true} : {t: p, hl: false});
  } else if (highlight && text.includes(highlight)) {
    const i = text.indexOf(highlight);
    parts = [{t: text.slice(0, i), hl: false}, {t: highlight, hl: true}, {t: text.slice(i + highlight.length), hl: false}].filter((p) => p.t.length);
  } else {
    parts = [{t: text, hl: false}];
  }

  const span = (p: {t: string; hl: boolean}, i: number) => {
    if (p.hl && variant === 'marker') {
      return <span key={i} style={{background: `linear-gradient(transparent 55%, ${markerColor} 55%)`, color, padding: '0 2px'}}>{p.t}</span>;
    }
    return <span key={i} style={{color: p.hl ? hlColor : color}}>{p.t}</span>;
  };

  const boxStyle: React.CSSProperties =
    variant === 'box' ? {background: bg, padding: '12px 26px', borderRadius: 8}
    : variant === 'pill' ? {background: bg, padding: '11px 30px', borderRadius: 999}
    : {};

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: align === 'center' ? 'center' : 'flex-start', backgroundColor: 'transparent'}}>
      <div style={{marginTop, marginLeft: align === 'left' ? '6%' : 0, opacity, transform: `translateY(${rise}px) scale(${fit})`, transformOrigin: align === 'left' ? 'left center' : 'center'}}>
        <div style={{...boxStyle, fontFamily: ff, fontWeight: variant === 'plain' || variant === 'marker' ? 900 : 800, fontSize, color, whiteSpace: 'nowrap', textAlign: align, textShadow: (variant === 'plain' || variant === 'marker') ? '0 3px 12px rgba(0,0,0,0.75)' : 'none'}}>
          {parts.map(span)}
        </div>
      </div>
    </AbsoluteFill>
  );
};
