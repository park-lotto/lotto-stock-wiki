import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveTheme, Theme} from './theme';
import {Brackets} from './Brackets';

// TOP 리스트 리빌: 항목이 한 줄씩 스태거로 슬라이드·페이드. 색·모서리·폰트는 theme.
export type ListRevealProps = {
  title: string; items: string[];
  position?: 'top' | 'center' | 'bottom'; theme?: string | Theme;
};

export const ListReveal: React.FC<ListRevealProps> = ({title, items, position = 'center', theme}) => {
  const t = resolveTheme(theme);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const cardIn = spring({frame, fps, config: {damping: 16, stiffness: 170, mass: 0.9}});
  const cardOpacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const cardY = interpolate(cardIn, [0, 1], [36, 0]);
  const draw = interpolate(frame, [2, 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const justify = position === 'top' ? 'flex-start' : position === 'bottom' ? 'flex-end' : 'center';
  const pad = position === 'top' ? {paddingTop: '12%'} : position === 'bottom' ? {paddingBottom: '14%'} : {};
  const ROW_START = 10, STAGGER = 6;

  return (
    <AbsoluteFill style={{justifyContent: justify, alignItems: 'center', backgroundColor: 'transparent', ...pad}}>
      <div
        style={{
          position: 'relative', opacity: cardOpacity, transform: `translateY(${cardY}px)`,
          minWidth: 520, padding: '26px 34px 30px',
          background: t.cardBg, border: `1px solid ${t.border}`, borderRadius: t.radius,
          boxShadow: `0 0 16px ${t.glow}, 0 10px 30px rgba(0,0,0,0.25)`, fontFamily: t.heading,
        }}
      >
        <Brackets theme={t} draw={draw} />
        <div
          style={{
            fontFamily: t.labelMono ? '"Consolas","Courier New",monospace' : t.heading,
            fontSize: 22, letterSpacing: t.labelMono ? '0.2em' : '0.02em', color: t.label,
            textTransform: t.labelMono ? 'uppercase' : 'none', fontWeight: 700,
            marginBottom: 18, borderBottom: `1px solid ${t.border}`, paddingBottom: 12,
          }}
        >
          {title}
        </div>
        {items.map((it, i) => {
          const t0 = ROW_START + i * STAGGER;
          const p = interpolate(frame, [t0, t0 + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const x = interpolate(p, [0, 1], [-34, 0]);
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 18, padding: '9px 0', opacity: p, transform: `translateX(${x}px)`}}>
              <span style={{fontFamily: t.labelMono ? '"Consolas","Courier New",monospace' : t.heading, fontSize: 26, fontWeight: 800, color: t.accent, minWidth: 42, textShadow: `0 0 12px ${t.glow}`}}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <span style={{fontSize: 40, fontWeight: 800, color: t.ink, letterSpacing: '-0.02em'}}>{it}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
