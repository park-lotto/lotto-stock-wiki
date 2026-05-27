import { useCurrentFrame, interpolate } from 'remotion';
import { COLORS } from '../theme';

// 삼성전자 스타일 샘플 캔들 데이터 (원 단위)
const CANDLES = [
  { o: 62000, h: 64500, l: 61000, c: 63800 },
  { o: 63800, h: 65200, l: 63200, c: 64500 },
  { o: 64500, h: 65800, l: 63800, c: 63200 }, // 음봉
  { o: 63200, h: 65000, l: 62800, c: 64800 },
  { o: 64800, h: 67200, l: 64200, c: 66800 },
  { o: 66800, h: 68500, l: 66200, c: 67500 },
  { o: 67500, h: 70200, l: 67200, c: 69800 },
  { o: 69800, h: 71500, l: 69200, c: 71200 },
  { o: 71200, h: 72800, l: 70800, c: 70500 }, // 음봉
  { o: 70500, h: 73500, l: 70200, c: 72800 },
];

const MIN_PRICE = 60000;
const MAX_PRICE = 75500;
const W = 900;
const H = 360;
const PAD_X = 40;
const PAD_Y = 20;
const CANDLE_W = 52;
const SLOT = (W - PAD_X * 2) / CANDLES.length;

const toY = (price: number) =>
  PAD_Y + ((MAX_PRICE - price) / (MAX_PRICE - MIN_PRICE)) * (H - PAD_Y * 2);

export const CandlestickChart: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      {/* 가격 그리드 라인 */}
      {[62000, 65000, 68000, 71000, 74000].map((price) => (
        <line
          key={price}
          x1={PAD_X}
          y1={toY(price)}
          x2={W - PAD_X}
          y2={toY(price)}
          stroke={COLORS.grid}
          strokeWidth={1}
        />
      ))}

      {/* 캔들 */}
      {CANDLES.map((c, i) => {
        const isBull = c.c >= c.o;
        const color = isBull ? COLORS.bull : COLORS.bear;
        const cx = PAD_X + i * SLOT + SLOT / 2;

        // 각 캔들이 10프레임 간격으로 순서대로 등장
        const startF = i * 10;
        const progress = interpolate(frame, [startF, startF + 15], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });

        if (progress === 0) return null;

        const highY = toY(c.h);
        const lowY = toY(c.l);
        const openY = toY(c.o);
        const closeY = toY(c.c);

        // 몸통: 중심에서 위아래로 성장
        const bodyMidY = (openY + closeY) / 2;
        const fullHalf = Math.max(2, Math.abs(openY - closeY) / 2);
        const animHalf = fullHalf * progress;

        return (
          <g key={i} opacity={progress}>
            {/* 위 꼬리 (wick) */}
            <line
              x1={cx} y1={highY}
              x2={cx} y2={bodyMidY - animHalf}
              stroke={color}
              strokeWidth={2.5}
            />
            {/* 아래 꼬리 (wick) */}
            <line
              x1={cx} y1={bodyMidY + animHalf}
              x2={cx} y2={lowY}
              stroke={color}
              strokeWidth={2.5}
            />
            {/* 몸통 (body) */}
            <rect
              x={cx - CANDLE_W / 2}
              y={bodyMidY - animHalf}
              width={CANDLE_W}
              height={animHalf * 2}
              fill={color}
              rx={4}
            />
          </g>
        );
      })}
    </svg>
  );
};
