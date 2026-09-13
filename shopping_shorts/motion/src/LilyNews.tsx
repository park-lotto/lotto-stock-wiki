import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 뉴스 자막 모음(#4 ver2~6). variant 로 버전을 나눔.
//  'anchor'(ver2): 이름표+직함 탭 + 파란 하단 박스 본문(앵커/인터뷰)
//  'headline'(ver3): 위 회색 소제목 + 아래 큰 흰 본문(2줄 헤드라인)
//  'silver'(ver4): 은색 그라데이션 바 안 한 줄(속보 타이틀)
//  'label'(ver5): 파란 라벨 탭 + 흰 본문 밑줄(코너/의견)
//  'profile'(ver6): 좌측 원형 프로필 + 우측 직함(작게)+이름(크게) 로워서드
export type LilyNewsProps = {
  variant: 'anchor' | 'headline' | 'silver' | 'label' | 'profile';
  title?: string;       // 소제목/직함/라벨/상단줄
  text: string;         // 본문/이름
  color?: string;       // 강조색(파랑 등)
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

export const LilyNews: React.FC<LilyNewsProps> = ({
  variant,
  title = '',
  text,
  color = '#2f6fd0',
  fontFamily = 'TmonMonsori',
  fontSize = 50,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const slide = interpolate(frame, [0, 12], [-36, 0], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '16%' : position === 'bottom' ? '68%' : '40%';
  const ff = `"${fontFamily}", "Malgun Gothic", sans-serif`;
  const estW = text.length * fontSize * 0.62 + 200;
  const fit = Math.min(1, (width * 0.92) / estW);
  const wrap = (child: React.ReactNode) => (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `translateX(${slide}px) scale(${fit})`, transformOrigin: 'center', fontFamily: ff}}>{child}</div>
    </AbsoluteFill>
  );

  if (variant === 'anchor') {
    return wrap(
      <div>
        <div style={{marginLeft: 20, marginBottom: -2, position: 'relative', zIndex: 2, display: 'flex', gap: 8, alignItems: 'flex-end'}}>
          <span style={{background: color, color: '#fff', fontWeight: 700, fontSize: fontSize * 0.5, padding: '4px 16px', clipPath: 'polygon(0 0,100% 0,90% 100%,0 100%)', whiteSpace: 'nowrap'}}>{title.split('|')[0] || title}</span>
          {title.includes('|') ? <span style={{color: '#cfe0f5', fontSize: fontSize * 0.4, paddingBottom: 4}}>{title.split('|')[1]}</span> : null}
        </div>
        <div style={{background: `linear-gradient(180deg, ${color} 0%, ${color}dd 100%)`, padding: '18px 40px', minWidth: width * 0.66, boxShadow: '0 6px 18px rgba(0,0,0,0.45)'}}>
          <span style={{color: '#fff', fontWeight: 600, fontSize, whiteSpace: 'nowrap'}}>{text}</span>
        </div>
      </div>
    );
  }

  if (variant === 'headline') {
    return wrap(
      <div style={{textAlign: 'left'}}>
        {title ? <div style={{color: '#9fb4cc', fontWeight: 600, fontSize: fontSize * 0.6, marginBottom: 8, letterSpacing: '0.02em'}}>{title}</div> : null}
        <div style={{color: '#f4f4f4', fontWeight: 900, fontSize: fontSize * 1.25, whiteSpace: 'nowrap', textShadow: '0 3px 10px rgba(0,0,0,0.7)'}}>{text}</div>
      </div>
    );
  }

  if (variant === 'silver') {
    return wrap(
      <div style={{background: 'linear-gradient(180deg,#f2f2f2 0%,#c9c9c9 48%,#9a9a9a 52%,#dcdcdc 100%)', padding: '14px 46px', borderRadius: 4, boxShadow: '0 5px 16px rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.6)'}}>
        <span style={{color: '#222', fontWeight: 900, fontSize, whiteSpace: 'nowrap', textShadow: '0 1px 0 rgba(255,255,255,0.7)'}}>{text}</span>
      </div>
    );
  }

  if (variant === 'label') {
    return wrap(
      <div style={{textAlign: 'left'}}>
        {title ? <div style={{display: 'inline-block', background: `linear-gradient(100deg,${color},${color}bb)`, color: '#fff', fontWeight: 700, fontSize: fontSize * 0.5, padding: '5px 18px', clipPath: 'polygon(0 0,100% 0,92% 100%,0 100%)', marginBottom: 8}}>{title}</div> : null}
        <div style={{position: 'relative', display: 'inline-block', paddingBottom: 6}}>
          <div style={{color: '#f4f4f4', fontWeight: 900, fontSize: fontSize * 1.15, whiteSpace: 'nowrap', textShadow: '0 3px 10px rgba(0,0,0,0.7)'}}>{text}</div>
          <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 4, background: color, borderRadius: 2}} />
        </div>
      </div>
    );
  }

  // profile: 원형 + 직함/이름
  return wrap(
    <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
      <div style={{width: fontSize * 2.6, height: fontSize * 2.6, borderRadius: '50%', background: 'linear-gradient(180deg,#fff,#d8d8d8)', boxShadow: '0 4px 14px rgba(0,0,0,0.4)', flexShrink: 0, border: '3px solid rgba(255,255,255,0.7)'}} />
      <div style={{textAlign: 'left'}}>
        {title ? <div style={{color: '#bcd0ea', fontWeight: 600, fontSize: fontSize * 0.55, marginBottom: 4}}>{title}</div> : null}
        <div style={{color: color, fontWeight: 900, fontSize: fontSize * 1.2, whiteSpace: 'nowrap', textShadow: '0 3px 10px rgba(0,0,0,0.6)'}}>{text}</div>
      </div>
    </div>
  );
};
