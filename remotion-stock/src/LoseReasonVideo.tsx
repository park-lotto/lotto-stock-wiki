import React from 'react';
import { AbsoluteFill, Series, useCurrentFrame, interpolate, Easing } from 'remotion';
import { C, GLOW, FONT } from './constants';
import { FadeWrapper } from './components/FadeWrapper';

const SCENE_DUR = 360;
export const LOSE_REASON_FRAMES = SCENE_DUR * 28;

const fi = (f: number, s: number, d = 20) =>
  interpolate(f, [s, s + d], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const slideY = (f: number, s: number, dist = 60, d = 22) =>
  interpolate(f, [s, s + d], [dist, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

const slideX = (f: number, s: number, dist = 80, d = 22) =>
  interpolate(f, [s, s + d], [dist, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

const elas = (f: number, s: number, d = 26) =>
  interpolate(f, [s, s + d], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(1)),
  });

const countUp = (f: number, s: number, end: number, d = 90) =>
  interpolate(f, [s, s + d], [0, end], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const Shell: React.FC<{ f: number; caption: string; captionDelay?: number; children: React.ReactNode }> =
  ({ f, caption, captionDelay = 55, children }) => {
  const fadeIn = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.035 + 0.05;
  const scanY  = interpolate(f, [0, 38], [-2, 104], { extrapolateRight: 'clamp' });
  const scanOp = interpolate(f, [0, 5, 33, 38], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const capOp  = fi(f, captionDelay, 15);
  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT }}>
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow }} />
      <div style={{ position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2,
        background: 'linear-gradient(90deg, transparent, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)', opacity: scanOp, zIndex: 10, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        paddingInline: 120 }}>
        {children}
      </div>
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: capOp }}>
        <div style={{ color: C.textPrimary, fontSize: 40, fontWeight: 700,
          textAlign: 'center', paddingInline: 80, lineHeight: 1.4 }}>
          {caption}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Lbl: React.FC<{ f: number; text: string; s?: number }> = ({ f, text, s = 8 }) => (
  <div style={{ opacity: fi(f, s, 15), color: C.textSub, fontSize: 28, fontWeight: 500,
    letterSpacing: 5, marginBottom: 24 }}>
    {text}
  </div>
);

const HBar: React.FC<{ f: number; s: number; label: string; value: number; max: number; color: string; suffix?: string; dec?: number }> =
  ({ f, s, label, value, max, color, suffix = '', dec = 0 }) => {
  const prog = interpolate(f, [s, s + 90], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
  });
  const display = dec > 0 ? value.toFixed(dec) : String(Math.round(value));
  return (
    <div style={{ marginBottom: 24, width: '100%', maxWidth: 780 }}>
      <div style={{ color: C.textSub, fontSize: 26, marginBottom: 10 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ flex: 1, height: 50, background: '#1a1a1a', borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ width: `${(value / max) * 100 * prog}%`, height: '100%', background: color, borderRadius: 6 }} />
        </div>
        <span style={{ color, fontSize: 30, fontWeight: 700, textShadow: GLOW.mid.text, minWidth: 110 }}>
          {display}{suffix}
        </span>
      </div>
    </div>
  );
};

// ── S01: 97% 임팩트 훅 ────────────────────────────────────
const S01: React.FC = () => {
  const f = useCurrentFrame();
  const num = Math.max(97, Math.ceil(interpolate(f, [0, 55], [100, 97], { extrapolateRight: 'clamp' })));
  const sc = elas(f, 10, 28);
  const breathe = sc >= 1 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 34]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;
  const burstOp = interpolate(f, [85, 92, 118], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burstSc = interpolate(f, [85, 118], [0.2, 2.8], { extrapolateRight: 'clamp' });
  return (
    <Shell f={f} caption="수익을 내는 사람은 단 1%">
      <Lbl f={f} text="데이터 탐정" />
      <div style={{ position: 'absolute', top: '38%', left: '50%', width: 560, height: 560,
        marginLeft: -280, marginTop: -280, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
        opacity: burstOp, transform: `scale(${burstSc})`, pointerEvents: 'none' }} />
      <div style={{ transform: `scale(${sc * breathe})`, fontSize: 148, fontWeight: 900,
        color: C.main, lineHeight: 1,
        textShadow: sc > 0.9 ? dynGlow : undefined }}>
        {num}%
      </div>
      <div style={{ opacity: fi(f, 65, 20), color: C.textPrimary, fontSize: 36, marginTop: 20,
        transform: `translateY(${slideY(f, 65, 40, 20)}px)` }}>
        데이트레이더 중 6개월 안에 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>돈을 잃는</span> 비율
      </div>
    </Shell>
  );
};

// ── S02: 오늘 91.7억 반대매매 ─────────────────────────────
const S02: React.FC = () => {
  const f = useCurrentFrame();
  const amt = countUp(f, 30, 91.7, 80);
  return (
    <Shell f={f} caption="레버리지 투자자 91.7억원 강제 반대매매">
      <Lbl f={f} text="2026.05.22 — 오늘" />
      <div style={{ opacity: fi(f, 20, 18), transform: `translateY(${slideY(f, 20, 50, 18)}px)`,
        background: C.cardBg, border: `1px solid ${C.main}88`,
        borderLeft: `4px solid ${C.main}`, borderRadius: 12, padding: '36px 64px', textAlign: 'center' }}>
        <div style={{ color: C.textSub, fontSize: 24, marginBottom: 16, letterSpacing: 3 }}>
          긴급 반대매매 발생
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, justifyContent: 'center' }}>
          <span style={{ fontSize: 110, fontWeight: 900, color: C.main, textShadow: GLOW.strong.text }}>
            {amt.toFixed(1)}
          </span>
          <span style={{ fontSize: 48, color: C.main, fontWeight: 700 }}>억원</span>
        </div>
      </div>
      <div style={{ opacity: fi(f, 150, 20), color: C.main, fontSize: 30, marginTop: 28,
        textShadow: GLOW.mid.text }}>
        종목이 나빠서? 운이 나빠서? — 아닙니다. <span style={{ color: C.textPrimary }}>구조 때문입니다.</span>
      </div>
    </Shell>
  );
};

