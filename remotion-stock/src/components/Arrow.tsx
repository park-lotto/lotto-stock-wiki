import { C } from '../constants';

interface ArrowProps {
  size?: number;
  color?: string;
  opacity?: number;
}

export const Arrow = ({ size = 48, color = C.main, opacity = 1 }: ArrowProps) => (
  <svg
    width={size}
    height={size * 0.45}
    viewBox="0 0 48 22"
    style={{ opacity, flexShrink: 0 }}
  >
    <path
      d="M2 11 L38 11 M28 3 L38 11 L28 19"
      stroke={color}
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
  </svg>
);
