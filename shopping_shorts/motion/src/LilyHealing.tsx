import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 힐링 감성 자막(#44). variant 로 버전을 나눔.
//  'brace'(ver4/6): 위 작은 부제 + { ENG 문구 }(serif, 중괄호 강조)
//  'soft'(ver1/2/3): 부드러운 파스텔 한 줄(위아래 얇은 선)
//  'coffee'(ver10): 이름표 | 감성 한 줄(잔잔한 로워서드 바)
// sub/text/accent 만 바꾸면 같은 스타일.
export type LilyHealingProps = {
  variant: 'brace' | 'soft' | 'coffee';
  sub?: string;
  text: string;
  name?: string;        // coffee 이름표
  color?: string;
  accent?: string;      // 중괄호·강조색
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyHealing: React.FC<LilyHealingProps> = ({
  variant,
  sub = '',
  text,
  name = '',
  color = '#f0ece6',
  accent = '#d98f5a',
  fontFamily = 'TmonMonsori',
  fontSize = 58,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 12], [0, 1], {extrapolateRight: 'clamp'});
  const rise = interpolate(frame, [0, 16], [10, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '16%' : position === 'bottom' ? '66%' : '42%';
  const ff = `"${fontFamily}", "Malgun Gothic", sans-serif`;
  const serif = `Georgia, "Times New Roman", serif`;
  const estW = text.length * fontSize * 0.66 + 200;
  const fit = Math.min(1, (width * 0.86) / estW);
  const wrap = (child: React.ReactNode) => (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `translateY(${rise}px) scale(${fit})`, textAlign: 'center'}}>{child}</div>
    </AbsoluteFill>
  );

  if (variant === 'brace') {
    return wrap(
      <div>
        {sub ? <div style={{fontFamily: ff, fontWeight: 500, fontSize: fontSize * 0.55, color, marginBottom: 12, letterSpacing: '0.04em', textShadow: '0 2px 8px rgba(0,0,0,0.6)'}}>{sub}</div> : null}
        <div style={{fontFamily: serif, fontWeight: 600, fontSize: fontSize * 1.15, color, letterSpacing: '0.12em', textShadow: '0 2px 10px rgba(0,0,0,0.6)'}}>
          <span style={{color: accent, margin: '0 14px'}}>{'{'}</span>
          {text}
          <span style={{color: accent, margin: '0 14px'}}>{'}'}</span>
        </div>
      </div>
    );
  }

  if (variant === 'soft') {
    return wrap(
      <div style={{padding: '4px 0'}}>
        <div style={{height: 2, width: '70%', margin: '0 auto 14px', background: 'rgba(255,255,255,0.4)'}} />
        <div style={{fontFamily: ff, fontWeight: 700, fontSize, color, whiteSpace: 'nowrap', textShadow: '0 2px 10px rgba(0,0,0,0.6)'}}>{text}</div>
        <div style={{height: 2, width: '70%', margin: '14px auto 0', background: 'rgba(255,255,255,0.4)'}} />
      </div>
    );
  }

  // coffee: 잔잔한 로워서드 바 [이름] | 문구
  return wrap(
    <div style={{display: 'inline-flex', alignItems: 'center', background: 'rgba(20,18,16,0.72)', borderRadius: 6, overflow: 'hidden', boxShadow: '0 4px 14px rgba(0,0,0,0.4)', fontFamily: ff}}>
      {name ? <div style={{color: accent, fontWeight: 700, fontSize: fontSize * 0.52, padding: '10px 18px', whiteSpace: 'nowrap'}}>{name}</div> : null}
      <div style={{width: 1, alignSelf: 'stretch', background: 'rgba(255,255,255,0.25)'}} />
      <div style={{color, fontWeight: 500, fontSize: fontSize * 0.56, padding: '10px 22px', whiteSpace: 'nowrap'}}>{text}</div>
    </div>
  );
};