// ── S03: 세 가지 구조 리스트 ──────────────────────────────
const S03: React.FC = () => {
  const f = useCurrentFrame();
  const cards = [
    { n: '1', text: '살아남은 사람의 이야기만 듣는다', s: 48 },
    { n: '2', text: '복리를 버리고 한 방을 노린다', s: 72 },
    { n: '3', text: '사는 순간 눈이 멀어버린다', s: 96 },
  ];
  return (
    <Shell f={f} caption="종목이 아니라 구조가 문제입니다">
      <Lbl f={f} text="오늘의 주제" />
      <div style={{ opacity: fi(f, 20, 18), color: C.textPrimary, fontSize: 52, fontWeight: 900,
        marginBottom: 32, transform: `translateY(${slideY(f, 20, 50, 18)}px)` }}>
        세 가지 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>구조</span>
      </div>
      {cards.map(({ n, text, s }) => {
        const scanY2 = interpolate(f, [s + 10, s + 28], [0, 110], { extrapolateRight: 'clamp' });
        const scanOp2 = interpolate(f, [s + 10, s + 15, s + 24, s + 28], [0, 0.9, 0.9, 0], { extrapolateRight: 'clamp' });
        return (
          <div key={n} style={{
            opacity: fi(f, s, 22), transform: `translateX(${slideX(f, s, -80)}px)`,
            display: 'flex', alignItems: 'center', gap: 24,
            background: C.cardBg, border: `1px solid ${C.borderSub}`,
            borderRadius: 12, padding: '22px 40px', marginBottom: 16, width: '100%',
            position: 'relative', overflow: 'hidden',
          }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: C.main,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 30, fontWeight: 900, color: '#000000', flexShrink: 0,
              boxShadow: GLOW.mid.box }}>
              {n}
            </div>
            <span style={{ color: C.textPrimary, fontSize: 28 }}>{text}</span>
            <div style={{ position: 'absolute', left: 0, right: 0, top: `${scanY2}%`, height: 1.5,
              background: 'linear-gradient(90deg, transparent, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent)',
              opacity: scanOp2, pointerEvents: 'none' }} />
          </div>
        );
      })}
    </Shell>
  );
};

// ── S04: 생존자 편향 dots ─────────────────────────────────
const S04: React.FC = () => {
  const f = useCurrentFrame();
  const POS = Array.from({ length: 20 }, (_, i) => ({
    x: 140 + (i % 5) * 150, y: 80 + Math.floor(i / 5) * 90,
    survivor: i < 3, fadeAt: 55 + i * 8,
  }));
  return (
    <Shell f={f} caption="우리 눈에는 성공한 사람만 보인다">
      <Lbl f={f} text="생존자 편향" />
      <svg width={900} height={430} style={{ opacity: fi(f, 25, 20) }}>
        {POS.map((p, i) => {
          const isFaded = !p.survivor;
          const fadeProg = fi(f, p.fadeAt, 20);
          const op = isFaded ? Math.max(0.06, 1 - fadeProg * 0.94) : 1;
          const color = p.survivor ? C.main : C.textSub;
          return (
            <g key={i}>
              {p.survivor && (
                <circle cx={p.x} cy={p.y} r={36} fill="none" stroke={C.main} strokeWidth={1.5}
                  opacity={op * 0.45 * fi(f, 170)} />
              )}
              <circle cx={p.x} cy={p.y} r={p.survivor ? 26 : 20} fill={color} opacity={op} />
            </g>
          );
        })}
        {f > 185 && (
          <>
            <text x={458} y={395} fill={C.main} fontSize={22} textAnchor="middle" opacity={fi(f, 185)}>
              ↑ 유튜브·텔레그램에서 목소리를 내는 사람들
            </text>
            <text x={458} y={30} fill={C.textSub} fontSize={22} textAnchor="middle" opacity={fi(f, 200)}>
              조용히 사라진 17명
            </text>
          </>
        )}
      </svg>
    </Shell>
  );
};

// ── S05: 탈레브 quote ────────────────────────────────────
const S05: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Shell f={f} caption="묘지의 목소리를 듣지 못한다">
      <Lbl f={f} text="나심 탈레브 / The Black Swan" />
      <div style={{ opacity: fi(f, 22, 18), transform: `translateY(${slideY(f, 22, 50, 18)}px)`,
        background: C.cardBgActive, borderLeft: `4px solid ${C.main}`,
        borderRadius: 12, padding: '40px 56px', width: '100%' }}>
        <div style={{ fontSize: 36, lineHeight: 1.7, color: C.textPrimary, fontStyle: 'italic', marginBottom: 20 }}>
          "우리는 묘지의 목소리를 듣지 못한다"
        </div>
        <div style={{ color: C.main, fontSize: 22, fontWeight: 600, textShadow: GLOW.weak.text }}>
          — 나심 탈레브
        </div>
      </div>
      <div style={{ opacity: fi(f, 120, 20), color: C.textPrimary, fontSize: 28, marginTop: 32,
        textAlign: 'center', lineHeight: 1.7,
        transform: `translateY(${slideY(f, 120, 30, 20)}px)` }}>
        수익 인증 유튜버, 탑픽 텔레그램 — 살아남은 소수만 목소리를 냅니다<br />
        <span style={{ color: C.textSub, fontSize: 24 }}>실패한 다수는 조용히 사라졌습니다</span>
      </div>
    </Shell>
  );
};

