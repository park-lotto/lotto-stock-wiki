import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 크리스마스 자막(#7). variant 로 버전을 나눔.
//  'neon'(ver2): 네온 붉은 글로우 Merry Christmas(2줄, serif) + 눈사람 이모지
//  'label'(ver3/4): 위 아이콘 라벨(🎄) + 아래 강조 본문("소중한 사람들과 함께합니다!")
//  'scene'(ver6/7): 큰 트리 아이콘 + "눈 내리는 어느 / 크리스마스 밤"(배경 색 밴드)
//  'namebar'(ver8): 눈사람/트리 이름표 + 흰 자막바
// text/accent/icon 만 바꾸면 같은 스타일.
export type LilyXmasProps = {
  variant: 'neon' | 'label' | 'scene' | 'namebar';
  title?: string;       // 위 라벨/작은 줄
  text: string;         // 본문/큰 줄
  highlight?: string;   // 강조 단어
  accent?: string;      // 강조·테마색(빨강/초록)
  icon?: string;        // 이모지(🎄 ⛄ 🎅)
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyXmas: React.FC<LilyXmasProps> = ({
  variant,
  title = '',
  text,
  highlight = '',
  accent = '#e23a3a',
  icon = '🎄',
  fontFamily = 'TmonMonsori',
  fontSize = 56,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 9], [0, 1], {extrapolateRight: 'clamp'});
  const rise = interpolate(frame, [0, 12], [14, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '64%' : '38%';
  const ff = `"${fontFamily}", "Malgun Gothic", sans-serif`;
  const estW = text.length * fontSize * 0.62 + 160;
  const fit = Math.min(1, (width * 0.88) / estW);
  const wrap = (child: React.ReactNode) => (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `translateY(${rise}px) scale(${fit})`, textAlign: 'center', fontFamily: ff}}>{child}</div>
    </AbsoluteFill>
  );

  // 본문 강조 분해
  const parts = (highlight && text.includes(highlight))
    ? [{t: text.slice(0, text.indexOf(highlight)), hl: false}, {t: highlight, hl: true}, {t: text.slice(text.indexOf(highlight) + highlight.length), hl: false}].filter((p) => p.t.length)
    : [{t: text, hl: false}];

  if (variant === 'neon') {
    return wrap(
      <div style={{fontFamily: 'Georgia, "Times New Roman", serif', fontWeight: 700, fontSize: fontSize * 1.5, color: '#fff', lineHeight: 1.05, textShadow: `0 0 8px ${accent}, 0 0 18px ${accent}, 0 0 30px ${accent}`}}>
        {text.split(/\\n|\n/).map((l, i) => <div key={i}>{l}</div>)}
        {icon ? <span style={{fontSize: fontSize, marginLeft: 8}}>{icon}</span> : null}
      </div>
    );
  }

  if (variant === 'label') {
    return wrap(
      <div>
        {title ? (
          <div style={{display: 'inline-flex', alignItems: 'center', gap: 6, background: '#fff', color: accent, fontWeight: 800, fontSize: fontSize * 0.5, padding: '5px 16px', borderRadius: 8, marginBottom: 12, boxShadow: '0 3px 10px rgba(0,0,0,0.3)'}}>
            <span>{icon}</span>{title}
          </div>
        ) : null}
        <div style={{fontWeight: 900, fontSize, whiteSpace: 'nowrap', textShadow: '0 3px 10px rgba(0,0,0,0.6)', WebkitTextStroke: '5px #fff', paintOrder: 'stroke fill'}}>
          {parts.map((p, i) => <span key={i} style={{color: p.hl ? accent : '#222'}}>{p.t}</span>)}
        </div>
      </div>
    );
  }

  if (variant === 'scene') {
    return wrap(
      <div style={{display: 'flex', alignItems: 'center', gap: 18}}>
        <div style={{fontSize: fontSize * 1.8}}>{icon}</div>
        <div style={{textAlign: 'left'}}>
          {title ? <div style={{color: '#e8e8e8', fontWeight: 700, fontSize: fontSize * 0.7, marginBottom: 6, textShadow: '0 2px 6px rgba(0,0,0,0.7)'}}>{title}</div> : null}
          <div style={{display: 'inline-block', background: accent, color: '#fff', fontWeight: 900, fontSize, padding: '6px 18px', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.4)', whiteSpace: 'nowrap'}}>{text}</div>
        </div>
      </div>
    );
  }

  // namebar: 아이콘 이름표 + 흰 자막바
  return wrap(
    <div style={{display: 'flex', alignItems: 'stretch', borderRadius: 6, overflow: 'hidden', boxShadow: '0 5px 16px rgba(0,0,0,0.45)'}}>
      <div style={{background: accent, color: '#fff', fontWeight: 800, fontSize: fontSize * 0.55, padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap'}}>
        <span>{icon}</span>{title}
      </div>
      <div style={{background: '#fff', color: '#222', fontWeight: 700, fontSize: fontSize * 0.62, padding: '10px 22px', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap'}}>{text}</div>
    </div>
  );
};
