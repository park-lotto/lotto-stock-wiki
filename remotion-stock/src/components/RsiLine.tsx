import { useCurrentFrame, interpolate } from 'remotion';
import { COLORS } from '../theme';

// 위 캔들 10개에 대응하는 RSI 값
const RSI_DATA = [42, 45, 38, 52, 58, 62, 65, 61, 55, 48];

const W = 900;
const H = 140;
const PAD_X = 40;
const PAD_Y = 15;
const MIN_RSI = 20;
const MAX_RSI = 80;

const toY = (rsi: number) =>
  PAD_Y + ((MAX_RSI - rsi) / (MAX_RSI - MIN_RSI)) * (H - PAD_Y * 2);

const SLOT = (W - PAD_X * 2) / (RSI_DATA.length - 1);

// 전체 폴리라인의 근사 길이 계산
const getPathLength = () => {
  let len = 0;
  for (let i = 1; i < RSI_DATA.length; i++) {
    const dx = SLOT;
    const dy = toY(RSI_DATA[i]) - toY(RSI_DATA[i - 1]);
    len += Math.sqrt(dx * dx + dy * dy);
  }
  return len;
};

const PATH_LENGTH = getPathLength();

export const RsiLine: React.FC = () => {
  const frame = useCurrentFrame();

  // 80프레임에 걸쳐 라인 그리기
  const progress = interpolate(frame, [10, 90], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const dashOffset = PATH_LENGTH * (1 - progress);

  const points = RSI_DATA.map((rsi, i) => {
    const x = PAD_X + i * SLOT;
    const y = toY(rsi);
    return `${x},${y}`;
  }).join(' ');

  // 과매수/과매도 기준선
  const overBoughtY = toY(70);
  const overSoldY = toY(30);

  return (
    <div>
      <div style={{ color: COLORS.orange, fontSize: 26, fontWeight: 700, marginBottom: 8 }}>
        RSI (14)
      </div>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        {/* 과매수 70 라인 */}
        <line x1={PAD_X} y1={overBoughtY} x2={W - PAD_X} y2={overBoughtY}
          stroke={COLORS.bull} strokeWidth={1} strokeDasharray="6 4" opacity={0.5} />
        <text x={W - PAD_X + 4} y={overBoughtY + 5} fill={COLORS.bull} fontSize={18} opacity={0.6}>70</text>

        {/* 과매도 30 라인 */}
        <line x1={PAD_X} y1={overSoldY} x2={W - PAD_X} y2={overSoldY}
          stroke={COLORS.bear} strokeWidth={1} strokeDasharray="6 4" opacity={0.5} />
        <text x={W - PAD_X + 4} y={overSoldY + 5} fill={COLORS.bear} fontSize={18} opacity={0.6}>30</text>

        {/* RSI 라인 — 프레임마다 strokeDashoffset 업데이트로 그리기 효과 */}
        <polyline
          points={points}
          fill="none"
          stroke={COLORS.orange}
          strokeWidth={3}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={PATH_LENGTH}
          strokeDashoffset={dashOffset}
        />

        {/* 현재 RSI 값 점 */}
        {progress > 0.9 && (
          <circle
            cx={PAD_X + (RSI_DATA.length - 1) * SLOT}
            cy={toY(RSI_DATA[RSI_DATA.length - 1])}
            r={7}
            fill={COLORS.orange}
          />
        )}
      </svg>

      <div style={{ color: COLORS.textDim, fontSize: 22, marginTop: 4 }}>
        현재 RSI{' '}
        <span style={{ color: COLORS.orange, fontWeight: 700 }}>
          {RSI_DATA[RSI_DATA.length - 1]}
        </span>
        {' '}— 중립 구간, 상승 여지 있음
      </div>
    </div>
  );
};
