import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 레퍼런스급 데이터 카드: 프레임(코너 브래킷)이 그려지고 숫자가 0→값으로 카운트업.
// 짜깁기로는 못 만드는 계열 — 가격·할인율·평점·소요시간 전부 이 하나로.
export type CountCardProps = {
  label: string;   // 상단 모노스페이스 라벨 (예: "COOKING · 소요시간")
  value: number;   // 카운트업 도달값 (예: 5)
  suffix: string;  // 값 뒤 단위 (예: "분")
  accent?: string; // 강조색 (기본 라임)
  position?: 'top' | 'center' | 'bottom';
};

export const CountCard: React.FC<CountCardProps> = ({
  label, value, suffix, accent = '#c6f04a', position = 'center',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // 카드 등장: 살짝 아래에서 튕겨 올라오며 페이드.
  const enter = spring({frame, fps, config: {damping: 14, stiffness: 180, mass: 0.8}});
  const cardOpacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const cardY = interpolate(enter, [0, 1], [40, 0]);
  // 코너 브래킷이 그려지는 길이(0→1).
  const draw = interpolate(frame, [2, 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // 숫자 카운트업(0→value), ease-out.
  const countP = interpolate(frame, [6, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const eased = 1 - Math.pow(1 - countP, 3);
  const shown = Math.round(value * eased);
  // 글로우 맥동.
  const glow = 10 + 8 * Math.sin(frame / 6);

  const justify = position === 'top' ? 'flex-start' : position === 'bottom' ? 'flex-end' : 'center';
  const pad = position === 'top' ? {paddingTop: '12%'} : position === 'bottom' ? {paddingBottom: '14%'} : {};

  const bracket = (corner: string): React.CSSProperties => {
    const len = 34 * draw;
    const t = 4;
    const base: React.CSSProperties = {position: 'absolute', borderColor: accent, borderStyle: 'solid', borderWidth: 0};
    const v = {width: t, height: len};
    const h = {width: len, height: t};
    if (corner === 'tl') return {...base, top: -2, left: -2, borderTopWidth: t, borderLeftWidth: t, width: len, height: len, borderRightWidth: 0, borderBottomWidth: 0};
    if (corner === 'tr') return {...base, top: -2, right: -2, borderTopWidth: t, borderRightWidth: t, width: len, height: len};
    if (corner === 'bl') return {...base, bottom: -2, left: -2, borderBottomWidth: t, borderLeftWidth: t, width: len, height: len};
    return {...base, bottom: -2, right: -2, borderBottomWidth: t, borderRightWidth: t, width: len, height: len};
  };

  return (
    <AbsoluteFill style={{justifyContent: justify, alignItems: 'center', backgroundColor: 'transparent', ...pad}}>
      <div
        style={{
          position: 'relative',
          opacity: cardOpacity,
          transform: `translateY(${cardY}px)`,
          minWidth: 420,
          padding: '30px 40px 34px',
          background: 'rgba(6,10,4,0.82)',
          border: `1px solid ${accent}44`,
          boxShadow: `0 0 ${glow}px ${accent}55, inset 0 0 40px rgba(0,0,0,0.6)`,
          fontFamily: '"Malgun Gothic","맑은 고딕",system-ui,sans-serif',
        }}
      >
        {(['tl', 'tr', 'bl', 'br'] as const).map((c) => (
          <span key={c} style={bracket(c)} />
        ))}

        <div
          style={{
            fontFamily: '"Consolas","Courier New",monospace',
            fontSize: 22,
            letterSpacing: '0.22em',
            color: accent,
            textTransform: 'uppercase',
            marginBottom: 6,
            fontWeight: 700,
          }}
        >
          {label}
        </div>

        <div style={{display: 'flex', alignItems: 'flex-end', lineHeight: 0.9}}>
          <span
            style={{
              fontSize: 150,
              fontWeight: 900,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              fontVariantNumeric: 'tabular-nums',
              textShadow: '0 4px 22px rgba(0,0,0,0.7)',
            }}
          >
            {shown}
          </span>
          <span
            style={{
              fontSize: 64,
              fontWeight: 900,
              color: accent,
              marginLeft: 10,
              marginBottom: 14,
              textShadow: `0 0 18px ${accent}88`,
            }}
          >
            {suffix}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
