import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveTheme, Theme} from './theme';
import {Brackets} from './Brackets';

// 프레임 콜아웃 카드: 아이콘/로고 + 이름 + 태그가 옆에서 슬라이드로 진입. 색·모서리는 theme.
export type CalloutCardProps = {
  icon?: string; imageUrl?: string; name: string; tag: string;
  position?: 'top' | 'center' | 'bottom'; from?: 'left' | 'right'; theme?: string | Theme;
};

export const CalloutCard: React.FC<CalloutCardProps> = ({
  icon = '⭐', imageUrl, name, tag, position = 'center', from = 'right', theme,
}) => {
  const t = resolveTheme(theme);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const slide = spring({frame, fps, config: {damping: 15, stiffness: 190, mass: 0.9}});
  const dir = from === 'left' ? -1 : 1;
  const x = interpolate(slide, [0, 1], [dir * 420, 0]);
  const opacity = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
  const draw = interpolate(frame, [4, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const tagOpacity = interpolate(frame, [14, 24], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const glowR = 12 + 8 * Math.sin(frame / 7);

  const justify = position === 'top' ? 'flex-start' : position === 'bottom' ? 'flex-end' : 'center';
  const pad = position === 'top' ? {paddingTop: '13%'} : position === 'bottom' ? {paddingBottom: '15%'} : {};

  return (
    <AbsoluteFill style={{justifyContent: justify, alignItems: 'center', backgroundColor: 'transparent', ...pad}}>
      <div
        style={{
          position: 'relative', opacity, transform: `translateX(${x}px)`,
          display: 'flex', alignItems: 'center', gap: 22, padding: '22px 30px', minWidth: 440,
          background: t.cardBg, border: `1px solid ${t.border}`, borderRadius: t.radius,
          boxShadow: `0 0 ${glowR}px ${t.glow}, 0 10px 30px rgba(0,0,0,0.25)`, fontFamily: t.heading,
        }}
      >
        <Brackets theme={t} draw={draw} />
        <div
          style={{
            width: 92, height: 92, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: t.brackets ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
            border: `1px solid ${t.border}`, borderRadius: Math.max(8, t.radius - 6),
            fontSize: 54, overflow: 'hidden',
          }}
        >
          {imageUrl ? <img src={imageUrl} style={{width: '100%', height: '100%', objectFit: 'cover'}} /> : <span>{icon}</span>}
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 8}}>
          <span style={{fontSize: 52, fontWeight: 900, color: t.ink, letterSpacing: '-0.02em', lineHeight: 1}}>{name}</span>
          <span
            style={{
              opacity: tagOpacity,
              fontFamily: t.labelMono ? '"Consolas","Courier New",monospace' : t.heading,
              fontSize: 22, letterSpacing: t.labelMono ? '0.14em' : '0.02em', color: t.accent,
              textTransform: t.labelMono ? 'uppercase' : 'none', fontWeight: 700,
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
