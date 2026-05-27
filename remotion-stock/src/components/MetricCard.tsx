import { useCurrentFrame, interpolate } from 'remotion';
import { COLORS, FONT } from '../theme';

interface Props {
  label: string;
  value: number;
  suffix?: string;
  accentColor: string;
  startFrame: number;
  description?: string;
}

export const MetricCard: React.FC<Props> = ({
  label,
  value,
  suffix = '원',
  accentColor,
  startFrame,
  description,
}) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [startFrame, startFrame + 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const translateY = interpolate(frame, [startFrame, startFrame + 20], [40, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const countedValue = interpolate(frame, [startFrame + 5, startFrame + 40], [0, value], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (t) => 1 - Math.pow(1 - t, 3),
  });

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${translateY}px)`,
        backgroundColor: COLORS.card,
        border: `2px solid ${accentColor}`,
        borderRadius: 20,
        padding: '44px 60px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {/* 색상 바 */}
      <div style={{ width: 60, height: 6, backgroundColor: accentColor, borderRadius: 3 }} />

      {/* 라벨 */}
      <div style={{ color: COLORS.textDim, fontFamily: FONT.main, fontSize: 30, fontWeight: 500 }}>
        {label}
      </div>

      {/* 수치 */}
      <div style={{ color: accentColor, fontFamily: FONT.mono, fontSize: 80, fontWeight: 700, lineHeight: 1 }}>
        {Math.round(countedValue).toLocaleString('ko-KR')}
        <span style={{ fontSize: 36, marginLeft: 8 }}>{suffix}</span>
      </div>

      {/* 설명 */}
      {description && (
        <div style={{ color: COLORS.textDim, fontFamily: FONT.main, fontSize: 24 }}>
          {description}
        </div>
      )}
    </div>
  );
};
