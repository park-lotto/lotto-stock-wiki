// YT_AI_S05_클라이맥스 — 씬5 클라이맥스 (1200프레임 / 40초)
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

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
  { s: 0,   e: 60,  text: '보셨습니까?' },
  { s: 120, e: 420, text: '수백 개, 아니 수천 개의 정보 속에서 AI가 뽑아낸 핵심 종목 3가지와 주요 섹터가 이렇게 단 몇 분 만에 여러분 앞에 펼쳐집니다.' },
  { s: 420, e: 570, text: '이것만 알아도 여러분은 이미 남들보다 몇 시간 앞서가는 겁니다.' },
  { s: 570, e: 720, text: '더 이상 복잡한 정보의 늪에서 허우적대지 마세요.' },
  { s: 720, e: 900, text: 'STOCK BRAIN이 여러분의 시간을 아껴주고, 수익률을 높여줄 겁니다.' },
  { s: 960, e: 1200, text: '300개 정보 중 3개, 이것이 바로 AI의 힘입니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// ── 탑픽 및 섹터 데이터 ──────────────────────────────────────────────
const TOP_PICKS = [
  { name: '삼성전자', highlightStart: 180, highlightEnd: 280 },
  { name: 'SK하이닉스', highlightStart: 220, highlightEnd: 320 },
  { name: 'LG에너지솔루션', highlightStart: 260, highlightEnd: 360 },
];
const MAIN_SECTORS = [
  { name: '반도체', highlightStart: 300, highlightEnd: 400 },
  { name: '2차전지', highlightStart: 340, highlightEnd: 440 },
  { name: 'AI/로봇', highlightStart: 380, highlightEnd: 480 },
];

export const YT_AI_S05_클라이맥스: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5; // For dynamic glow
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px ${C.main}, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // Phase 1: Final briefing summary (f0-600)
  const phase1Opacity = ip(f, 0, 30, 0, 1);
  const phase1FadeOut = ip(f, 570, 600, 1, 0);

  // Phase 2: Core message (f600-1200)
  const phase2Opacity = ip(f, 600, 630, 0, 1);

  // '핵심 종목 3가지' text animation
  const keyTextScale = ip(f, 120, 180, 0.8, 1.2, Easing.out(Easing.back));
  const keyTextOpacity = ip(f, 120, 150, 0, 1);
  const keyTextGlowVal = ip(f, 120, 400, 0, 1);
  const keyTextShadow = `0 0 ${keyTextGlowVal * 20}px ${C.main}, 0 0 ${keyTextGlowVal * 40}px rgba(0,255,208,0.5)`;

  // '300개 정보 노가다 → 딸깍 한 번 → 주도주 딱 3개' text animation
  const coreMessageScale = ip(f, 630, 750, 0.5, 1.0, Easing.out(Easing.elastic));
  const coreMessageOpacity = ip(f, 600, 660, 0, 1);
  const coreMessageGlowVal = ip(f, 600, 1200, 0, 1);
  const coreMessageShadow = `0 0 ${coreMessageGlowVal * 20}px ${C.main}, 0 0 ${coreMessageGlowVal * 40}px rgba(0,255,208,0.5)`;

  // Transformation effect for Phase 2
  const transformLineX = ip(f, 750, 900, -500, 0, Easing.out(Easing.cubic));
  const transformLineOpacity = ip(f, 750, 800, 0, 1);

  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14', overflow: 'hidden' }}>
      <Html5Audio src={staticFile('voice/yt_ai_s05_클라이맥스.m4a')} />

      {/* Phase 1: Briefing Summary */}
      <div style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: Math.min(phase1Opacity, phase1FadeOut),
        transform: `scale(${ip(f, 0, 600, 1, 0.9)})`, // Slight zoom out
      }}>
        <div style={{
          fontFamily: FONT,
          fontSize: 80,
          fontWeight: 900,
          color: '#FFF',
          marginBottom: 40,
          textShadow: keyTextShadow,
          transform: `scale(${keyTextScale})`,
          opacity: keyTextOpacity,
        }}>
          핵심 종목 3가지
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 40,
          marginBottom: 60,
        }}>
          {TOP_PICKS.map((stock, i) => {
            const stockOp = ip(f, stock.highlightStart, stock.highlightStart + 30, 0, 1);
            const stockScale = ip(f, stock.highlightStart, stock.highlightStart + 60, 0.8, 1.1, Easing.out(Easing.back));
            const stockGlow = ip(f, stock.highlightStart, stock.highlightEnd, 0, 1, Easing.inOut(Easing.cubic));
            return (
              <div key={i} style={{
                fontFamily: FONT,
                fontSize: 64,
                fontWeight: 700,
                color: C.main,
                padding: '20px 40px',
                borderRadius: 20,
                background: `rgba(0,255,208,${stockGlow * 0.1})`, // Dynamic background tint
                border: `2px solid rgba(0,255,208,${stockGlow})`,
                boxShadow: `0 0 ${stockGlow * 30}px ${C.main}, 0 0 ${stockGlow * 60}px rgba(0,255,208,0.5)`,
                opacity: stockOp,
                transform: `scale(${stockScale})`,
                textAlign: 'center',
              }}>
                {stock.name}
              </div>
            );
          })}
        </div>

        <div style={{
          fontFamily: FONT,
          fontSize: 60,
          fontWeight: 800,
          color: '#FFA502',
          marginBottom: 30,
          textShadow: `0 0 ${ip(f, 280, 500, 0, 20)}px #FFA502`,
        }}>
          주요 섹터
        </div>

        <div style={{
          display: 'flex',
          gap: 30,
        }}>
          {MAIN_SECTORS.map((sector, i) => {
            const sectorOp = ip(f, sector.highlightStart, sector.highlightStart + 30, 0, 1);
            const sectorScale = ip(f, sector.highlightStart, sector.highlightStart + 60, 0.8, 1.1, Easing.out(Easing.back));
            const sectorGlow = ip(f, sector.highlightStart, sector.highlightEnd, 0, 1, Easing.inOut(Easing.cubic));
            return (
              <div key={i} style={{
                fontFamily: FONT,
                fontSize: 48,
                fontWeight: 600,
                color: '#FFA502',
                padding: '15px 30px',
                borderRadius: 15,
                background: `rgba(255,165,2,${sectorGlow * 0.1})`, // Dynamic background tint
                border: `2px solid rgba(255,165,2,${sectorGlow})`,
                boxShadow: `0 0 ${sectorGlow * 20}px #FFA502, 0 0 ${sectorGlow * 40}px rgba(255,165,2,0.5)`,
                opacity: sectorOp,
                transform: `scale(${sectorScale})`,
                textAlign: 'center',
              }}>
                {sector.name}
              </div>
            );
          })}
        </div>
      </div>

      {/* Phase 2: Core Message */}
      <div style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: phase2Opacity,
        transform: `scale(${coreMessageScale})`,
      }}>
        <div style={{
          fontFamily: FONT,
          fontSize: 100,
          fontWeight: 900,
          color: '#FFF',
          textAlign: 'center',
          lineHeight: 1.4,
          textShadow: coreMessageShadow,
          marginBottom: 40,
        }}>
          <span style={{ color: '#FF4757' }}>300개 정보 노가다</span>
          <br />
          <span style={{ fontSize: 120, color: C.main, textShadow: dynGlow }}>→ 딸깍 한 번 →</span>
          <br />
          <span style={{ color: C.main }}>주도주 딱 3개</span>
        </div>

        {/* Visual emphasis for transformation - sweeping line */}
        <div style={{
          position: 'absolute',
          width: 800,
          height: 10,
          background: 'linear-gradient(to right, #FF4757, #FFA502, #00FFD0)', // More colors for impact
          borderRadius: 5,
          opacity: transformLineOpacity,
          transform: `translateX(${transformLineX}px)`,
          bottom: '20%',
        }} />
      </div>

      {/* 자막바 */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:'16%',
        display:'flex',alignItems:'center',justifyContent:'center',paddingInline:80,
        background:'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)'}}>
        {sub&&<div style={{color:'#FFF',fontSize:40,fontWeight:700,textAlign:'center',
          opacity:sub.op,textShadow:'0 2px 8px rgba(0,0,0,0.9)'}}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};