import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 프레임 콜아웃 카드: 아이콘/로고 + 이름 + 태그가 옆에서 슬라이드로 진입(레퍼런스 Microsoft 카드).
// 제품·브랜드·핵심 포인트 강조용. 아이콘은 이모지 or 이미지 data URI.
export type CalloutCardProps = {
  icon?: string;      // 이모지(예: "🍓") — 로고 이미지 대체
  imageUrl?: string;  // 있으면 이모지 대신 이미지
  name: string;       // 큰 이름 (예: "딸기 풍선")
  tag: string;        // 하단 모노스페이스 태그 (예: "과학놀이 · DIY")
  accent?: string;
  position?: 'top' | 'center' | 'bottom';
  from?: 'left' | 'right';
};

export const CalloutCard: React.FC<CalloutCardProps> = ({
  icon = '⭐', imageUrl, name, tag, accent = '#c6f04a', position = 'center', from = 'right',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // 옆에서 미끄러져 들어와 살짝 튕김.
  const slide = spring({frame, fps, config: {damping: 15, stiffness: 190, mass: 0.9}});
  const dir = from === 'left' ? -1 : 1;
  const x = interpolate(slide, [0, 1], [dir * 420, 0]);
  const opacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const draw = interpolate(frame, [4, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // 태그는 카드가 자리잡은 뒤 페이드.
  const tagOpacity = interpolate(frame, [14, 24], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const glow = 12 + 8 * Math.sin(frame / 7);

  const justify = position === 'top' ? 'flex-start' : position === 'bottom' ? 'flex-end' : 'center';
  const pad = position === 'top' ? {paddingTop: '13%'} : position === 'bottom' ? {paddingBottom: '15%'} : {};

  const t = 4;
  const len = 34 * draw;
  const brackets = (['tl', 'tr', 'bl', 'br'] as const).map((c) => {
    const s: React.CSSProperties = {position: 'absolute', borderColor: accent, borderStyle: 'solid', width: len, height: len, borderWidth: 0};
    if (c === 'tl') return {...s, top: -2, left: -2, borderTopWidth: t, borderLeftWidth: t};
    if (c === 'tr') return {...s, top: -2, right: -2, borderTopWidth: t, borderRightWidth: t};
    if (c === 'bl') return {...s, bottom: -2, left: -2, borderBottomWidth: t, borderLeftWidth: t};
    return {...s, bottom: -2, right: -2, borderBottomWidth: t, borderRightWidth: t};
  });

  return (
    <AbsoluteFill style={{justifyContent: justify, alignItems: 'center', backgroundColor: 'transparent', ...pad}}>
      <div
        style={{
          position: 'relative',
          opacity,
          transform: `translateX(${x}px)`,
          display: 'flex',
          alignItems: 'center',
          gap: 22,
          padding: '22px 30px',
          minWidth: 440,
          background: 'rgba(6,10,4,0.85)',
          border: `1px solid ${accent}44`,
          boxShadow: `0 0 ${glow}px ${accent}55, inset 0 0 40px rgba(0,0,0,0.6)`,
          fontFamily: '"Malgun Gothic","맑은 고딕",system-ui,sans-serif',
        }}
      >
        {brackets.map((st, i) => <span key={i} style={st} />)}

        <div
          style={{
            width: 92, height: 92, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(255,255,255,0.06)',
            border: `1px solid ${accent}33`,
            borderRadius: 8,
            fontSize: 54,
            overflow: 'hidden',
          }}
        >
          {imageUrl
            ? <img src={imageUrl} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            : <span>{icon}</span>}
        </div>

        <div style={{display: 'flex', flexDirection: 'column', gap: 8}}>
          <span style={{fontSize: 52, fontWeight: 900, color: '#fff', letterSpacing: '-0.02em', lineHeight: 1}}>
            {name}
          </span>
          <span
            style={{
              opacity: tagOpacity,
              fontFamily: '"Consolas","Courier New",monospace',
              fontSize: 22,
              letterSpacing: '0.14em',
              color: accent,
              textTransform: 'uppercase',
              fontWeight: 700,
              display: 'flex', alignItems: 'center', gap: 8,
            }}
          >
            <span style={{fontSize: 16}}>▲</span>{tag}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
