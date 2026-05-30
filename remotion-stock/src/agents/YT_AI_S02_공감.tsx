// YT_AI_S02_공감 — 씬2 공감 (1350프레임 / 45초)

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
  { s: 0,   e: 150, text: '여러분, 매일 아침 텔레그램 100개 채널, 유튜브 5개, 증권사 리포트까지...' },
  { s: 150, e: 270, text: '이 모든 정보를 다 보시느라 정말 힘드시죠?' },
  { s: 270, e: 570, text: '핵심을 놓칠까 봐 불안하고, 밤샘 분석에 지쳐서 정작 중요한 매매 타이밍을 놓치신 적도 많으실 겁니다.' },
  { s: 570, e: 810, text: '그래서 어제도, 그제도, 놓친 종목이 대체 몇 개나 되십니까?' },
  { s: 810, e: 1080, text: '정보의 홍수 속에서 진짜 \'황금 같은 기회\'를 놓치고 계시지는 않나요?' },
  { s: 1080, e: 1350, text: '남들보다 빠르게, 핵심 정보만 쏙쏙 뽑아볼 수 있다면 얼마나 좋을까요?' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// ── 아이콘 데이터 ─────────────────────────────────────────────────
const ICONS_DATA = [
  { id: 'telegram', src: staticFile('icons/telegram.png'), text: '100개 채널', start: 30, end: 450, x: 200, y: 300 },
  { id: 'youtube', src: staticFile('icons/youtube.png'), text: '5개', start: 180, end: 450, x: 800, y: 200 },
  { id: 'pdf', src: staticFile('icons/pdf.png'), text: '리포트', start: 330, end: 450, x: 1400, y: 350 },
];

export const YT_AI_S02_공감: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const bgGlow = Math.sin(f * 0.04) * 0.028 + 0.05;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // ━━━━ Phase 1: 0-450 frames (0-15s)
  const phase1Active = f < 450;

  // ━━━━ Phase 2: 450-900 frames (15-30s)
  const phase2Active = f >= 450 && f < 900;
  const phase2TextOp = ip(f, 450, 480);
  const tiredPersonOp = ip(f, 500, 530);

  // ━━━━ Phase 3: 900-1350 frames (30-45s)
  const phase3Active = f >= 900;
  const phase3TextOp = ip(f, 960, 990);
  const lostStockBlink = Math.sin(f * 0.3) > 0; // Simple blink

  // Background elements (abstract lines/dots)
  const renderBackground = (opacity: number, density: number, blur: number = 0, chaos: number = 0) => (
    <div style={{
      position: 'absolute',
      width: '100%',
      height: '100%',
      backgroundColor: '#080c14',
      opacity: opacity,
      filter: `blur(${blur}px)`,
    }}>
      {Array.from({ length: Math.floor(100 * density) }).map((_, i) => {
        const x = (i * 13 + f * 0.1 * (1 + chaos)) % 1920;
        const y = (i * 17 + f * 0.05 * (1 + chaos)) % 1080;
        const size = 5 + Math.sin(f * 0.1 + i) * 3;
        const color = i % 3 === 0 ? '#00FFD0' : i % 3 === 1 ? '#FFA502' : '#FF4757';
        const glow = `0 0 ${size * 2}px ${color}`;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: size,
              height: size,
              borderRadius: '50%',
              backgroundColor: color,
              boxShadow: glow,
              opacity: ip(f, 0, 30, 0, 0.5) * opacity,
              transform: `scale(${ip(f, i * 5, i * 5 + 30, 0.5, 1.2, Easing.out(Easing.back))})`,
            }}
          />
        );
      })}
      {Array.from({ length: Math.floor(50 * density) }).map((_, i) => {
        const x1 = (i * 20 + f * 0.2 * (1 + chaos)) % 1920;
        const y1 = (i * 25 + f * 0.1 * (1 + chaos)) % 1080;
        const x2 = (x1 + 100 + Math.sin(f * 0.05 + i) * 50) % 1920;
        const y2 = (y1 + 50 + Math.cos(f * 0.08 + i) * 30) % 1080;
        const color = i % 2 === 0 ? '#00FFD0' : '#FFA502';
        const lineWidth = 2 + Math.sin(f * 0.05 + i) * 1;
        const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
        const length = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
        return (
          <div
            key={`line-${i}`}
            style={{
              position: 'absolute',
              left: x1,
              top: y1,
              width: length,
              height: lineWidth,
              backgroundColor: color,
              boxShadow: `0 0 ${lineWidth * 2}px ${color}`,
              opacity: ip(f, 0, 30, 0, 0.3) * opacity,
              transform: `rotate(${angle}deg)`,
              transformOrigin: '0 0',
            }}
          />
        );
      })}
    </div>
  );


  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14', overflow: 'hidden' }}>
      <Html5Audio src={staticFile('voice/yt_ai_s02_공감.m4a')} />

      {/* Background */}
      {renderBackground(
        ip(f, 0, 30), // Fade in
        phase3Active ? 2 : 1, // Density increases in phase 3
        phase2Active ? 5 : 0, // Blur in phase 2
        phase3Active ? 1 : 0 // Chaos increases in phase 3
      )}

      {/* Phase 1: Icons and Numbers */}
      {phase1Active && ICONS_DATA.map((icon, i) => {
        const iconOp = ip(f, icon.start, icon.start + 30);
        const textOp = ip(f, icon.start + 30, icon.start + 60);
        const scale = ip(f, icon.start, icon.start + 15, 0.5, 1, Easing.out(Easing.back));
        const yOffset = ip(f, icon.start, icon.start + 30, 50, 0, Easing.out(Easing.cubic));
        const glowPulse = Math.sin(f * 0.1 + i) * 0.5 + 0.5;
        const iconGlowSz = interpolate(glowPulse, [0, 1], [10, 25]);
        const iconDynGlow = `0 0 ${iconGlowSz}px #00FFD0, 0 0 ${iconGlowSz * 2}px rgba(0,255,208,0.5)`;

        return (
          <div key={icon.id} style={{
            position: 'absolute',
            left: icon.x,
            top: icon.y + yOffset,
            opacity: iconOp,
            transform: `scale(${scale})`,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 20,
          }}>
            <img src={icon.src} style={{ width: 150, height: 150, boxShadow: iconDynGlow }} />
            <div style={{
              fontFamily: FONT,
              fontSize: 48,
              fontWeight: 700,
              color: '#FFF',
              textShadow: '0 0 10px rgba(0,255,208,0.8)',
              opacity: textOp,
            }}>{icon.text}</div>
          </div>
        );
      })}

      {/* Phase 2: Central text and tired person */}
      {phase2Active && (
        <>
          <div style={{
            position: 'absolute',
            top: '30%',
            width: '100%',
            textAlign: 'center',
            fontFamily: FONT,
            fontSize: 72,
            fontWeight: 800,
            color: '#FFF',
            textShadow: dynGlow,
            opacity: phase2TextOp,
            paddingInline: 80,
          }}>
            매일 아침 텔레그램 100개 채널, 유튜브 5개, 증권사 리포트까지...
            <br />
            다 보시느라 정말 힘드시죠?
          </div>
          <img
            src={staticFile('images/tired_person.png')} // Placeholder for tired person image
            style={{
              position: 'absolute',
              bottom: '18%', // Above subtitle bar
              left: '50%',
              transform: 'translateX(-50%)',
              width: 400,
              height: 'auto',
              opacity: tiredPersonOp,
              filter: `drop-shadow(${dynGlow})`,
            }}
          />
        </>
      )}

      {/* Phase 3: Question and blinking text */}
      {phase3Active && (
        <div style={{
          position: 'absolute',
          top: '35%',
          width: '100%',
          textAlign: 'center',
          fontFamily: FONT,
          fontSize: 80,
          fontWeight: 800,
          color: '#FFF',
          textShadow: dynGlow,
          opacity: phase3TextOp,
          paddingInline: 80,
        }}>
          그래서 어제도, 그제도,
          <br />
          <span style={{
            color: '#FF4757', // Red for emphasis
            textShadow: lostStockBlink ? `0 0 30px #FF4757, 0 0 60px rgba(255,71,87,0.5)` : 'none',
            transition: 'text-shadow 0.1s ease-in-out',
          }}>
            놓친 종목
          </span>
          이 대체 몇 개나 되십니까?
        </div>
      )}

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