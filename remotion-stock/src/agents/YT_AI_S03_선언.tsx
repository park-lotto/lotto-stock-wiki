// YT_AI_S03_선언 — 씬3 선언 (750프레임 / 25초)
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { FONT } from '../constants';

function ip(
  f: number, a: number, b: number,
  from = 0, to = 1,
  ease: (t: number) => number = Easing.out(Easing.cubic),
) {
  return interpolate(f, [a, b], [from, to], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease,
  });
}

// ── 자막 세그먼트 ─────────────────────────────────────────────────
const SUBS = [
  { s: 0,   e: 150, text: '이제 그 모든 정보 노가다는 끝났습니다.' },
  { s: 150, e: 300, text: '저는 AI에게 맡기고 매일 새벽, 이 한 장으로 모든 걸 끝냅니다.' },
  { s: 300, e: 450, text: '이것이 바로 로또의 주식 인사이트, STOCK BRAIN입니다.' },
  { s: 450, e: 750, text: '여러분도 저처럼, 정보의 바다에서 허우적댈 필요가 전혀 없습니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// ── 정보 노가다 클러터 데이터 ──────────────────────────────────────────────
const CLUTTER_ITEMS = Array.from({ length: 100 }).map((_, i) => ({
  id: i,
  text: Math.random() > 0.5 ? String.fromCharCode(65 + Math.floor(Math.random() * 26)) : Math.floor(Math.random() * 999).toString(),
  x: Math.random() * 1920,
  y: Math.random() * 1080,
  size: Math.random() * 20 + 15,
  color: Math.random() > 0.7 ? '#FFA502' : '#9ca3af', // Amber or grey
}));

export const YT_AI_S03_선언: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const bgGlow = Math.sin(f * 0.04) * 0.028 + 0.05;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // Phase 1: Clutter to Clarity (0-300 frames)
  const clutterOpacity = ip(f, 0, 250, 1, 0);
  const clutterScale = ip(f, 0, 250, 1, 0.5);

  // Lotto placeholder (always present, fades in)
  const lottoOpacity = ip(f, 0, 30, 0, 1);
  const lottoScale = ip(f, 0, 30, 0.8, 1);

  // Tablet/Briefing (appears around 250, fades out around 400 for STOCK BRAIN)
  const tabletOpacity = ip(f, 250, 300, 0, 1, Easing.out(Easing.cubic));
  const tabletScale = ip(f, 250, 300, 0.8, 1, Easing.out(Easing.cubic));
  const tabletMoveY = ip(f, 375, 425, 0, -50); // Move up slightly as STOCK BRAIN appears
  const tabletFadeOut = ip(f, 400, 450, 1, 0);

  // STOCK BRAIN logo (appears around 375)
  const stockBrainOpacity = ip(f, 375, 425, 0, 1, Easing.out(Easing.cubic));
  const stockBrainScale = ip(f, 375, 425, 0.8, 1.1, Easing.out(Easing.back(1.7))); // Slightly overshoots
  const stockBrainScaleFinal = ip(f, 425, 475, 1.1, 1); // Settles down

  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14', overflow: 'hidden' }}>
      <Html5Audio src={staticFile('voice/yt_ai_s03_declaration.m4a')} />

      {/* Background Glow */}
      <div style={{
        position: 'absolute', inset: -100,
        background: `radial-gradient(circle at center, rgba(0,255,208,${bgGlow}) 0%, transparent 70%)`,
        opacity: ip(f, 0, 100, 0, 1),
      }} />

      {/* Phase 1: Information Clutter */}
      {CLUTTER_ITEMS.map(item => (
        <div key={item.id} style={{
          position: 'absolute',
          left: item.x,
          top: item.y,
          fontSize: item.size,
          fontFamily: "Consolas, Menlo, monospace",
          color: item.color,
          opacity: clutterOpacity,
          transform: `scale(${clutterScale})`,
          filter: `blur(${ip(f, 200, 250, 0, 2)}px)`, // Blur out as it disappears
        }}>
          {item.text}
        </div>
      ))}

      {/* Lotto Placeholder */}
      <div style={{
        position: 'absolute',
        width: 200, height: 200,
        borderRadius: '50%',
        backgroundColor: '#00FFD0', // C.main assumed
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: FONT, fontSize: 48, fontWeight: 700, color: '#080c14',
        opacity: lottoOpacity,
        transform: `translate(-50%, -50%) scale(${lottoScale})`,
        left: '50%', top: '30%', // Position of Lotto
        boxShadow: dynGlow,
      }}>
        로또님
      </div>

      {/* Phase 2: Tablet/Briefing */}
      <div style={{
        position: 'absolute',
        left: '50%', top: '50%',
        transform: `translate(-50%, -50%) scale(${tabletScale}) translateY(${tabletMoveY}px)`,
        width: 600, height: 400,
        backgroundColor: '#FFF',
        borderRadius: 20,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: tabletOpacity * tabletFadeOut,
        flexDirection: 'column',
        padding: 40,
        boxSizing: 'border-box',
      }}>
        <div style={{
          fontFamily: FONT, fontSize: 48, fontWeight: 700, color: '#080c14',
          textAlign: 'center',
          marginBottom: 20,
        }}>
          오늘의 핵심 브리핑
        </div>
        <div style={{
          fontFamily: "Consolas, Menlo, monospace", fontSize: 28, color: '#333',
          textAlign: 'left',
          width: '100%',
          lineHeight: 1.4,
        }}>
          • AI가 분석한 시장 동향<br/>
          • 탑픽 종목 및 매매 전략<br/>
          • 리스크 요인 및 대응 방안<br/>
          • 주요 뉴스 요약
        </div>
      </div>

      {/* Phase 2: STOCK BRAIN Logo */}
      <div style={{
        position: 'absolute',
        left: '50%', top: '50%',
        transform: `translate(-50%, -50%) scale(${stockBrainScale * stockBrainScaleFinal})`,
        fontFamily: FONT,
        fontSize: 120,
        fontWeight: 900,
        color: '#00FFD0', // C.main assumed
        textShadow: dynGlow,
        opacity: stockBrainOpacity,
        textAlign: 'center',
        letterSpacing: -2,
      }}>
        STOCK BRAIN
      </div>

      {/* Subtitle Bar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80,
        background: 'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)',
      }}>
        {sub && <div style={{
          color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center',
          opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)',
        }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};