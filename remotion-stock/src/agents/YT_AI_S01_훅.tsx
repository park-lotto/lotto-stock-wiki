// YT_AI_S01_훅 — 씬1 훅 (750프레임 / 25초)
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { FONT } from '../constants';

function ip(f: number, a: number, b: number, from = 0, to = 1, ease: (t: number) => number = Easing.out(Easing.cubic)) {
  return interpolate(f, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });
}

// ── 자막 세그먼트 ─────────────────────────────────────────────────
const SUBS = [
  { s: 0,   e: 240, text: "매일 아침, 수백 개의 뉴스, 리포트, 텔레그램 속에서 진짜 '오늘 오를 대장주'를 1분 만에 찾아주는 미친 AI가 있다면 믿으시겠습니까?" },
  { s: 300, e: 750, text: "저는 매일 새벽 4시, 이 AI 덕분에 정보 노가다 없이 여유롭게 시장을 선점합니다." },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  // Fade in/out for subtitles over 15 frames
  const op = Math.min((f - seg.s) / 15, 1, (seg.e - f) / 15);
  return { text: seg.text, op };
}

// ── 정보 요소 데이터 ──────────────────────────────────────────────
const INFO_ELEMENTS = Array.from({ length: 25 }).map((_, i) => ({
  id: i,
  type: i % 3 === 0 ? 'news' : i % 3 === 1 ? 'telegram' : 'pdf',
  text: `AI가 필요한 이유: 정보 과부하 시대의 생존 전략 ${i+1}`,
  x: Math.random() * 1920,
  y: Math.random() * 1080,
  speedX: (Math.random() - 0.5) * 1.5, // -0.75 to 0.75 pixels per frame
  speedY: (Math.random() - 0.5) * 1.5,
  rotationSpeed: (Math.random() - 0.5) * 0.2, // -0.1 to 0.1 degrees per frame
  initialRotation: Math.random() * 360,
}));