// ── S06: 리버모어 $100M 상승 ─────────────────────────────
const S06: React.FC = () => {
  const f = useCurrentFrame();
  const W = 860, H = 290;
  const prog = interpolate(f, [30, 200], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const raw: [number, number][] = [[0, H], [0.2 * W, H * 0.8], [0.45 * W, H * 0.55], [0.65 * W, H * 0.25], [0.85 * W, H * 0.08], [W, H * 0.02]];
  const n = Math.min(raw.length, Math.floor(prog * (raw.length - 1)) + 2);
  const pts = raw.slice(0, n);
  if (n < raw.length) {
    const fr = prog * (raw.length - 1) - (n - 2);
    const [x1, y1] = raw[n - 2], [x2, y2] = raw[n - 1];
    pts[pts.length - 1] = [x1 + (x2 - x1) * fr, y1 + (y2 - y1) * fr];
  }
  const d = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  return (
    <Shell f={f} caption="대공황에 베팅해 1억 달러 달성">
      <Lbl f={f} text="1929년 — 제시 리버모어" />
      <svg width={W} height={H + 36} style={{ opacity: fi(f, 25, 15) }}>
        <line x1={0} y1={H} x2={W} y2={H} stroke={C.textSub} strokeWidth={1} opacity={0.25} />
        <path d={d} stroke={C.main} strokeWidth={3} fill="none" />
        {prog > 0.88 && (
          <text x={W - 8} y={H * 0.02 + 18} fill={C.main} fontSize={20} textAnchor="end"
            opacity={fi(f, 190)} style={{ filter: GLOW.weak.filter }}>$100,000,000</text>
        )}
      </svg>
      <div style={{ opacity: fi(f, 210, 18), color: C.main, fontSize: 52, fontWeight: 900,
        textShadow: GLOW.strong.text, marginTop: 8 }}>
        1억 달러 달성
      </div>
    </Shell>
  );
};

// ── S07: 리버모어 폭락 + 4번 파산 ───────────────────────
const S07: React.FC = () => {
  const f = useCurrentFrame();
  const W = 860, H = 290;
  const prog = interpolate(f, [18, 170], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const raw: [number, number][] = [[0, H * 0.02], [0.25 * W, H * 0.2], [0.5 * W, H * 0.5], [0.75 * W, H * 0.78], [W, H * 0.98]];
  const n = Math.min(raw.length, Math.floor(prog * (raw.length - 1)) + 2);
  const pts = raw.slice(0, n);
  if (n < raw.length) {
    const fr = prog * (raw.length - 1) - (n - 2);
    const [x1, y1] = raw[n - 2], [x2, y2] = raw[n - 1];
    pts[pts.length - 1] = [x1 + (x2 - x1) * fr, y1 + (y2 - y1) * fr];
  }
  const d = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  return (
    <Shell f={f} caption="역사상 최고 트레이더. 4번 파산.">
      <Lbl f={f} text="그로부터 5년 후" />
      <svg width={W} height={H + 24} style={{ opacity: fi(f, 8, 15) }}>
        <line x1={0} y1={H} x2={W} y2={H} stroke={C.textSub} strokeWidth={1} opacity={0.25} />
        <path d={d} stroke={C.textPrimary} strokeWidth={3} fill="none" />
        {prog > 0.88 && (
          <text x={W - 8} y={H * 0.98 + 18} fill={C.textPrimary} fontSize={20} textAnchor="end"
            opacity={fi(f, 162)}>$0</text>
        )}
      </svg>
      <div style={{ opacity: fi(f, 175, 18), color: C.textPrimary, fontSize: 60, fontWeight: 900,
        marginTop: 8 }}>
        전 재산 소멸
      </div>
      <div style={{ opacity: fi(f, 210, 18), color: C.textSub, fontSize: 26 }}>
        우리가 따라가는 유튜버가 리버모어보다 뛰어날까요?
      </div>
    </Shell>
  );
};

// ── S08: 한국 거래량 65% 파이 ────────────────────────────
const S08: React.FC = () => {
  const f = useCurrentFrame();
  const prog = interpolate(f, [28, 110], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const kPct = prog * 65;
  const deg = (kPct / 100) * 360;
  return (
    <Shell f={f} caption="개인이 65%를 차지하며 가장 많이 잃는다">
      <Lbl f={f} text="한국 주식시장 거래량" />
      <div style={{ position: 'relative', width: 280, height: 280, opacity: fi(f, 22, 18) }}>
        <div style={{ width: '100%', height: '100%', borderRadius: '50%',
          background: `conic-gradient(${C.main} 0deg ${deg}deg, #222 ${deg}deg 360deg)`,
          boxShadow: GLOW.mid.box }} />
        <div style={{ position: 'absolute', inset: '22%', borderRadius: '50%', background: C.bg,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ color: C.main, fontSize: 48, fontWeight: 900, textShadow: GLOW.mid.text }}>
            {Math.round(kPct)}%
          </span>
          <span style={{ color: C.textSub, fontSize: 16 }}>개인</span>
        </div>
      </div>
      <div style={{ opacity: fi(f, 130, 18), color: C.textPrimary, fontSize: 30, marginTop: 28,
        textAlign: 'center', lineHeight: 1.7, transform: `translateY(${slideY(f, 130, 30, 18)}px)` }}>
        시장을 가장 많이 움직이면서 가장 많이 잃는 주체
      </div>
    </Shell>
  );
};

// ── S09: 보유기간 bars ───────────────────────────────────
const S09: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Shell f={f} caption="개인은 평균 3~5일. 1주일도 못 버팁니다">
      <Lbl f={f} text="평균 보유 기간" />
      <div style={{ opacity: fi(f, 20, 15), color: C.textSub, fontSize: 26, marginBottom: 32,
        transform: `translateY(${slideY(f, 20, 30, 15)}px)` }}>
        한국 개인 vs 기관
      </div>
      <HBar f={f} s={40} label="🧑 개인 투자자" value={4} max={200} color={C.textPrimary} suffix="일" />
      <HBar f={f} s={100} label="🏦 기관 투자자" value={180} max={200} color={C.main} suffix="일" />
    </Shell>
  );
};

// ── S10: 한 방 본능 임팩트 (cross-X slide) ───────────────
const S10: React.FC = () => {
  const f = useCurrentFrame();
  const t1X  = interpolate(f, [38, 68], [-180, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [38, 68], [0, 1], { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [38, 68], [22, 0], { extrapolateRight: 'clamp' });
  const t2X  = interpolate(f, [55, 88], [180, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [55, 88], [0, 1], { extrapolateRight: 'clamp' });
  const breathe = t2Op > 0.9 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 34]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;
  return (
    <Shell f={f} caption="이 본능은 390년 동안 바뀌지 않았습니다">
      <Lbl f={f} text="두 번째 구조" />
      <div style={{ textAlign: 'center' }}>
        <div style={{ opacity: t1Op, transform: `translateX(${t1X}px)`,
          letterSpacing: t1Ls, fontSize: 100, fontWeight: 900, color: C.textPrimary, lineHeight: 1.15 }}>
          빠르게 벌고 싶은
        </div>
        <div style={{ opacity: t2Op, transform: `translateX(${t2X}px) scale(${breathe})`,
          fontSize: 100, fontWeight: 900, color: C.main, lineHeight: 1.15,
          textShadow: t2Op > 0.5 ? dynGlow : undefined }}>
          본능
        </div>
      </div>
      <div style={{ opacity: fi(f, 140, 18), color: C.textSub, fontSize: 28, marginTop: 24 }}>
        두 배, 세 배 소리가 들리면 이성이 꺼집니다
      </div>
    </Shell>
  );
};

// ── S11: 튤립 버블 ───────────────────────────────────────
const S11: React.FC = () => {
  const f = useCurrentFrame();
  const hSc = elas(f, 20, 26);
  const eSc = elas(f, 50, 26);
  const eqOp = fi(f, 38, 15);
  return (
    <Shell f={f} caption="1637년 — 암스테르담 집 한 채 = 튤립 한 뿌리">
      <Lbl f={f} text="1637년 네덜란드 — 튤립 버블" />
      <div style={{ display: 'flex', alignItems: 'center', gap: 36 }}>
        <div style={{ fontSize: 150, transform: `scale(${hSc})` }}>🏠</div>
        <div style={{ fontSize: 60, color: C.textSub, opacity: eqOp }}>＝</div>
        <div style={{ fontSize: 150, transform: `scale(${eSc})` }}>🌷</div>
      </div>
      <div style={{ opacity: fi(f, 90, 18), color: C.textPrimary, fontSize: 36, marginTop: 28,
        textAlign: 'center', lineHeight: 1.7, transform: `translateY(${slideY(f, 90, 30, 18)}px)` }}>
        집을 팔고 튤립을 샀습니다<br />
        그리고 하루아침에 폭락했습니다
      </div>
    </Shell>
  );
};

// ── S12: 버블 타임라인 ───────────────────────────────────
const S12: React.FC = () => {
  const f = useCurrentFrame();
  const events = [
    { year: '1637', label: '튤립 버블', sub: '집 한 채 = 꽃 한 뿌리', x: 155 },
    { year: '2000', label: '닷컴 버블', sub: '인터넷 기업 붕괴', x: 458 },
    { year: '2021', label: '코인 광풍', sub: '비트코인 8천만원대 붕괴', x: 760 },
  ];
  const lineW = interpolate(f, [30, 130], [0, 800], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  return (
    <Shell f={f} caption="인간은 390년이 지나도 안 바뀝니다">
      <Lbl f={f} text="반복되는 버블의 역사" />
      <div style={{ opacity: fi(f, 20, 15), color: C.textPrimary, fontSize: 52, fontWeight: 900, marginBottom: 36,
        transform: `translateY(${slideY(f, 20, 40, 15)}px)` }}>
        매번 "이번은 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>다르다</span>"고 했습니다
      </div>
      <svg width={930} height={240}>
        <line x1={80} y1={100} x2={80 + lineW} y2={100} stroke={C.borderSub} strokeWidth={2} />
        {events.map(({ year, label, sub, x }, i) => {
          const op = fi(f, 45 + i * 55, 20);
          const sc = elas(f, 45 + i * 55, 20);
          return (
            <g key={year} opacity={op}>
              <circle cx={x} cy={100} r={10 * sc} fill={C.main} />
              <line x1={x} y1={90} x2={x} y2={54} stroke={C.main} strokeWidth={2} />
              <text x={x} y={44} fill={C.main} fontSize={18} textAnchor="middle" fontWeight={700}>{year}</text>
              <text x={x} y={138} fill={C.textPrimary} fontSize={20} textAnchor="middle">{label}</text>
              <text x={x} y={162} fill={C.textSub} fontSize={16} textAnchor="middle">{sub}</text>
            </g>
          );
        })}
      </svg>
    </Shell>
  );
};

// ── S13: 코스톨라니 수면제 ───────────────────────────────
const S13: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Shell f={f} caption="코스톨라니 — 유럽의 전설적 투자자 (50년 경력)">
      <Lbl f={f} text="앙드레 코스톨라니" />
      <div style={{ opacity: fi(f, 22, 18), transform: `translateY(${slideY(f, 22, 50, 18)}px)`,
        background: C.cardBgActive, borderLeft: `4px solid ${C.main}`,
        borderRadius: 12, padding: '40px 56px', width: '100%' }}>
        <div style={{ fontSize: 34, lineHeight: 1.8, color: C.textPrimary, fontStyle: 'italic', marginBottom: 20 }}>
          "주식을 사고, 수면제를 먹고, 자라.<br />
          몇 년 뒤에 깨어나서 팔아라.<br />
          그것이 가장 확실한 방법이다."
        </div>
        <div style={{ color: C.main, fontSize: 22, fontWeight: 600 }}>— 앙드레 코스톨라니</div>
      </div>
      <div style={{ opacity: fi(f, 130, 18), color: C.textPrimary, fontSize: 28, marginTop: 28,
        transform: `translateY(${slideY(f, 130, 30, 18)}px)` }}>
        수면제 먹는 동안 남들이 다 벌 것 같으니까요
      </div>
    </Shell>
  );
};

// ── S14: 복리 237배 카운트업 ─────────────────────────────
const S14: React.FC = () => {
  const f = useCurrentFrame();
  const mul = Math.floor(countUp(f, 28, 237, 100));
  const money = Math.floor(countUp(f, 90, 23, 80));
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = fi(f, 28) > 0.5 ? interpolate(pulse, [0, 1], [8, 28]) : 8;
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55)`;
  const burstOp = interpolate(f, [110, 118, 148], [0, 0.5, 0], { extrapolateRight: 'clamp' });
  const burstSc = interpolate(f, [110, 148], [0.2, 2.6], { extrapolateRight: 'clamp' });
  return (
    <Shell f={f} caption="단 한 번의 한방이 30년치 복리를 날립니다">
      <Lbl f={f} text="복리의 수학" />
      <div style={{ opacity: fi(f, 16, 15), color: C.textSub, fontSize: 26, marginBottom: 12 }}>연 20% × 30년 복리</div>
      <div style={{ position: 'absolute', top: '38%', left: '50%', width: 480, height: 480,
        marginLeft: -240, marginTop: -240, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
        opacity: burstOp, transform: `scale(${burstSc})`, pointerEvents: 'none' }} />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ fontSize: 160, fontWeight: 900, color: C.main, lineHeight: 1,
          textShadow: fi(f, 28) > 0.3 ? dynGlow : undefined }}>
          {mul}
        </span>
        <span style={{ fontSize: 52, color: C.main, fontWeight: 700, textShadow: GLOW.mid.text }}>배</span>
      </div>
      <div style={{ opacity: fi(f, 92, 18), color: C.textPrimary, fontSize: 30, marginTop: 16 }}>
        1,000만원이 <span style={{ color: C.main, textShadow: GLOW.mid.text, fontWeight: 700 }}>{money}억원</span>이 됩니다
      </div>
    </Shell>
  );
};

// ── S15: -50% 비대칭 ─────────────────────────────────────
const S15: React.FC = () => {
  const f = useCurrentFrame();
  const W = 800, H = 300;
  const progL = interpolate(f, [28, 100], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const progR = interpolate(f, [104, 180], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  return (
    <Shell f={f} caption="잃는 것보다 회복이 두 배 어렵습니다">
      <Lbl f={f} text="손실의 함정" />
      <svg width={W} height={H + 80}>
        <line x1={60} y1={H} x2={740} y2={H} stroke={C.textSub} strokeWidth={1.5} opacity={0.3} />
        <rect x={110} y={H - progL * 150} width={150} height={progL * 150} fill={C.textPrimary} rx={5} />
        <text x={185} y={H - progL * 150 - 14} fill={C.textPrimary} fontSize={28} textAnchor="middle"
          fontWeight={700} opacity={progL}>-50%</text>
        <text x={185} y={H + 34} fill={C.textSub} fontSize={22} textAnchor="middle">손실</text>
        <rect x={540} y={H - progR * 300} width={150} height={progR * 300} fill={C.main} rx={5} />
        <text x={615} y={H - progR * 300 - 14} fill={C.main} fontSize={28} textAnchor="middle"
          fontWeight={700} opacity={progR} style={{ filter: GLOW.mid.filter }}>+100%</text>
        <text x={615} y={H + 34} fill={C.textSub} fontSize={22} textAnchor="middle">회복에 필요</text>
        {f > 155 && (
          <text x={400} y={H / 2 + 10} fill={C.textSub} fontSize={42} textAnchor="middle"
            opacity={fi(f, 155)}>→</text>
        )}
      </svg>
    </Shell>
  );
};

// ── S16: 레버리지 FSS 비교 ───────────────────────────────
const S16: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Shell f={f} caption="레버리지 하나가 손실을 2.3배로 키웁니다">
      <Lbl f={f} text="금융감독원 — 4.6백만 개인 계좌 분석" />
      <div style={{ opacity: fi(f, 18, 15), color: C.textPrimary, fontSize: 44, fontWeight: 700,
        marginBottom: 36, transform: `translateY(${slideY(f, 18, 40, 15)}px)` }}>
        레버리지의 현실
      </div>
      <HBar f={f} s={42} label="📈 레버리지 사용" value={19} max={25} color={C.textPrimary} suffix="% 손실" />
      <HBar f={f} s={100} label="📊 레버리지 미사용" value={8.2} max={25} color={C.main} suffix="% 손실" dec={1} />
    </Shell>
  );
};

// ── S17: 확증 편향 비교형 ────────────────────────────────
const S17: React.FC = () => {
  const f = useCurrentFrame();
  const bigW = interpolate(f, [55, 130], [0, 180], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const smW  = interpolate(f, [100, 160], [0, 90], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const aiReveal = interpolate(f, [145, 185], [0, 1], { extrapolateRight: 'clamp' });
  const humanDim = interpolate(f, [145, 185], [1, 0.38], { extrapolateRight: 'clamp' });
  return (
    <Shell f={f} caption="종목을 사는 순간 뇌가 바뀝니다">
      <Lbl f={f} text="확증 편향 (Confirmation Bias)" />
      <div style={{ opacity: fi(f, 20, 15), color: C.textPrimary, fontSize: 48, fontWeight: 900, marginBottom: 36,
        transform: `translateY(${slideY(f, 20, 40, 15)}px)` }}>
        종목을 산 순간,{' '}
        <span style={{ color: C.main, textShadow: GLOW.mid.text }}>뇌가 바뀐다</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, opacity: fi(f, 48, 22) * humanDim }}>
          <div style={{ width: bigW, height: 64, background: `${C.main}22`, border: `2px solid ${C.main}`,
            borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, boxShadow: GLOW.mid.box }}>
            <span style={{ color: C.main, fontSize: 18, fontWeight: 700 }}>호재 뉴스</span>
          </div>
          <span style={{ color: C.textSub, fontSize: 24, fontStyle: 'italic' }}>"역시 내가 잘 샀지"</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, opacity: fi(f, 95, 22) * aiReveal }}>
          <div style={{ width: smW, height: 46, background: `${C.textPrimary}22`, border: `2px solid ${C.textPrimary}`,
            borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0 }}>
            <span style={{ color: C.textPrimary, fontSize: 16, fontWeight: 700 }}>악재 뉴스</span>
          </div>
          <span style={{ color: C.textSub, fontSize: 24, fontStyle: 'italic' }}>"이건 일시적이야"</span>
        </div>
      </div>
    </Shell>
  );
};

// ── S18: 찰리 멍거 ───────────────────────────────────────
const S18: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Shell f={f} caption="찰리 멍거 — 워런 버핏의 50년 파트너">
      <Lbl f={f} text="찰리 멍거 / Charlie Munger" />
      <div style={{ opacity: fi(f, 22, 18), transform: `translateY(${slideY(f, 22, 50, 18)}px)`,
        background: C.cardBgActive, borderLeft: `4px solid ${C.main}`,
        borderRadius: 12, padding: '40px 56px', width: '100%' }}>
        <div style={{ fontSize: 34, lineHeight: 1.8, color: C.textPrimary, fontStyle: 'italic', marginBottom: 20 }}>
          "거꾸로 생각하라. 항상 거꾸로 생각하라.<br />
          틀릴 이유를 먼저 찾는 사람만이 살아남는다."
        </div>
        <div style={{ color: C.main, fontSize: 22, fontWeight: 600 }}>— 찰리 멍거</div>
      </div>
      <div style={{ opacity: fi(f, 130, 18), color: C.textPrimary, fontSize: 28, marginTop: 28,
        transform: `translateY(${slideY(f, 130, 30, 18)}px)` }}>
        오를 이유 전에{' '}
        <span style={{ color: C.main, textShadow: GLOW.mid.text }}>떨어질 이유를 먼저 찾아야 합니다</span>
      </div>
    </Shell>
  );
};

// ── S19: 손절 못 하는 계단 ───────────────────────────────
const S19: React.FC = () => {
  const f = useCurrentFrame();
  const steps: [string, string, number, number, number][] = [
    ['-10%', '"곧 오르겠지"', 110, 52, 20],
    ['-20%', '"이제 바닥이야"', 250, 145, 85],
    ['-40%', '물타기', 390, 240, 155],
  ];
  return (
    <Shell f={f} caption="사는 순간 눈이 멀어 손절을 못 합니다">
      <Lbl f={f} text="세 번째 구조" />
      <div style={{ opacity: fi(f, 18, 15), color: C.textPrimary, fontSize: 48, fontWeight: 900, marginBottom: 8,
        transform: `translateY(${slideY(f, 18, 40, 15)}px)` }}>
        손절을{' '}<span style={{ color: C.main, textShadow: GLOW.mid.text }}>못 하는</span>{' '}구조
      </div>
      <svg width={680} height={370}>
        {steps.map(([pct, label, x, y, s]) => (
          <g key={pct} opacity={fi(f, s, 22)}>
            <rect x={x} y={y} width={130} height={55} fill={`${C.textPrimary}18`} rx={7}
              stroke={C.textPrimary} strokeWidth={1.5} />
            <text x={x + 65} y={y + 34} fill={C.textPrimary} fontSize={28} textAnchor="middle"
              fontWeight={700}>{pct}</text>
            <text x={x + 65} y={y + 82} fill={C.textSub} fontSize={19} textAnchor="middle">{label}</text>
          </g>
        ))}
        {f > 85 && <path d="M240,79 L250,145" stroke={C.textPrimary} strokeWidth={2}
          strokeDasharray="5 4" opacity={fi(f, 85)} />}
        {f > 155 && <path d="M380,172 L390,240" stroke={C.textPrimary} strokeWidth={2}
          strokeDasharray="5 4" opacity={fi(f, 155)} />}
        {f > 225 && <text x={340} y={340} fill={C.textPrimary} fontSize={22} textAnchor="middle"
          opacity={fi(f, 225)}>↓ 물타기 후 더 크게 물립니다</text>}
      </svg>
    </Shell>
  );
};

// ── S20: 물타기 악순환 플로우 ────────────────────────────
const S20: React.FC = () => {
  const f = useCurrentFrame();
  const CYCLE_LEN = 44;
  const CYCLE_START = 200;
  const steps = ['매수', '하락 -10%', '물타기', '추가 하락 -40%', '강제 손절'];
  const stepS = [20, 65, 110, 155, 200];
  const cycleF = f >= CYCLE_START ? (f - CYCLE_START) % CYCLE_LEN : -1;
  const stepGlow = (i: number) => cycleF >= 0 ? Math.max(0, 1 - Math.abs(cycleF - i * 11) / 8) : 0;
  const arrowSx = (i: number) => {
    const s = stepS[i] + 15;
    return interpolate(f, [s, s + 16], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  };
  return (
    <Shell f={f} caption="물타기 후 더 크게 물립니다">
      <Lbl f={f} text="물타기 악순환" />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {steps.map((label, i) => {
          const glow = stepGlow(i);
          const isLast = i === steps.length - 1;
          return (
            <React.Fragment key={label}>
              <div style={{
                opacity: fi(f, stepS[i], 22),
                background: isLast ? `${C.main}22` : C.cardBg,
                border: `1px solid ${glow > 0.3 || isLast ? C.main : C.borderSub}`,
                borderRadius: 10, padding: '16px 18px', textAlign: 'center', minWidth: 100,
                boxShadow: glow > 0.3 ? GLOW.mid.box : 'none',
              }}>
                <span style={{ color: isLast ? C.main : C.textPrimary, fontSize: 20, fontWeight: 700 }}>
                  {label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div style={{ transform: `scaleX(${arrowSx(i)})`, transformOrigin: 'left center',
                  opacity: fi(f, stepS[i] + 15, 16), color: C.textSub, fontSize: 28 }}>→</div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </Shell>
  );
};

// ── S21: 삼성/에코프로 케이스 ────────────────────────────
const S21: React.FC = () => {
  const f = useCurrentFrame();
  const CARDS = [
    { name: '삼성전자', detail: '국내 1위 기업도\n물타기로 손실', s: 35 },
    { name: '에코프로', detail: '테마주 고점 매수\n→ 물타기 → 대손실', s: 75 },
  ];
  const aiReveal = interpolate(f, [135, 175], [0, 1], { extrapolateRight: 'clamp' });
  const humanDim = interpolate(f, [135, 175], [1, 0.35], { extrapolateRight: 'clamp' });
  return (
    <Shell f={f} caption="종목이 문제가 아닙니다">
      <Lbl f={f} text="삼성전자도, 에코프로도" />
      <div style={{ opacity: fi(f, 20, 15), color: C.textPrimary, fontSize: 48, fontWeight: 900, marginBottom: 36,
        transform: `translateY(${slideY(f, 20, 40, 15)}px)` }}>
        종목이 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>문제가 아닙니다</span>
      </div>
      <div style={{ display: 'flex', gap: 32 }}>
        {CARDS.map(({ name, detail, s }, i) => (
          <div key={name} style={{
            opacity: fi(f, s, 22) * (i === 0 ? humanDim : aiReveal),
            background: i === 0 ? C.cardBg : C.cardBgActive,
            border: `1px solid ${i === 0 ? C.borderSub : C.borderActive}`,
            borderRadius: 12, padding: '28px 44px', textAlign: 'center',
            boxShadow: i === 1 && aiReveal > 0.3 ? GLOW.mid.box : 'none',
          }}>
            <div style={{ color: C.textPrimary, fontSize: 28, fontWeight: 700, marginBottom: 12 }}>{name}</div>
            <div style={{ color: C.textPrimary, fontSize: 20, lineHeight: 1.7, whiteSpace: 'pre-line' }}>{detail}</div>
          </div>
        ))}
      </div>
      <div style={{ opacity: fi(f, 180, 18), color: C.textSub, fontSize: 26, marginTop: 28 }}>
        사는 순간 눈이 멀어버리는 본능이 문제입니다
      </div>
    </Shell>
  );
};

// ── S22: 세 가지 구조 최종 정리 ─────────────────────────
const S22: React.FC = () => {
  const f = useCurrentFrame();
  const ITEMS = [
    { n: '1', text: '살아남은 사람의 이야기만 본다 → 생존자 편향', s: 30 },
    { n: '2', text: '복리를 버리고 단기 한 방 → 레버리지·단타', s: 80 },
    { n: '3', text: '사는 순간 눈이 멀어 손절 불가 → 확증 편향', s: 130 },
  ];
  const ringPhase = f >= 230 ? ((f - 230) % 60) / 60 : 0;
  const ringGlow = (i: number) => {
    const center = i / 3 + 1 / 6;
    const dist = Math.min(Math.abs(ringPhase - center), 1 - Math.abs(ringPhase - center));
    return Math.max(0, 1 - dist * 3 * 1.8);
  };
  return (
    <Shell f={f} caption="이 세 가지는 종목과 무관합니다">
      <Lbl f={f} text="오늘의 정리" />
      {ITEMS.map(({ n, text, s }, i) => {
        const rg = ringGlow(i);
        return (
          <div key={n} style={{
            opacity: fi(f, s, 22),
            transform: `translateX(${slideX(f, s, -80)}px)`,
            display: 'flex', alignItems: 'center', gap: 24,
            background: C.cardBg, border: `1px solid ${rg > 0.3 ? C.borderActive : C.borderSub}`,
            borderRadius: 12, padding: '22px 40px', marginBottom: 16, width: '100%',
            boxShadow: rg > 0.3 ? GLOW.mid.box : 'none',
          }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: C.main, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 28, fontWeight: 900, color: '#000' }}>
              {n}
            </div>
            <span style={{ color: C.textPrimary, fontSize: 24, lineHeight: 1.5 }}>{text}</span>
          </div>
        );
      })}
    </Shell>
  );
};

// ── S23: 탈레브 마지막 quote 클라이맥스 ──────────────────
const S23: React.FC = () => {
  const f = useCurrentFrame();
  const zoom = interpolate(f, [0, 180], [1, 1.04], { extrapolateRight: 'clamp' });
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = fi(f, 22) > 0.5 ? interpolate(pulse, [0, 1], [10, 34]) : 10;
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;
  const burstOp = interpolate(f, [85, 92, 118], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burstSc = interpolate(f, [85, 118], [0.2, 2.8], { extrapolateRight: 'clamp' });
  return (
    <Shell f={f} caption="주식에서 먼저 부서지지 않는 것이 먼저입니다">
      <div style={{ transform: `scale(${zoom})`, width: '100%', display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div style={{ position: 'absolute', top: '38%', left: '50%', width: 560, height: 560,
          marginLeft: -280, marginTop: -280, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
          opacity: burstOp, transform: `scale(${burstSc})`, pointerEvents: 'none' }} />
        <Lbl f={f} text="나심 탈레브 — Antifragile" />
        <div style={{ opacity: fi(f, 22, 18), transform: `translateY(${slideY(f, 22, 50, 18)}px)`,
          background: C.cardBgActive, borderLeft: `4px solid ${C.main}`,
          borderRadius: 12, padding: '40px 56px' }}>
          <div style={{ fontSize: 32, lineHeight: 1.8, color: C.textPrimary, fontStyle: 'italic',
            marginBottom: 20, textShadow: fi(f, 22) > 0.5 ? dynGlow : undefined }}>
            "강한 것은 충격에 버티는 게 아니다.<br />
            충격에 오히려 더 강해지는 것이다.<br />
            그러려면 먼저 부서지지 않아야 한다."
          </div>
          <div style={{ color: C.main, fontSize: 22, fontWeight: 600, textShadow: GLOW.mid.text }}>
            — 나심 탈레브 / Antifragile
          </div>
        </div>
      </div>
    </Shell>
  );
};

// ── S24: "구조가 바뀌어야" 임팩트 (cross-X slide) ─────────
const S24: React.FC = () => {
  const f = useCurrentFrame();
  const zoom = interpolate(f, [0, 180], [1, 1.04], { extrapolateRight: 'clamp' });
  const t1X  = interpolate(f, [38, 68], [-180, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t1Op = interpolate(f, [38, 68], [0, 1], { extrapolateRight: 'clamp' });
  const t1Ls = interpolate(f, [38, 68], [22, 0], { extrapolateRight: 'clamp' });
  const t2X  = interpolate(f, [55, 88], [180, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const t2Op = interpolate(f, [55, 88], [0, 1], { extrapolateRight: 'clamp' });
  const breathe = t2Op > 0.9 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 34]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.55), 0 0 ${gSz * 4}px rgba(0,191,154,0.3)`;
  const burstOp = interpolate(f, [88, 95, 125], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burstSc = interpolate(f, [88, 125], [0.2, 2.8], { extrapolateRight: 'clamp' });
  return (
    <Shell f={f} caption="이 세 가지를 아는 것과 모르는 것이 계좌의 운명을 가릅니다">
      <div style={{ transform: `scale(${zoom})`, textAlign: 'center' }}>
        <div style={{ position: 'absolute', top: '38%', left: '50%', width: 560, height: 560,
          marginLeft: -280, marginTop: -280, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)',
          opacity: burstOp, transform: `scale(${burstSc})`, pointerEvents: 'none' }} />
        <div style={{ opacity: t1Op, transform: `translateX(${t1X}px)`,
          letterSpacing: t1Ls, fontSize: 110, fontWeight: 900, color: C.textPrimary, lineHeight: 1.15 }}>
          구조가 바뀌어야
        </div>
        <div style={{ opacity: t2Op, transform: `translateX(${t2X}px) scale(${breathe})`,
          fontSize: 110, fontWeight: 900, color: C.main, lineHeight: 1.15,
          textShadow: t2Op > 0.5 ? dynGlow : undefined }}>
          결과가 바뀐다
        </div>
      </div>
    </Shell>
  );
};

// ── S25: 다음 영상 예고 ──────────────────────────────────
const S25: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Shell f={f} caption="기관이 빠진 빈집에서 진입하는 법 — 다음 영상">
      <Lbl f={f} text="다음 영상" />
      <div style={{ opacity: fi(f, 28, 20), transform: `translateY(${slideY(f, 28, 50, 20)}px)`,
        background: C.cardBgActive, border: `1px solid ${C.borderActive}`,
        borderRadius: 16, padding: '40px 64px', textAlign: 'center', width: '100%',
        boxShadow: GLOW.mid.box }}>
        <div style={{ color: C.main, fontSize: 26, fontWeight: 700, marginBottom: 16,
          textShadow: GLOW.weak.text }}>실전 편</div>
        <div style={{ color: C.textPrimary, fontSize: 48, fontWeight: 900, lineHeight: 1.4 }}>
          기관이 빠진{' '}
          <span style={{ color: C.main, textShadow: GLOW.mid.text }}>빈집</span>에서<br />
          진입하는 법
        </div>
        <div style={{ color: C.textSub, fontSize: 24, marginTop: 16 }}>수급 데이터로 직접 보여드립니다</div>
      </div>
    </Shell>
  );
};

