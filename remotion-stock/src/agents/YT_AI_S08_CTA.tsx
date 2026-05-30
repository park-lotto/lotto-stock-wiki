// YT_AI_S08_CTA — 씬 8 CTA (750프레임 / 25초)
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
  { s: 0,   e: 150, text: '오늘 보여드린 STOCK BRAIN이 궁금하시다면,' },
  { s: 210, e: 360, text: '댓글에 \'로또AI\'라고 남겨주세요!' },
  { s: 360, e: 540, text: '선착순으로 서비스 대기 신청 링크를 드립니다.' },
  { s: 540, e: 750, text: '지금 바로 댓글 남겨주시고, AI와 함께하는 새로운 투자 경험을 시작하세요!' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

export const YT_AI_S08_CTA: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  // Global pulse for dynamic glow
  const pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz = interpolate(pulse, [0, 1], [10, 30]);
  const mainGlow = `0 0 ${gSz}px ${C.main}, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`; // For C.main (#00FFD0)
  const accentGlow = `0 0 ${gSz}px #FFA502, 0 0 ${gSz * 2}px rgba(255,165,2,0.5)`; // For #FFA502

  // ━━━━ Phase 1 (0-15s / f0-450)
  // "오늘 보여드린 STOCK BRAIN이 궁금하시다면,"
  const introTextOp = ip(f, 0, 30, 0, 1) * ip(f, 120, 150, 1, 0); // Appears, then fades out before pause
  const stockBrainGlowOp = ip(f, 30, 90, 0.5, 1) * ip(f, 90, 120, 1, 0.5); // Glows during its active phase

  // "댓글에 '로또AI'라고 남겨주세요!"
  const ctaTextOp = ip(f, 210, 240, 0, 1);
  const ctaTextScale = ip(f, 210, 240, 0.8, 1, Easing.out(Easing.back(1.7)));
  const lottoAIGlowOp = ip(f, 240, 300, 0.5, 1) * ip(f, 300, 360, 1, 0.5);

  // Comment box UI
  const commentBoxY = ip(f, 210, 270, 1080, 700, Easing.out(Easing.cubic)); // Slides up from bottom
  const commentBoxOp = ip(f, 210, 240, 0, 1);

  // ━━━━ Phase 2 (15-25s / f450-750)
  // "선착순으로 서비스 대기 신청 링크를 드립니다."
  const secondaryCtaOp = ip(f, 450, 480, 0, 1);
  const secondaryCtaScale = ip(f, 450, 480, 0.8, 1, Easing.out(Easing.back(1.7)));
  const firstComeGlowOp = ip(f, 480, 540, 0.5, 1) * ip(f, 540, 600, 1, 0.5);

  // "지금 바로 댓글 남겨주시고, AI와 함께하는 새로운 투자 경험을 시작하세요!"
  const finalCtaOp = ip(f, 540, 570, 0, 1);
  const finalCtaScale = ip(f, 540, 570, 0.8, 1, Easing.out(Easing.back(1.7)));
  const newExperienceGlowOp = ip(f, 570, 630, 0.5, 1) * ip(f, 630, 690, 1, 0.5);

  // Link/Button UI
  const linkButtonY = ip(f, 480, 540, 1080, 850, Easing.out(Easing.cubic));
  const linkButtonOp = ip(f, 480, 510, 0, 1);

  return (
    <AbsoluteFill style={{ backgroundColor: '#080c14', overflow: 'hidden' }}>
      <Html5Audio src={staticFile('voice/yt_ai_s08_cta.m4a')} />

      {/* Phase 1: Intro Text */}
      <div style={{
        position: 'absolute',
        top: '20%',
        width: '100%',
        textAlign: 'center',
        opacity: introTextOp,
        transform: `scale(${ip(f, 0, 30, 0.8, 1)})`,
        fontFamily: FONT,
        fontSize: 60,
        fontWeight: 700,
        color: '#FFF',
        textShadow: '0 2px 8px rgba(0,0,0,0.9)',
      }}>
        오늘 보여드린 <span style={{ color: C.main, textShadow: mainGlow, opacity: stockBrainGlowOp }}>STOCK BRAIN</span>이 궁금하시다면,
      </div>

      {/* Phase 1: Main CTA Text */}
      <div style={{
        position: 'absolute',
        top: '40%',
        width: '100%',
        textAlign: 'center',
        opacity: ctaTextOp,
        transform: `scale(${ctaTextScale})`,
        fontFamily: FONT,
        fontSize: 80,
        fontWeight: 900,
        color: '#FFF',
        textShadow: '0 4px 12px rgba(0,0,0,0.9)',
      }}>
        댓글에 <span style={{ color: C.main, textShadow: mainGlow, opacity: lottoAIGlowOp }}>'로또AI'</span>라고 남겨주세요!
      </div>

      {/* Phase 1: Comment Box UI */}
      <div style={{
        position: 'absolute',
        left: '50%',
        transform: `translateX(-50%)`,
        top: commentBoxY,
        width: 800,
        height: 120,
        backgroundColor: '#1a202c',
        borderRadius: 20,
        border: `4px solid ${C.main}`,
        boxShadow: mainGlow,
        opacity: commentBoxOp,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
        boxSizing: 'border-box',
      }}>
        <div style={{
          fontFamily: FONT,
          fontSize: 40,
          color: '#9ca3af',
        }}>
          '로또AI' 라고 입력...
        </div>
        <div style={{
          position: 'absolute',
          right: 20,
          padding: '10px 20px',
          backgroundColor: C.main,
          borderRadius: 10,
          fontFamily: FONT,
          fontSize: 32,
          fontWeight: 700,
          color: '#080c14',
          cursor: 'pointer',
          boxShadow: `0 0 10px ${C.main}`,
        }}>
          댓글
        </div>
      </div>

      {/* Phase 2: Secondary CTA Text */}
      <div style={{
        position: 'absolute',
        top: '60%',
        width: '100%',
        textAlign: 'center',
        opacity: secondaryCtaOp,
        transform: `scale(${secondaryCtaScale})`,
        fontFamily: FONT,
        fontSize: 50,
        fontWeight: 700,
        color: '#FFF',
        textShadow: '0 2px 8px rgba(0,0,0,0.9)',
      }}>
        <span style={{ color: '#FFA502', textShadow: accentGlow, opacity: firstComeGlowOp }}>선착순으로</span> 서비스 대기 신청 링크를 드립니다.
      </div>

      {/* Phase 2: Link/Button UI */}
      <div style={{
        position: 'absolute',
        left: '50%',
        transform: `translateX(-50%)`,
        top: linkButtonY,
        width: 700,
        height: 100,
        backgroundColor: '#FFA502',
        borderRadius: 15,
        border: `3px solid #FFA502`,
        boxShadow: `0 0 15px #FFA502`,
        opacity: linkButtonOp,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
      }}>
        <div style={{
          fontFamily: FONT,
          fontSize: 45,
          fontWeight: 800,
          color: '#080c14',
        }}>
          서비스 대기 신청 링크 받기
        </div>
        <div style={{
          position: 'absolute',
          right: 25,
          fontSize: 50,
          color: '#080c14',
        }}>
          ➡️
        </div>
      </div>

      {/* Phase 2: Final CTA Text */}
      <div style={{
        position: 'absolute',
        top: '75%',
        width: '100%',
        textAlign: 'center',
        opacity: finalCtaOp,
        transform: `scale(${finalCtaScale})`,
        fontFamily: FONT,
        fontSize: 40,
        fontWeight: 600,
        color: '#FFF',
        textShadow: '0 2px 6px rgba(0,0,0,0.8)',
      }}>
        지금 바로 댓글 남겨주시고, AI와 함께하는 <span style={{ color: C.main, textShadow: mainGlow, opacity: newExperienceGlowOp }}>새로운 투자 경험</span>을 시작하세요!
      </div>


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