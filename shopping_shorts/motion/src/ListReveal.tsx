import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// TOP 리스트 리빌: 항목이 한 줄씩 스태거로 슬라이드·페이드 등장(레퍼런스 GLOBAL TOP10).
// 애니메이션이 핵심 — 각 행이 시차를 두고 왼쪽에서 밀려들어온다.
export type ListRevealProps = {
  title: string;      // 상단 라벨 (예: "준비물 · READY")
  items: string[];    // 항목들
  accent?: string;
  position?: 'top' | 'center' | 'bottom';
};

export const ListReveal: React.FC<ListRevealProps> = ({
  title, items, accent = '#c6f04a', position = 'center',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const cardIn = spring({frame, fps, config: {damping: 16, stiffness: 170, mass: 0.9}});
  const cardOpacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const cardY = interpolate(cardIn, [0, 1], [36, 0]);
  const draw = interpolate(frame, [2, 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const justify = position === 'top' ? 'flex-start' : position === 'bottom' ? 'flex-end' : 'center';
  const pad = position === 'top' ? {paddingTop: '12%'} : position === 'bottom' ? {paddingBottom: '14%'} : {};

  const ROW_START = 10;   // 첫 행 등장 프레임
  const STAGGER = 6;      // 행 간 시차

  const bracketLen = 34 * draw;
  const brackets = (['tl', 'tr', 'bl', 'br'] as const).map((c) => {
    const t = 4;
    const s: React.CSSProperties = {position: 'absolute', borderColor: accent, borderStyle: 'solid', width: bracketLen, height: bracketLen, borderWidth: 0};
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
          opacity: cardOpacity,
          transform: `translateY(${cardY}px)`,
          minWidth: 520,
          padding: '26px 34px 30px',
          background: 'rgba(6,10,4,0.84)',
          border: `1px solid ${accent}40`,
          boxShadow: `0 0 16px ${accent}44, inset 0 0 40px rgba(0,0,0,0.6)`,
          fontFamily: '"Malgun Gothic","맑은 고딕",system-ui,sans-serif',
        }}
      >
        {brackets.map((st, i) => <span key={i} style={st} />)}

        <div
          style={{
            fontFamily: '"Consolas","Courier New",monospace',
            fontSize: 22,
            letterSpacing: '0.2em',
            color: accent,
            textTransform: 'uppercase',
            fontWeight: 700,
            marginBottom: 18,
            borderBottom: `1px solid ${accent}33`,
            paddingBottom: 12,
          }}
        >
          {title}
        </div>

        {items.map((it, i) => {
          const t0 = ROW_START + i * STAGGER;
          const p = interpolate(frame, [t0, t0 + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const x = interpolate(p, [0, 1], [-34, 0]);
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 18,
                padding: '9px 0',
                opacity: p,
                transform: `translateX(${x}px)`,
              }}
            >
              <span
                style={{
                  fontFamily: '"Consolas","Courier New",monospace',
                  fontSize: 26,
                  fontWeight: 700,
                  color: accent,
                  minWidth: 42,
                  textShadow: `0 0 12px ${accent}66`,
                }}
              >
                {String(i + 1).padStart(2, '0')}
              </span>
              <span style={{fontSize: 40, fontWeight: 800, color: '#fff', letterSpacing: '-0.02em'}}>
                {it}
              </span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
