// GB06 — 씬6 CTA Whisper 싱크 (10s 오디오 + 구독 애니 = 600프레임)
// Whisper: f0~235 "AI직원 자료...계속 보여드릴 테니까" / f235~300 "구독 누르시면..."
// Phase1 f0~235 / Phase2 f235~600 (오디오 끝 후 구독 버튼 애니 계속)
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO     = 'audio/국씬6.m4a';
const HAS_AUDIO = true;

const fi = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const fo = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const lr = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

const NEXT_ITEMS = [
  { icon: '🤖', title: 'AI 직원들이 만든 자료', desc: '수집·분석·알림까지 자동 브리핑 계속 공개' },
  { icon: '📡', title: '다음 영상에서도 이어집니다', desc: '구독하시면 절대 놓치지 않습니다' },
];

export const GB06_CTA = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.045;

  // ─── Phase 전환 (Whisper 기준) ───
  // f235 "구독 누르시면" 시작에 맞춰 Phase2 전환
  const showPh1 = f < 198 ? fi(0, 18)(f) : fo(198, 235)(f);
  const showPh2 = f < 235 ? 0 : fi(235, 268)(f);

  // ─── Phase1 ───
  const diagX  = lr(-120, 120, 0, 40)(f);
  const diagOp = f < 40 ? interpolate(f, [0, 4, 32, 40], [0, 1, 1, 0]) : 0;

  const p1LabelOp = fi(10, 40)(f);
  const p1TitleOp = fi(30, 68)(f);
  const p1TitleY  = lr(40, 0, 30, 68)(f);

  // 카드 2개 f235 이전에 다 등장 (기존 [90,180] → [55,130])
  const cardS = [55, 130];
  const cardAnims = cardS.map(s => ({
    op:    fi(s, s + 40)(f),
    tx:    lr(-80, 0, s, s + 40)(f),
    scale: lr(0.92, 1, s, s + 40)(f),
    scanY: lr(0, 110, s + 12, s + 30)(f),
    scanO: f >= s + 12 && f < s + 30 ? interpolate(f, [s+12, s+16, s+26, s+30], [0, 0.9, 0.9, 0]) : 0,
  }));

  const allVis = f >= 185;
  const ringPh = allVis ? ((f - 185) % 70) / 70 : 0;
  const cardGlow = (i: number) => {
    if (!allVis) return 0;
    const center = i / 2 + 0.25;
    const dist = Math.min(Math.abs(ringPh - center), 1 - Math.abs(ringPh - center));
    return Math.max(0, 1 - dist * 2 * 1.8);
  };

  const sub1Op = fi(185, 225)(f);
  const sub1Y  = lr(20, 0, 185, 225)(f);

  // ─── Phase2 ───
  const diag2X  = lr(-120, 120, 235, 268)(f);
  const diag2Op = f >= 235 && f < 268 ? interpolate(f, [235, 239, 260, 268], [0, 1, 1, 0]) : 0;

  const chIconSc  = interpolate(f, [280, 315], [0.4, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const chIconOp  = fi(280, 295)(f);
  const chNameOp  = fi(315, 353)(f);
  const chNameY   = lr(70, 0, 315, 353)(f);
  const chNameLs  = lr(12, -2, 315, 353)(f);
  const sloganOp  = fi(360, 390)(f);
  const sloganY   = lr(30, 0, 360, 390)(f);

  const btnOp     = fi(410, 448)(f);
  const btnScale  = interpolate(f, [410, 448], [0.4, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const btnMag    = Math.min(1, (f - 410) / 50);
  const btnPulse  = Math.sin(f * 0.1) * 0.5 + 0.5;
  const btnGlow   = `0 0 ${interpolate(btnPulse, [0, 1], [16, 32]) * btnMag}px rgba(0,255,208,${0.7 * btnMag}), 0 0 ${interpolate(btnPulse, [0, 1], [24, 48]) * btnMag}px rgba(0,255,208,${0.35 * btnMag})`;
  const iconPulse = Math.sin(f * 0.08) * 0.015 + 1;

  const bgGlowAmp = interpolate(f, [410, 570], [0, 0.06], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const bgGlowPh2 = Math.sin(f * 0.05) * 0.04 + 0.06 + bgGlowAmp;

  // 파티클
  const PARTICLES = [
    { x: 22, delay: 10, size: 5 }, { x: 38, delay: 25, size: 7 },
    { x: 55, delay: 5,  size: 4 }, { x: 68, delay: 35, size: 6 },
    { x: 78, delay: 15, size: 5 }, { x: 88, delay: 40, size: 4 },
  ];

  const cap1 = showPh1 > 0.5 ? fi(165, 205)(f) : 0;  // Phase1 후반 (f235 직전)
  const cap2 = showPh2 > 0.1 ? fi(460, 500)(f) : 0;  // 버튼 등장 직후

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: `radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)`, opacity: showPh2 > 0.5 ? bgGlowPh2 : bgGlow }} />

      {/* 대각선 스윕 */}
      {[{ x: diagX, op: diagOp * showPh1 }, { x: diag2X, op: diag2Op }].map(({ x, op }, i) => (
        <div key={i} style={{ position: 'absolute', top: '-20%', bottom: '-20%', left: `${x}%`, width: 60, background: 'linear-gradient(90deg, transparent 0%, rgba(0,255,208,0.6) 40%, rgba(128,255,232,0.9) 50%, rgba(0,255,208,0.6) 60%, transparent 100%)', transform: 'rotate(30deg)', transformOrigin: 'center center', opacity: op, pointerEvents: 'none', zIndex: 10 }} />
      ))}

      {/* ═══ PHASE 1 ═══ */}
      <AbsoluteFill style={{ opacity: showPh1, pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingInline: 140, gap: 28 }}>
          <div style={{ fontSize: 28, fontWeight: 500, color: C.textSub, letterSpacing: 5, opacity: p1LabelOp }}>다음 영상 예고</div>
          <div style={{ fontSize: 80, fontWeight: 900, color: C.textPrimary, opacity: p1TitleOp, transform: `translateY(${p1TitleY}px)`, lineHeight: 1, textAlign: 'center' }}>
            AI 직원들 자료&nbsp;<span style={{ color: C.main, textShadow: GLOW.mid.text }}>계속 보여드립니다</span>
          </div>

          <div style={{ display: 'flex', gap: 28, width: '100%' }}>
            {NEXT_ITEMS.map((item, i) => {
              const g = cardGlow(i);
              return (
                <div key={i} style={{ flex: 1, opacity: cardAnims[i].op, transform: `translateX(${cardAnims[i].tx}px) scale(${cardAnims[i].scale})`, background: C.cardBg, border: `1.5px solid ${g > 0.3 ? C.main : C.borderSub}`, borderRadius: 20, padding: '28px 32px', position: 'relative', overflow: 'hidden', boxShadow: g > 0.2 ? `0 0 ${16*g}px rgba(0,255,208,${0.5*g})` : 'none' }}>
                  <div style={{ position: 'absolute', left: 0, right: 0, top: `${cardAnims[i].scanY}%`, height: 1, background: 'linear-gradient(90deg, transparent, rgba(0,255,208,0.6), transparent)', opacity: cardAnims[i].scanO }} />
                  <div style={{ fontSize: 68, marginBottom: 14 }}>{item.icon}</div>
                  <div style={{ fontSize: 32, fontWeight: 700, color: g > 0.3 ? C.main : C.textPrimary, lineHeight: 1.3, marginBottom: 10 }}>{item.title}</div>
                  <div style={{ fontSize: 22, color: C.textSub }}>{item.desc}</div>
                </div>
              );
            })}
          </div>

          <div style={{ opacity: sub1Op, transform: `translateY(${sub1Y}px)`, fontSize: 30, color: C.textSub, fontWeight: 500, textAlign: 'center' }}>
            🔔 구독하시면 <span style={{ color: C.main }}>절대 놓치지 않습니다</span>
          </div>
        </div>
      </AbsoluteFill>

      {/* ═══ PHASE 2 — 채널 클로징 ═══ */}
      <AbsoluteFill style={{ opacity: showPh2, pointerEvents: 'none' }}>
        {PARTICLES.map(({ x, delay, size }) => {
          const prog = Math.max(0, (f - 410 - delay) / 160);
          if (prog <= 0) return null;
          return (
            <div key={x} style={{ position: 'absolute', left: `${x}%`, bottom: `${20 + prog * 60}%`, width: size, height: size, borderRadius: '50%', background: C.main, opacity: Math.max(0, 1 - prog * 1.2), boxShadow: `0 0 ${size * 2}px ${C.main}` }} />
          );
        })}

        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: '18%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
          <div style={{ fontSize: 100, opacity: chIconOp, transform: `scale(${chIconSc * iconPulse})`, filter: GLOW.strong.filter }}>📺</div>
          <div style={{ fontSize: 72, fontWeight: 900, color: C.textPrimary, opacity: chNameOp, transform: `translateY(${chNameY}px)`, letterSpacing: chNameLs }}>
            로또의 주식인사이트
          </div>
          <div style={{ fontSize: 36, color: C.textSub, fontWeight: 500, opacity: sloganOp, transform: `translateY(${sloganY}px)` }}>
            AI가 만든 분석 — 매일 업데이트
          </div>

          <div style={{ opacity: btnOp, transform: `scale(${btnScale})` }}>
            <div style={{ background: C.dataUp, borderRadius: 50, padding: '20px 64px', display: 'flex', alignItems: 'center', gap: 18, boxShadow: btnGlow }}>
              <span style={{ fontSize: 40 }}>🔔</span>
              <span style={{ fontSize: 38, fontWeight: 900, color: '#fff' }}>구독</span>
            </div>
          </div>
        </div>
      </AbsoluteFill>

      {/* 자막 바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[
          { o: cap1, text: <>AI 직원들 자료 — <span style={{ color: C.main }}>다음 영상에서도 계속 보여드립니다</span></> },
          { o: cap2, text: <>구독 누르시면 <span style={{ color: C.main }}>절대 놓치지 않습니다</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{ position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center', paddingInline: 80, opacity: o, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
