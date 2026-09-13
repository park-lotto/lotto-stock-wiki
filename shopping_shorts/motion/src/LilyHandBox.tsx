import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

// 릴리리아 손그림 라벨박스(#38 ver7/8): 삐뚤삐뚤 손그림 테두리 박스 안에
// 인용 본문 2줄 + 위쪽에 하트. 분홍/파랑 등 색 변형.
// text(줄바꿈은 \n) / bg / 만 바꾸면 같은 스타일.
export type LilyHandBoxProps = {
  text: string;         // \n 으로 2줄
  bg?: string;          // 박스 배경색
  textColor?: string;
  heart?: string;       // 하트 색(빈 문자열이면 숨김)
  fontFamily?: string;
  fontSize?: number;
  position?: 'top' | 'mid' | 'bottom';
};

// 손그림 느낌: 모서리마다 살짝 다른 border-radius + 미세 회전.
export const LilyHandBox: React.FC<LilyHandBoxProps> = ({
  text,
  bg = '#e59ab0',
  textColor = '#ffffff',
  heart = '#e0466a',
  fontFamily = 'TmonMonsori',
  fontSize = 52,
  position = 'mid',
}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const pop = interpolate(frame, [0, 7, 12], [0.7, 1.06, 1], {extrapolateRight: 'clamp'});
  const opacity = interpolate(frame, [0, 7], [0, 1], {extrapolateRight: 'clamp'});
  const marginTop = position === 'top' ? '14%' : position === 'bottom' ? '64%' : '38%';
  // 개행은 실제 \n 또는 리터럴 "\n"(JSON 이스케이프 잔재) 둘 다 허용
  const lines = text.split(/\\n|\n/);
  const longest = Math.max(...lines.map((l) => l.length));
  const estW = longest * fontSize * 0.62 + 130;
  const fit = Math.min(1, (width * 0.8) / estW);
  // 하트 통통 튀는 등장
  const heartY = interpolate(frame, [2, 9, 14], [10, -6, 0], {extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div style={{marginTop, opacity, transform: `scale(${fit * pop}) rotate(-1.2deg)`, position: 'relative'}}>
        {heart ? (
          <div style={{position: 'absolute', top: -fontSize * 0.7, left: -fontSize * 0.2, fontSize: fontSize * 0.8, color: heart, transform: `translateY(${heartY}px) rotate(-12deg)`, filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.25))'}}>♥</div>
        ) : null}
        <div
          style={{
            background: bg,
            // 손그림: 모서리 4개 반경을 서로 다르게
            borderRadius: '255px 15px 225px 15px / 15px 225px 15px 255px',
            padding: '22px 44px',
            boxShadow: '0 8px 22px rgba(0,0,0,0.28)',
            border: '3px solid rgba(255,255,255,0.35)',
            textAlign: 'center',
            fontFamily: `"${fontFamily}", "Malgun Gothic", sans-serif`,
          }}
        >
          {lines.map((l, i) => (
            <div key={i} style={{color: textColor, fontWeight: 800, fontSize, lineHeight: 1.3, textShadow: '0 2px 6px rgba(0,0,0,0.25)', whiteSpace: 'nowrap'}}>{l}</div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
