import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 환승연애 로워서드(#38 ver1~4): 좌측 이름표(탭) + 본문.
// variant 'bar'  = ver1/2: 검은 넓은 자막바 위에 작은 이름표 탭이 얹힘.
// variant 'plain'= ver3/4: 색 이름표 탭(밑줄) + 바 없이 큰 본문.
// name/text/color 만 바꾸면 같은 스타일.
export type LilyLowerProps = {
  name: string;
  text: string;
  variant?: 'bar' | 'plain';
  color?: string;       // 이름표 배경(그라데이션 기준색)
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyLower: React.FC<LilyLowerProps> = ({
  name,
  text,
  variant = 'bar',
  color = '#3b6ea5',
  fontFamily = 'TmonMonsori',
  fontSize = 52,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const slide = interpolate(frame, [0, 12], [-40, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '16%' : position === 'bottom' ? '70%' : '42%';
  const estW = text.length * fontSize * 0.62 + name.length * fontSize * 0.5 + 220;
  const fit = Math.min(1, (width * 0.92) / estW);

  // 이름표 탭: 좌상단 살짝 기운 그라데이션(원본은 사선 절단 느낌)
  const tab = (
    <div
      style={{
        display: 'inline-block',
        background: `linear-gradient(100deg, ${color} 0%, ${color}cc 100%)`,
        color: '#fff',
        fontWeight: 700,
        fontSize: fontSize * 0.5,
        padding: '5px 22px 5px 16px',
        clipPath: 'polygon(0 0, 100% 0, 92% 100%, 0% 100%)',
        letterSpacing: '0.02em',
        fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
        whiteSpace: 'nowrap',
      }}
    >
      {name}
    </div>
  );

  if (variant === 'bar') {
    return (
      <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
        <div style={{marginTop, opacity, transform: `translateX(${slide}px) scale(${fit})`, transformOrigin: 'center'}}>
          {/* 이름표는 바 좌상단에 얹힘 */}
          <div style={{marginLeft: 24, marginBottom: -2, position: 'relative', zIndex: 2}}>{tab}</div>
          <div
            style={{
              background: 'rgba(10,10,12,0.92)',
              padding: '16px 40px',
              minWidth: width * 0.62,
              boxShadow: '0 6px 20px rgba(0,0,0,0.5)',
            }}
          >
            <span style={{color: '#e8e8e8', fontWeight: 500, fontSize, fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, whiteSpace: 'nowrap'}}>{text}</span>
          </div>
        </div>
      </AbsoluteFill>
    );
  }

  // plain: 이름표 탭 + 바 없이 큰 본문(이름표에 밑줄강조)
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `translateX(${slide}px) scale(${fit})`, display: 'flex', alignItems: 'center', gap: 16}}>
        <div style={{position: 'relative', paddingBottom: 4}}>
          {/* 이름표: 색 배경 탭 + 흰 글자(사선 절단) + 아래 밑줄강조 */}
          <div style={{background: `linear-gradient(100deg, ${color}, ${color}cc)`, color: '#fff', fontWeight: 800, fontSize: fontSize * 0.6, fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, padding: '4px 18px', clipPath: 'polygon(0 0,100% 0,90% 100%,0 100%)', textShadow: '0 1px 3px rgba(0,0,0,0.3)', whiteSpace: 'nowrap'}}>{name}</div>
          <div style={{position: 'absolute', left: 0, right: 0, bottom: -4, height: 4, background: color, borderRadius: 2}} />
        </div>
        <div style={{color: '#f5f5f5', fontWeight: 900, fontSize, fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, whiteSpace: 'nowrap', textShadow: '0 3px 10px rgba(0,0,0,0.8)'}}>{text}</div>
      </div>
    </AbsoluteFill>
  );
};