// ── S26: CTA 클로징 ──────────────────────────────────────
const S26: React.FC = () => {
  const f = useCurrentFrame();
  const pulse = Math.sin(f * 0.12) * 0.5 + 0.5;
  const btnPulse = 0.88 + 0.12 * pulse;
  const glowStr = interpolate(pulse, [0, 1], [6, 28]);
  const dynGlow = `0 0 ${glowStr}px #00FFD0, 0 0 ${glowStr * 2}px rgba(0,255,208,0.55)`;
  return (
    <Shell f={f} caption="구독 + 알림 설정하시면 놓치지 않습니다">
      <Lbl f={f} text="로또의 주식" />
      <div style={{ opacity: fi(f, 16, 15), color: C.textPrimary, fontSize: 48, fontWeight: 700, marginBottom: 40,
        transform: `translateY(${slideY(f, 16, 40, 15)}px)` }}>
        오늘도 수익 나는 하루 되세요
      </div>
      <div style={{ display: 'flex', gap: 28, opacity: fi(f, 40, 20) }}>
        {[
          { icon: '👍', label: '좋아요', highlight: false, delay: 40 },
          { icon: '🔔', label: '알림 설정', highlight: true, delay: 60 },
          { icon: '📢', label: '구독', highlight: false, delay: 80 },
        ].map(({ icon, label, highlight, delay }) => (
          <div key={label} style={{
            opacity: fi(f, delay, 20),
            transform: `scale(${highlight ? btnPulse : 1})`,
            background: highlight ? C.main : C.cardBg,
            border: `1px solid ${highlight ? C.main : C.borderSub}`,
            color: highlight ? '#000000' : C.textPrimary,
            borderRadius: 12, padding: '22px 36px', textAlign: 'center',
            boxShadow: highlight ? dynGlow : 'none',
          }}>
            <div style={{ fontSize: 44, marginBottom: 8 }}>{icon}</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{label}</div>
          </div>
        ))}
      </div>
    </Shell>
  );
};

