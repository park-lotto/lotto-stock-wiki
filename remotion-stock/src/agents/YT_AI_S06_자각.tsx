// YT_AI_S06_자각 — 씬6 자각 (900프레임 / 30초)

import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';

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
  { s: 0,   e: 100, text: '이제 더 이상 밤샘 분석에 시달릴 필요 없습니다.' },
  { s: 120, e: 300, text: '매일 새벽 4시, AI가 뽑아주는 핵심 정보로 여러분의 투자는 이미 시작됩니다.' },
  { s: 360, e: 480, text: '이 STOCK BRAIN이 당신의 든든한 조력자가 되어줄 겁니다.' },
  { s: 500, e: 680, text: '남들보다 빠르게, 그리고 정확하게, 시장의 흐름을 읽고 선점할 수 있게 말이죠.' },
  { s: 700, e: 880, text: '정보의 격차를 AI로 극복하고, 여러분도 \'정보의 천재\'가 될 수 있습니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

export const YT_AI_S06_자각: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // Phase 1: 0-450 frames (0-15s)
  // Background UI graphics
  const uiOpacity = ip(f, 0, 30, 0, 0.6);
  const uiScale = ip(f, 0, 900, 1, 1.05); // Subtle zoom throughout
  const uiRotation = ip(f, 0, 900, 0, 2); // Subtle rotation

  // Keyword highlights style
  const keywordStyle = (startFrame: number, endFrame: number, color: string = C.main) => ({
    fontFamily: FONT,
    fontSize: 72,
    color: color,
    textShadow: dynGlow,
    opacity: ip(f, startFrame, startFrame + 15, 0, 1) * ip(f, endFrame - 15, endFrame, 1, 0),
    transform: `scale(${ip(f, startFrame, startFrame + 15, 0.8, 1, Easing.out(Easing.back(1.7)))})`,
  });

  // STOCK BRAIN animation
  const stockBrainOp = ip(f, 330, 360, 0, 1);
  const stockBrainScale = ip(f, 330, 360, 0.8, 1, Easing.out(Easing.back(1.7)));
  const stockBrainGlow = interpolate(f, [330, 390, 420, 480], [10, 40, 10, 40], {extrapolateLeft:'clamp', extrapolateRight:'clamp', easing: Easing.inOut(Easing.quad)}); // Pulsating glow
  const stockBrainColor = f % 60 < 30 ? C.main : '#FFA502'; // Alternating color

  // Phase 2: 450-900 frames (15-30s)
  const speedTextOp = ip(f, 500, 530, 0, 1);
  const speedTextScale = ip(f, 500, 530, 0.8, 1, Easing.out(Easing.back(1.7)));
  const speedTextTranslateY = ip(f, 500, 680, 0, -20); // Slight upward movement

  const gapTextOp = ip(f, 700, 730, 0, 1);
  const gapTextScale = ip(f, 700, 730, 0.8, 1, Easing.out(Easing.back(1.7)));

  // Visual for "정보의 격차 극복"
  const gapRectWidth = ip(f, 700, 780, 400, 0, Easing.out(Easing.cubic)); // Gap closing
  const aiRectWidth = ip(f, 700, 780, 0, 400, Easing.out(Easing.cubic)); // AI filling
  const aiRectOpacity = ip(f, 700, 730, 0, 1);

  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14', overflow: 'hidden' }}>
      <Html5Audio src={staticFile('voice/yt_ai_s06_awareness.m4a')} />

      {/* Background UI Graphics */}
      <AbsoluteFill style={{
        opacity: uiOpacity,
        transform: `scale(${uiScale}) rotate(${uiRotation}deg)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {/* Grid lines */}
        <div style={{
          position: 'absolute', width: '100%', height: '100%',
          backgroundImage: `
            linear-gradient(to right, rgba(0,255,208,0.1) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(0,255,208,0.1) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }} />

        {/* Central glowing circle/data hub */}
        <div style={{
          width: 400, height: 400, borderRadius: '50%',
          background: `radial-gradient(circle, rgba(0,255,208,0.3) 0%, rgba(0,255,208,0) 70%)`,
          boxShadow: `0 0 80px rgba(0,255,208,0.5), 0 0 160px rgba(0,255,208,0.2)`,
          opacity: ip(f, 0, 60, 0, 1) * ip(f, 850, 900, 1, 0),
          transform: `scale(${ip(f, 0, 900, 1, 1.1)})`,
        }} />

        {/* Data lines/streams */}
        {[...Array(8)].map((_, i) => {
          const delay = i * 10;
          const lineOp = ip(f, delay, delay + 30, 0, 0.4);
          const lineLength = ip(f, delay, delay + 120, 0, 800);
          const angle = (i / 8) * 360 + ip(f, 0, 900, 0, 360); // Rotate over time
          return (
            <div key={i} style={{
              position: 'absolute',
              width: lineLength,
              height: 2,
              background: `linear-gradient(to right, transparent, ${C.main}, transparent)`,
              opacity: lineOp,
              transform: `rotate(${angle}deg) translateX(${lineLength / 2}px)`,
              transformOrigin: 'left center',
            }} />
          );
        })}
      </AbsoluteFill>

      {/* Main Content Area - Assuming 로또님 is here or a placeholder */}
      <AbsoluteFill style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        paddingBottom: '16%', // For subtitle bar
      }}>
        {/* Phase 1 Keywords */}
        <div style={{ position: 'absolute', top: '20%', left: '10%' }}>
          <div style={keywordStyle(0, 100, '#FF4757')}>밤샘 분석</div>
        </div>
        <div style={{ position: 'absolute', top: '35%', right: '10%' }}>
          <div style={keywordStyle(120, 300, '#FFA502')}>새벽 4시</div>
        </div>
        <div style={{ position: 'absolute', top: '50%', left: '20%' }}>
          <div style={keywordStyle(180, 300, C.main)}>핵심 정보</div>
        </div>

        {/* STOCK BRAIN */}
        <div style={{
          fontFamily: FONT,
          fontSize: 120,
          color: stockBrainColor,
          textShadow: `0 0 ${stockBrainGlow}px ${stockBrainColor}, 0 0 ${stockBrainGlow * 2}px rgba(0,255,208,0.5)`,
          opacity: stockBrainOp,
          transform: `scale(${stockBrainScale})`,
          position: 'absolute',
          top: '40%',
        }}>
          STOCK BRAIN
        </div>
        <div style={{
          fontFamily: FONT,
          fontSize: 48,
          color: '#FFF',
          opacity: ip(f, 360, 390, 0, 1),
          position: 'absolute',
          top: '55%',
        }}>
          든든한 조력자
        </div>

        {/* Phase 2 Keywords */}
        <div style={{
          position: 'absolute',
          top: '30%',
          opacity: speedTextOp,
          transform: `scale(${speedTextScale}) translateY(${speedTextTranslateY}px)`,
          textAlign: 'center',
        }}>
          <span style={{ ...keywordStyle(500, 680, C.main), fontSize: 96 }}>남들보다 빠르게</span>
          <br />
          <span style={{ ...keywordStyle(550, 680, '#FFA502'), fontSize: 96 }}>그리고 정확하게</span>
        </div>

        {/* 정보의 격차 극복 visual */}
        <div style={{
          position: 'absolute',
          bottom: '25%', // Above subtitle bar
          display: 'flex',
          alignItems: 'center',
          opacity: gapTextOp,
          transform: `scale(${gapTextScale})`,
        }}>
          <div style={{
            fontFamily: FONT,
            fontSize: 60,
            color: '#FF4757',
            marginRight: 20,
            textShadow: dynGlow,
          }}>
            정보의 격차
          </div>
          <div style={{
            width: 400, height: 40,
            background: '#FF4757', // Base color for the gap
            borderRadius: 5,
            position: 'relative',
            overflow: 'hidden',
          }}>
            <div style={{
              position: 'absolute',
              left: 0, top: 0, bottom: 0,
              width: gapRectWidth,
              background: '#FF4757', // The actual gap part
            }} />
            <div style={{
              position: 'absolute',
              right: 0, top: 0, bottom: 0,
              width: aiRectWidth,
              background: C.main, // AI filling the gap
              opacity: aiRectOpacity,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: FONT,
              fontSize: 36,
              color: '#080c14',
            }}>
              AI
            </div>
          </div>
          <div style={{
            fontFamily: FONT,
            fontSize: 60,
            color: C.main,
            marginLeft: 20,
            textShadow: dynGlow,
          }}>
            극복
          </div>
        </div>
        <div style={{
          position: 'absolute',
          bottom: '18%',
          fontFamily: FONT,
          fontSize: 72,
          color: C.main,
          textShadow: dynGlow,
          opacity: ip(f, 780, 810, 0, 1),
          transform: `scale(${ip(f, 780, 810, 0.8, 1, Easing.out(Easing.back(1.7)))})`,
        }}>
          정보의 천재
        </div>

      </AbsoluteFill>

      {/* Subtitle Bar */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:'16%',
        display:'flex',alignItems:'center',justifyContent:'center',paddingInline:80,
        background:'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)'}}>
        {sub&&<div style={{color:'#FFF',fontSize:40,fontWeight:700,textAlign:'center',
          opacity:sub.op,textShadow:'0 2px 8px rgba(0,0,0,0.9)'}}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};