import { useCurrentFrame, interpolate } from 'remotion';
import { FONT } from '../theme';

interface Props {
  to: number;
  from?: number;
  startFrame: number;
  endFrame: number;
  prefix?: string;
  suffix?: string;
  fontSize?: number;
  color?: string;
}

export const CountUp: React.FC<Props> = ({
  to,
  from = 0,
  startFrame,
  endFrame,
  prefix = '',
  suffix = '',
  fontSize = 100,
  color = '#FFFFFF',
}) => {
  const frame = useCurrentFrame();

  const value = interpolate(frame, [startFrame, endFrame], [from, to], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (t) => 1 - Math.pow(1 - t, 3), // ease-out cubic: 처음엔 빠르게, 끝에서 천천히
  });

  const formatted = Math.round(value).toLocaleString('ko-KR');

  return (
    <span style={{ fontFamily: FONT.mono, fontSize, fontWeight: 700, color }}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
};
