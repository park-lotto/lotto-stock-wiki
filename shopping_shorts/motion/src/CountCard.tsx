import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveTheme, Theme} from './theme';
import {Brackets} from './Brackets';

// 카운트업 데이터 카드: 프레임 등장 + 숫자 0→값. 색·모서리·폰트는 theme에서.
export type CountCardProps = {
  label: string; value: number; suffix: string;
  position?: 'top' | 'center' | 'bottom'; theme?: string | Theme;
};

export const CountCard: React.FC<CountCardProps> = ({label, value, suffix, position = 'center', theme}) => {
  const t = resolveTheme(theme);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 14, stiffness: 180, mass: 0.8}});
  const cardOpacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const cardY = interpolate(enter, [0, 1], [40, 0]);
  const draw = interpolate(frame, [2, 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const countP = interpolate(frame, [6, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const shown = Math.round(value * (1 - Math.pow(1 - countP, 3)));
  const glowR = 10 + 8 * Math.sin(frame / 6);

  const justify = position === 'top' ? 'flex-start' : position === 'bottom' ? 'flex-end' : 'center';
  const pad = position === 'top' ? {paddingTop: '12%'} : position === 'bottom' ? {paddingBottom: '14%'} : {};

  return (
    <AbsoluteFill style={{justifyContent: justify, alignItems: 'center', backgroundColor: 'transparent', ...pad}}>
      <div
        style={{
          position: 'relative',
          opacity: cardOpacity,
          transform: `translateY(${cardY}px)`,
          minWidth: 420,
          padding: '30px 40px 34px',
          background: t.cardBg,
          border: `1px solid ${t.border}`,
          borderRadius: t.radius,
          boxShadow: `0 0 ${glowR}px ${t.glow}, 0 10px 30px rgba(0,0,0,0.25)`,
          fontFamily: t.heading,
        }}
      >
        <Brackets theme={t} draw={draw} />
        <div
          style={{
            fontFamily: t.labelMono ? '"Consolas","Courier New",monospace' : t.heading,
            fontSize: 22,
            letterSpacing: t.labelMono ? '0.22em' : '0.02em',
            color: t.label,
            textTransform: t.labelMono ? 'uppercase' : 'none',
            marginBottom: 6,
            fontWeight: 700,
          }}
        >
          {label}
        </div>
        <div style={{display: 'flex', alignItems: 'flex-end', lineHeight: 0.9}}>
          <span style={{fontSize: 150, fontWeight: 900, color: t.ink, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums'}}>
            {shown}
          </span>
          <span style={{fontSize: 64, fontWeight: 900, color: t.accent, marginLeft: 10, marginBottom: 14, textShadow: `0 0 18px ${t.glow}`}}>
            {suffix}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
