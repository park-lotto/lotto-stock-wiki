import { AbsoluteFill, Sequence, useCurrentFrame, interpolate } from 'remotion';
import { COLORS, FONT, STAGE } from './theme';
import { CountUp } from './components/CountUp';
import { CandlestickChart } from './components/CandlestickChart';
import { RsiLine } from './components/RsiLine';
import { MetricCard } from './components/MetricCard';

// ─────────────────────────────────────────
// Stage 1: 도입 (0~90프레임 / 3초) — 민트 테마
// ─────────────────────────────────────────
const Stage1: React.FC = () => {
  const frame = useCurrentFrame();

  const channelOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const titleOpacity   = interpolate(frame, [8, 28], [0, 1], { extrapolateRight: 'clamp' });
  const titleY         = interpolate(frame, [8, 28], [30, 0], { extrapolateRight: 'clamp' });
  const subOpacity     = interpolate(frame, [20, 38], [0, 1], { extrapolateRight: 'clamp' });
  const lineW          = interpolate(frame, [30, 55], [0, 100], { extrapolateRight: 'clamp' });
  const priceOpacity   = interpolate(frame, [38, 55], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        padding: '120px 80px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 28,
      }}
    >
      {/* 채널명 */}
      <div
        style={{
          opacity: channelOpacity,
          color: COLORS.mint,
          fontFamily: FONT.mono,
          fontSize: 32,
          letterSpacing: 4,
          fontWeight: 400,
        }}
      >
        📈 로또의 주식
      </div>

      {/* 종목명 */}
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          color: COLORS.text,
          fontFamily: FONT.main,
          fontSize: 110,
          fontWeight: 900,
          lineHeight: 1,
        }}
      >
        삼성전자
      </div>

      {/* 서브타이틀 */}
      <div
        style={{
          opacity: subOpacity,
          color: COLORS.mint,
          fontFamily: FONT.main,
          fontSize: 44,
          fontWeight: 500,
        }}
      >
        급등 분석 리포트
      </div>

      {/* 구분선 (왼쪽에서 오른쪽으로 그려짐) */}
      <div style={{ width: '100%', height: 2, backgroundColor: COLORS.grid }}>
        <div
          style={{
            width: `${lineW}%`,
            height: '100%',
            backgroundColor: COLORS.mint,
          }}
        />
      </div>

      {/* 현재가 카운트업 */}
      <div style={{ opacity: priceOpacity, marginTop: 20 }}>
        <div
          style={{
            color: COLORS.textDim,
            fontFamily: FONT.main,
            fontSize: 30,
            marginBottom: 12,
            letterSpacing: 2,
          }}
        >
          현재가
        </div>
        <CountUp
          to={70500}
          startFrame={45}
          endFrame={85}
          suffix="원"
          fontSize={108}
          color={COLORS.text}
        />
      </div>

      {/* 하단 날짜/출처 */}
      <div
        style={{
          position: 'absolute',
          bottom: 80,
          left: 80,
          right: 80,
          color: COLORS.textDim,
          fontFamily: FONT.mono,
          fontSize: 22,
          opacity: subOpacity,
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>KRX · Bloomberg Terminal</span>
        <span>2026.05.17</span>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────
// Stage 2: 분석 (90~210프레임 / 4초) — 주황 테마
// ─────────────────────────────────────────
const Stage2: React.FC = () => {
  const frame = useCurrentFrame();

  const headerOpacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const chartOpacity  = interpolate(frame, [10, 28], [0, 1], { extrapolateRight: 'clamp' });
  const rsiOpacity    = interpolate(frame, [85, 100], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        padding: '80px 60px',
        display: 'flex',
        flexDirection: 'column',
        gap: 32,
      }}
    >
      {/* 헤더 */}
      <div style={{ opacity: headerOpacity }}>
        <div
          style={{
            color: COLORS.orange,
            fontFamily: FONT.mono,
            fontSize: 28,
            letterSpacing: 3,
            marginBottom: 8,
          }}
        >
          TECHNICAL ANALYSIS
        </div>
        <div
          style={{
            color: COLORS.text,
            fontFamily: FONT.main,
            fontSize: 52,
            fontWeight: 700,
          }}
        >
          기술적 분석
        </div>
      </div>

      {/* 캔들차트 */}
      <div style={{ opacity: chartOpacity }}>
        <div
          style={{
            color: COLORS.textDim,
            fontFamily: FONT.main,
            fontSize: 24,
            marginBottom: 12,
          }}
        >
          주가 흐름 (10일)
        </div>
        <CandlestickChart />

        {/* 범례 */}
        <div style={{ display: 'flex', gap: 32, marginTop: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 20, height: 20, backgroundColor: COLORS.bull, borderRadius: 4 }} />
            <span style={{ color: COLORS.textDim, fontFamily: FONT.main, fontSize: 22 }}>양봉</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 20, height: 20, backgroundColor: COLORS.bear, borderRadius: 4 }} />
            <span style={{ color: COLORS.textDim, fontFamily: FONT.main, fontSize: 22 }}>음봉</span>
          </div>
        </div>
      </div>

      {/* RSI 라인차트 */}
      <div style={{ opacity: rsiOpacity }}>
        <RsiLine />
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────
// Stage 3: 결론 (210~300프레임 / 3초) — 빨강/파랑 테마
// ─────────────────────────────────────────
const Stage3: React.FC = () => {
  const frame = useCurrentFrame();

  const headerOpacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const disclaimerOpacity = interpolate(frame, [55, 72], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        padding: '100px 80px',
        display: 'flex',
        flexDirection: 'column',
        gap: 40,
      }}
    >
      {/* 헤더 */}
      <div style={{ opacity: headerOpacity }}>
        <div
          style={{
            color: COLORS.textDim,
            fontFamily: FONT.mono,
            fontSize: 28,
            letterSpacing: 3,
            marginBottom: 8,
          }}
        >
          CONCLUSION
        </div>
        <div
          style={{
            color: COLORS.text,
            fontFamily: FONT.main,
            fontSize: 52,
            fontWeight: 700,
          }}
        >
          분석 결론
        </div>
      </div>

      {/* 목표가 카드 (빨강) */}
      <MetricCard
        label="목표가"
        value={85000}
        suffix="원"
        accentColor={COLORS.bull}
        startFrame={12}
        description="+20.6% 상승 여지 · 저항선 73K 돌파 시 유효"
      />

      {/* 손절매 카드 (파랑) */}
      <MetricCard
        label="손절매"
        value={65000}
        suffix="원"
        accentColor={COLORS.bear}
        startFrame={30}
        description="-7.8% · 지지선 이탈 시 즉시 대응"
      />

      {/* 면책조항 */}
      <div
        style={{
          opacity: disclaimerOpacity,
          backgroundColor: 'rgba(255,255,255,0.04)',
          border: `1px solid ${COLORS.grid}`,
          borderRadius: 12,
          padding: '28px 36px',
        }}
      >
        <div
          style={{
            color: COLORS.textDim,
            fontFamily: FONT.main,
            fontSize: 22,
            lineHeight: 1.7,
          }}
        >
          ⚠️ 본 영상은 정보 제공 목적이며, 투자 조언이 아닙니다.
          <br />
          모든 투자 판단과 책임은 본인에게 있습니다.
          <br />
          출처: KRX · Bloomberg Terminal · 재무제표.com
        </div>
      </div>

      {/* 채널 워터마크 */}
      <div
        style={{
          opacity: disclaimerOpacity,
          position: 'absolute',
          bottom: 80,
          right: 80,
          color: COLORS.mint,
          fontFamily: FONT.mono,
          fontSize: 26,
          letterSpacing: 2,
        }}
      >
        @로또의 주식
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────
// 메인 컴포지션 — 배경 + 스테이지 전환
// ─────────────────────────────────────────
export const MyComposition: React.FC = () => {
  const frame = useCurrentFrame();

  // 스테이지별 배경 강조색 (왼쪽 사이드 바) 전환
  const accentColor =
    frame < STAGE.s1End
      ? COLORS.mint
      : frame < STAGE.s2End
        ? COLORS.orange
        : COLORS.bull;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, fontFamily: FONT.main }}>
      {/* 왼쪽 스테이지 인디케이터 바 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: 8,
          backgroundColor: accentColor,
        }}
      />

      {/* Stage 1: 도입 */}
      <Sequence from={STAGE.s1Start} durationInFrames={STAGE.s1End - STAGE.s1Start}>
        <Stage1 />
      </Sequence>

      {/* Stage 2: 분석 */}
      <Sequence from={STAGE.s1End} durationInFrames={STAGE.s2End - STAGE.s1End}>
        <Stage2 />
      </Sequence>

      {/* Stage 3: 결론 */}
      <Sequence from={STAGE.s2End} durationInFrames={STAGE.s3End - STAGE.s2End}>
        <Stage3 />
      </Sequence>
    </AbsoluteFill>
  );
};
