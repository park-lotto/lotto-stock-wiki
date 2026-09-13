import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

// 릴리리아 뉴스바 자막(#4): 하단 가로 바 = 왼쪽 색 로고박스 + 오른쪽 회색바에 검은 굵은 글자.
// text/logo 만 바꾸면 같은 뉴스 자막으로 나온다.
export type LilyNewsBarProps = {
  text: string;
  logo?: string;        // 로고 박스 2줄 텍스트("SBC\nNEWS")
  logoBg?: string;
  barBg?: string;
  textColor?: string;
  fontFamily?: string;
  fontSize?: number;
};

export const LilyNewsBar: React.FC<LilyNewsBarProps> = ({
  text,
  logo = 'SBC\nNEWS',
  logoBg = '#1f6fb0',
  barBg = 'rgba(180,180,180,0.92)',
  textColor = '#111111',
  fontFamily = 'TmonMonsori',
  fontSize = 46,
}) => {
  const frame = useCurrentFrame();
  // 바가 왼쪽에서 슬라이드 인
  const x = interpolate(frame, [0, 10], [-100, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const opacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const logoLines = logo.split('\n');
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'flex-start', backgroundColor: 'transparent'}}>
      <div style={{display: 'flex', alignItems: 'stretch', marginBottom: '9%', marginLeft: '5%', opacity, transform: `translateX(${x}px)`, boxShadow: '0 4px 14px rgba(0,0,0,0.4)'}}>
        <div style={{background: logoBg, color: '#fff', fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, fontWeight: 900, fontSize: fontSize * 0.72, padding: '10px 18px', display: 'flex', flexDirection: 'column', justifyContent: 'center', lineHeight: 1.02, letterSpacing: '0.04em'}}>
          {logoLines.map((l, i) => <div key={i}>{l}</div>)}
        </div>
        <div style={{background: barBg, color: textColor, fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`, fontWeight: 900, fontSize, padding: '10px 28px', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap'}}>
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