// ── S27: 핵심 메시지 ─────────────────────────────────────
const S27: React.FC = () => {
  const f = useCurrentFrame();
  const breathe = fi(f, 50) > 0.9 ? Math.sin(f * 0.07) * 0.018 + 1 : 1;
  return (
    <Shell f={f} caption="크게 버는 것은 그 다음입니다">
      <div style={{ textAlign: 'center' }}>
        <div style={{ opacity: fi(f, 22, 20), color: C.textSub, fontSize: 28, letterSpacing: 5, marginBottom: 20 }}>
          주식에서
        </div>
        <div style={{ opacity: fi(f, 40, 22), transform: `scale(${breathe})`,
          color: C.main, fontSize: 80, fontWeight: 900, lineHeight: 1.2,
          textShadow: fi(f, 50) > 0.9 ? GLOW.strong.text : GLOW.mid.text }}>
          먼저 부서지지<br />않는 것이 먼저
        </div>
      </div>
    </Shell>
  );
};

// ── S28: 아웃트로 ────────────────────────────────────────
const S28: React.FC = () => {
  const f = useCurrentFrame();
  const PARTS = Array.from({ length: 12 }, (_, i) => ({
    x: 240 + ((i * 137) % 1440), baseY: 600 + (i * 71) % 240,
    cycleLen: 90 + (i * 13) % 60, delay: i * 14,
  }));
  return (
    <Shell f={f} caption="로또의 주식 — 데이터가 말하면 듣는다" captionDelay={20}>
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        {PARTS.map(({ x, baseY, cycleLen, delay }, i) => {
          const age = Math.max(0, f - delay) % cycleLen;
          const prog = age / cycleLen;
          const pOp = prog < 0.2 ? prog / 0.2 : prog > 0.7 ? (1 - prog) / 0.3 : 1;
          return (
            <div key={i} style={{
              position: 'absolute', left: x, top: baseY - prog * 50,
              width: 4, height: 4, borderRadius: '50%', background: C.main,
              opacity: pOp * 0.6,
            }} />
          );
        })}
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ opacity: elas(f, 14, 28), color: C.main, fontSize: 80, fontWeight: 900,
          textShadow: GLOW.strong.text }}>
          로또의 주식
        </div>
        <div style={{ opacity: fi(f, 50, 18), color: C.textSub, fontSize: 28, letterSpacing: 4, marginTop: 16 }}>
          데이터가 말하면 듣는다
        </div>
      </div>
    </Shell>
  );
};

// ── 메인 컴포넌트 ─────────────────────────────────────────

const SCENES = [S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14,
  S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28];

export const LoseReasonVideo: React.FC = () => (
  <Series>
    {SCENES.map((Scene, i) => (
      <Series.Sequence key={i} durationInFrames={SCENE_DUR}>
        <FadeWrapper dur={SCENE_DUR}>
          <Scene />
        </FadeWrapper>
      </Series.Sequence>
    ))}
  </Series>
);
