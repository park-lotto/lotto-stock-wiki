import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveTheme, Theme} from './theme';

// 임팩트 텍스트: 강조어가 테마 색으로 화면에 슬램(튕기며 등장).
// 색·외곽선은 theme에서 오므로 카드들과 톤이 통일된다(이질감 제거).
export type ImpactTextProps = {word: string; position?: 'top' | 'bottom'; theme?: string | Theme};

export const ImpactText: React.FC<ImpactTextProps> = ({word, position = 'top', theme}) => {
  const t = resolveTheme(theme);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 10, stiffness: 220, mass: 0.7}});
  const scale = interpolate(enter, [0, 1], [0.4, 1]);
  const rot = interpolate(enter, [0, 1], [-6, 0]);
  const opacity = interpolate(frame, [0, 4], [0, 1], {extrapolateRight: 'clamp'});
  const marginTop = position === 'bottom' ? '76%' : '10%';
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          maxWidth: '86%',
          textAlign: 'center',
          fontFamily: t.heading,
          fontWeight: 900,
          fontSize: 92,
          lineHeight: 1.1,
          letterSpacing: '-0.03em',
          wordBreak: 'keep-all',
          opacity,
          transform: `scale(${scale}) rotate(${rot}deg)`,
          backgroundImage: `linear-gradient(180deg, ${t.impactTop}, ${t.accent})`,
          WebkitBackgroundClip: 'text',
          backgroundClip: 'text',
          color: 'transparent',
          WebkitTextStroke: `3px ${t.impactStroke}`,
          paintOrder: 'stroke fill',
          textShadow: `0 4px 18px rgba(0,0,0,0.55), 0 0 34px ${t.glow}, 0 0 64px ${t.glow}`,
        }}
      >
        {word}
      </div>
    </AbsoluteFill>
  );
};