export const YT_AI_S01_훅: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const bgGlow = Math.sin(f * 0.04) * 0.028 + 0.05;
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;

  // Phase 1: Chaotic information (0-300 frames)
  const phase1Opacity = ip(f, 0, 30, 0, 1); // Fade in chaos elements
  const phase1Out = ip(f, 270, 330, 1, 0); // Fade out chaos elements

  // Phase 2: Lotto님 and AI graphics (300-750 frames)
  const lottoIn = ip(f, 300, 360, 0, 1, Easing.out(Easing.back(1.7))); // Lotto님 fade in with a slight bounce
  const aiGraphicOpacity = ip(f, 330, 390, 0, 1); // AI graphic fade in
  const aiGraphicPulse = Math.sin(f * 0.1) * 0.5 + 0.5; // Pulsing effect for AI graphic

  // Emphasized keywords animation
  // "미친 AI" (0-240)
  const keyword1Scale = ip(f, 150, 180, 0.5, 1, Easing.out(Easing.back(1.7)));
  const keyword1Op = ip(f, 150, 180, 0, 1) * ip(f, 220, 250, 1, 0);

  // "정보 노가다" (300-750)
  const keyword2Scale = ip(f, 380, 410, 0.5, 1, Easing.out(Easing.back(1.7)));
  const keyword2Op = ip(f, 380, 410, 0, 1) * ip(f, 450, 480, 1, 0);

  // "시장 선점" (300-750)
  const keyword3Scale = ip(f, 580, 610, 0.5, 1, Easing.out(Easing.back(1.7)));
  const keyword3Op = ip(f, 580, 610, 0, 1) * ip(f, 650, 680, 1, 0);

  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14', overflow: 'hidden' }}>
      <Html5Audio src={staticFile('voice/yt_ai_s01_hook.m4a')} />

      {/* Background glow for overall scene */}
      <div style={{
        position: 'absolute', inset: -100,
        background: `radial-gradient(circle at center, rgba(0,255,208,${bgGlow}) 0%, transparent 70%)`,
        opacity: ip(f, 0, 30, 0, 1),
      }} />

      {/* Phase 1: Chaotic Information */}
      {INFO_ELEMENTS.map(el => {
        const x = (el.x + f * el.speedX) % (1920 + 400) - 200; // Allow elements to go off-screen and wrap
        const y = (el.y + f * el.speedY) % (1080 + 400) - 200;
        const rot = (el.initialRotation + f * el.rotationSpeed) % 360;
        const scale = ip(f, 0, 30, 0.5, 1); // Initial scale up, then static

        let content;
        let bgColor;
        let textColor = '#FFF';
        let borderColor = 'transparent';
        let padding = 16;
        let width = 300;
        let height = 150;

        if (el.type === 'news') {
          bgColor = 'rgba(26,32,44,0.8)';
          borderColor = '#00FFD0';
          content = (
            <>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#00FFD0', marginBottom: 8 }}>Breaking News</div>
              <div style={{ fontSize: 20, fontWeight: 500 }}>{el.text.slice(0, 30)}...</div>
            </>
          );
        } else if (el.type === 'telegram') {
          bgColor = 'rgba(44,62,80,0.8)';
          borderColor = '#FFA502';
          content = (
            <>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#FFA502', marginBottom: 4 }}>Telegram Alert</div>
              <div style={{ fontSize: 18 }}>{el.text.slice(0, 40)}</div>
            </>
          );
        } else { // pdf
          bgColor = 'rgba(52,73,94,0.8)';
          borderColor = '#FF4757';
          content = (
            <>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#FF4757', marginBottom: 8 }}>PDF Report</div>
              <div style={{ fontSize: 16 }}>Confidential Analysis...</div>
            </>
          );
          width = 250;
          height = 200;
        }

        return (
          <div
            key={el.id}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: width,
              height: height,
              background: bgColor,
              border: `2px solid ${borderColor}`,
              borderRadius: 12,
              padding: padding,
              color: textColor,
              fontFamily: FONT,
              transform: `rotate(${rot}deg) scale(${scale})`,
              boxShadow: `0 0 15px rgba(0,255,208,0.3)`,
              opacity: phase1Opacity * phase1Out, // Fade in and out with phase
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              textAlign: 'center',
              filter: `blur(${ip(f, 270, 330, 0, 5)}px)`, // Blur out during transition
            }}
          >
            {content}
          </div>
        );
      })}

      {/* Phase 2: Lotto님 and AI graphics */}
      <div style={{
        position: 'absolute',
        width: '100%',
        height: '100%',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        opacity: lottoIn,
      }}>
        {/* AI Graphic Effect */}
        <div style={{
          position: 'absolute',
          width: 800,
          height: 800,
          borderRadius: '50%',
          background: `radial-gradient(circle at center, rgba(0,255,208,${aiGraphicPulse * 0.3}) 0%, transparent 70%)`,
          boxShadow: `0 0 ${aiGraphicPulse * 50 + 20}px rgba(0,255,208,0.7)`,
          opacity: aiGraphicOpacity,
          transform: `scale(${1 + aiGraphicPulse * 0.1})`,
        }} />
        <div style={{
          position: 'absolute',
          width: 600,
          height: 600,
          borderRadius: '50%',
          border: `4px solid rgba(0,255,208,${aiGraphicPulse * 0.8})`,
          opacity: aiGraphicOpacity,
          transform: `scale(${1 - aiGraphicPulse * 0.05}) rotate(${f * 0.2}deg)`,
        }} />
        <div style={{
          position: 'absolute',
          width: 700,
          height: 700,
          borderRadius: '50%',
          border: `2px dashed rgba(0,255,208,${aiGraphicPulse * 0.5})`,
          opacity: aiGraphicOpacity,
          transform: `scale(${1 + aiGraphicPulse * 0.02}) rotate(${f * -0.1}deg)`,
        }} />

        {/* Lotto님 Image - Placeholder, assuming a static image */}
        <img
          src={staticFile('lotto.png')} // Placeholder image. Replace with actual image path.
          alt="Lotto님"
          style={{
            width: 500,
            height: 500,
            borderRadius: '50%',
            objectFit: 'cover',
            boxShadow: dynGlow,
            opacity: lottoIn,
            transform: `scale(${1 + pulse * 0.02})`,
            zIndex: 10,
          }}
        />
      </div>

      {/* Emphasized Keywords */}
      <div style={{
        position: 'absolute',
        top: '20%',
        left: '50%',
        transform: `translateX(-50%) scale(${keyword1Scale})`,
        fontFamily: FONT,
        fontSize: 60,
        fontWeight: 900,
        color: '#FFF',
        textAlign: 'center',
        textShadow: '0 0 10px rgba(0,255,208,0.8)',
        zIndex: 20,
        opacity: keyword1Op,
      }}>
        <span style={{ color: '#00FFD0' }}>미친 AI</span>
      </div>
      <div style={{
        position: 'absolute',
        top: '40%',
        left: '50%',
        transform: `translateX(-50%) scale(${keyword2Scale})`,
        fontFamily: FONT,
        fontSize: 60,
        fontWeight: 900,
        color: '#FFF',
        textAlign: 'center',
        textShadow: '0 0 10px rgba(255,165,2,0.8)',
        zIndex: 20,
        opacity: keyword2Op,
      }}>
        <span style={{ color: '#FFA502' }}>정보 노가다</span>
      </div>
      <div style={{
        position: 'absolute',
        top: '60%',
        left: '50%',
        transform: `translateX(-50%) scale(${keyword3Scale})`,
        fontFamily: FONT,
        fontSize: 60,
        fontWeight: 900,
        color: '#FFF',
        textAlign: 'center',
        textShadow: '0 0 10px rgba(255,71,87,0.8)',
        zIndex: 20,
        opacity: keyword3Op,
      }}>
        <span style={{ color: '#FF4757' }}>시장 선점</span>
      </div>


      {/* Subtitle bar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', paddingInline: 80,
        background: 'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)'
      }}>
        {sub && <div style={{
          color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center',
          opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)', fontFamily: FONT
        }}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};