// GB05 — 씬5 "AI 에이전트 직원들" (46초 = 1380프레임)
// Phase1 (f0~540):  🤖 AI 직원 4명 orbit 등장 + "매일 시키는 일이 있어요"
// Phase2 (f540~1050): 📋 "아침에 이미 정리" + 실제 내용 목업
// Phase3 (f1050~1380): 💬 "따로 영상으로" + 댓글 CTA
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO     = 'audio/국씬5.m4a';
const HAS_AUDIO = false;

const fi = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const fo = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const lr = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

const WORKERS = [
  { icon: '📡', name: '수집 직원', desc: '24시간 수집' },
  { icon: '🧠', name: '분석 직원', desc: '핵심만 추출' },
  { icon: '📋', name: '정리 직원', desc: '섹터·종목 정리' },
  { icon: '📨', name: '알림 직원', desc: '아침 자동 전송' },
];

const ITEMS = [
  { icon: '📊', text: '국민성장펀드 발표 당일 분위기', tag: 'Today' },
  { icon: '📈', text: '움직인 종목', tag: 'Stocks' },
  { icon: '💬', text: '변화하는 시장 센티', tag: 'Senti' },
  { icon: '🎬', text: '오늘 영상 아이디어까지', tag: 'Content' },
];

export const GB05_StockBrain = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  const showPh1 = f < 490 ? fi(0, 20)(f) : fo(490, 540)(f);
  const showPh2 = f < 540 ? 0 : f < 1000 ? fi(540, 580)(f) : fo(1000, 1050)(f);
  const showPh3 = f < 1050 ? 0 : fi(1050, 1090)(f);

  // ─── Phase1 스캔라인 ───
  const scanX  = lr(-2, 104, 0, 36)(f);
  const scanOp = f < 36 ? interpolate(f, [0, 4, 30, 36], [0, 1, 1, 0]) : 0;

  // ─── Phase1 ───
  const p1TitleOp = fi(20, 55)(f);
  const p1TitleY  = lr(40, 0, 20, 55)(f);
  const p1SubOp   = fi(70, 110)(f);

  // 직원 4명 stagger elastic
  const workers = WORKERS.map((_, i) => {
    const s = 120 + i * 70;
    return {
      op:    fi(s, s + 35)(f),
      scale: interpolate(f, [s, s + 50], [0.3, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) }),
      y:     lr(40, 0, s, s + 35)(f),
    };
  });

  // 순환 글로우
  const allW = f >= 400;
  const wRing = allW ? ((f - 400) % 72) / 72 : 0;
  const wGlow = (i: number) => {
    if (!allW) return 0;
    const center = i / 4 + 0.125;
    const dist = Math.min(Math.abs(wRing - center), 1 - Math.abs(wRing - center));
    return Math.max(0, 1 - dist * 4 * 1.8);
  };

  // ─── Phase2 ───
  const scan2Y  = lr(-2, 104, 540, 578)(f);
  const scan2Op = f >= 540 && f < 578 ? interpolate(f, [540, 544, 572, 578], [0, 1, 1, 0]) : 0;

  const p2TitleOp = fi(585, 625)(f);
  const p2TitleY  = lr(30, 0, 585, 625)(f);
  const itemAnims = ITEMS.map((_, i) => {
    const s = 640 + i * 80;
    return {
      op:    fi(s, s + 40)(f),
      tx:    lr(260, 0, s, s + 40)(f),
      scale: lr(0.92, 1, s, s + 40)(f),
    };
  });
  const allItems = f >= 960;
  const iRing = allItems ? ((f - 960) % 60) / 60 : 0;
  const iGlow = (i: number) => {
    if (!allItems) return 0;
    const center = i / 4 + 0.125;
    const dist = Math.min(Math.abs(iRing - center), 1 - Math.abs(iRing - center));
    return Math.max(0, 1 - dist * 4 * 1.8);
  };

  // ─── Phase3 ───
  const p3scan1Y  = lr(-2, 104, 1050, 1088)(f);
  const p3scan1Op = f >= 1050 && f < 1088 ? interpolate(f, [1050, 1054, 1082, 1088], [0, 1, 1, 0]) : 0;
  const p3Icon    = fi(1092, 1125)(f);
  const p3L1Op    = fi(1130, 1168)(f);
  const p3L1Y     = lr(-60, 0, 1130, 1168)(f);
  const p3L2Op    = fi(1175, 1215)(f);
  const p3L2Y     = lr(60, 0, 1175, 1215)(f);
  const p3Breathe = p3L2Op > 0.9 ? Math.sin(f * 0.08) * 0.02 + 1 : 1;
  const p3Pulse   = Math.sin(f * 0.08) * 0.5 + 0.5;
  const p3GSz     = interpolate(p3Pulse, [0, 1], [14, 40]);
  const p3Glow    = `0 0 ${p3GSz}px #00FFD0, 0 0 ${p3GSz*2}px rgba(0,255,208,0.6), 0 0 ${p3GSz*4}px rgba(0,191,154,0.35)`;
  const burstOp   = interpolate(f, [1230, 1238, 1268], [0, 0.55, 0], { extrapolateRight: 'clamp' });
  const burstSc   = lr(0.2, 2.8, 1230, 1268)(f);
  const btnOp     = fi(1275, 1335)(f);
  const btnSc     = interpolate(f, [1275, 1335], [0.4, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1)) });
  const btnPulse  = Math.sin(f * 0.1) * 0.5 + 0.5;
  const btnGlow   = `0 0 ${interpolate(btnPulse, [0, 1], [16, 32]) * Math.min(1, (f-1275)/40)}px rgba(0,255,208,0.6)`;

  // 자막
  const cap1 = showPh1 > 0.5 ? fi(400, 440)(f) : 0;
  const cap2 = showPh2 > 0.1 ? fi(920, 960)(f) : 0;
  const cap3 = showPh3 > 0.1 ? fi(1290, 1330)(f) : 0;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: `radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)`, opacity: bgGlow }} />

      {f < 36 && <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${scanX}%`, width: 2, background: 'linear-gradient(180deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', boxShadow: '0 0 10px rgba(0,255,208,0.9)', opacity: scanOp, zIndex: 10 }} />}
      {f >= 540 && f < 578 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${scan2Y}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: scan2Op, zIndex: 10 }} />}
      {f >= 1050 && f < 1088 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${p3scan1Y}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: p3scan1Op, zIndex: 10 }} />}

      <div style={{ position: 'absolute', top: '44%', left: '50%', width: 560, height: 560, marginLeft: -280, marginTop: -280, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)', opacity: burstOp, transform: `scale(${burstSc})`, pointerEvents: 'none' }} />

      {/* ═══ PHASE 1 — AI 직원들 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: showPh1, paddingInline: 120, gap: 0 }}>
        <div style={{ opacity: p1TitleOp, transform: `translateY(${p1TitleY}px)`, textAlign: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 32, color: C.textSub, letterSpacing: 4, marginBottom: 8 }}>제가 매일 시키는 일</div>
          <div style={{ fontSize: 100, fontWeight: 900, color: C.textPrimary, lineHeight: 1.1 }}>
            AI 에이전트&nbsp;<span style={{ color: C.main, textShadow: GLOW.mid.text }}>직원들</span>
          </div>
        </div>
        <div style={{ opacity: p1SubOp, fontSize: 30, color: C.textSub, marginBottom: 28 }}>24시간 일하는 직원들입니다</div>

        {/* 직원 4명 그리드 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20, width: '100%' }}>
          {WORKERS.map((w, i) => {
            const g = wGlow(i);
            return (
              <div key={i} style={{
                opacity: workers[i].op, transform: `translateY(${workers[i].y}px) scale(${workers[i].scale})`,
                background: g > 0.3 ? 'rgba(0,255,208,0.08)' : 'rgba(255,255,255,0.04)',
                border: `1.5px solid ${g > 0.3 ? C.main : C.borderSub}`,
                borderRadius: 20, padding: '24px 16px', textAlign: 'center',
                boxShadow: g > 0.2 ? `0 0 ${16*g}px rgba(0,255,208,${0.5*g})` : 'none',
              }}>
                <div style={{ fontSize: 72, lineHeight: 1, marginBottom: 10 }}>{w.icon}</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: g > 0.3 ? C.main : C.textPrimary, marginBottom: 4 }}>{w.name}</div>
                <div style={{ fontSize: 16, color: C.textSub }}>{w.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ═══ PHASE 2 — 아침에 이미 정리 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: showPh2, paddingInline: 100, gap: 20 }}>
        <div style={{ opacity: p2TitleOp, transform: `translateY(${p2TitleY}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 32, color: C.textSub, marginBottom: 8 }}>아침에 일어나면</div>
          <div style={{ fontSize: 88, fontWeight: 900, color: C.textPrimary, lineHeight: 1 }}>이미 <span style={{ color: C.main, textShadow: GLOW.mid.text }}>모든 게 정리</span>돼 있습니다</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, width: '100%' }}>
          {ITEMS.map((item, i) => {
            const g = iGlow(i);
            return (
              <div key={i} style={{
                opacity: itemAnims[i].op, transform: `translateX(${itemAnims[i].tx}px) scale(${itemAnims[i].scale})`,
                background: g > 0.3 ? 'rgba(0,255,208,0.07)' : 'rgba(255,255,255,0.04)',
                border: `1.5px solid ${g > 0.3 ? C.main : C.borderSub}`,
                borderRadius: 16, padding: '18px 28px',
                display: 'flex', alignItems: 'center', gap: 18,
                boxShadow: g > 0.2 ? `0 0 ${14*g}px rgba(0,255,208,${0.45*g})` : 'none',
              }}>
                <div style={{ fontSize: 44 }}>{item.icon}</div>
                <div style={{ fontSize: 28, fontWeight: 600, color: g > 0.3 ? C.main : C.textPrimary }}>{item.text}</div>
                <div style={{ marginLeft: 'auto', background: C.main, color: '#000', fontSize: 14, fontWeight: 900, padding: '4px 12px', borderRadius: 8 }}>{item.tag}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ═══ PHASE 3 — 댓글로 남겨주세요 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: showPh3, gap: 12 }}>
        <div style={{ fontSize: 110, lineHeight: 1, opacity: p3Icon, filter: GLOW.mid.filter }}>🎬</div>
        <div style={{ fontSize: 48, color: C.textSub, fontWeight: 600, opacity: p3L1Op, transform: `translateY(${p3L1Y}px)` }}>어떻게 만들어지는지</div>
        <div style={{ fontSize: 120, fontWeight: 900, color: C.textPrimary, lineHeight: 1.1, opacity: p3L1Op, transform: `translateY(${p3L1Y}px)`, textAlign: 'center' }}>따로 영상으로<br /><span style={{ color: C.main, textShadow: GLOW.mid.text }}>올려드릴게요</span></div>
        <div style={{ opacity: p3L2Op, transform: `translateY(${p3L2Y}px) scale(${p3Breathe})`, textShadow: p3L2Op > 0.5 ? p3Glow : 'none', fontSize: 44, color: C.main, fontWeight: 700 }}>궁금하신 분들은 댓글로 남겨주세요</div>

        <div style={{ opacity: btnOp, transform: `scale(${btnSc})`, marginTop: 12 }}>
          <div style={{
            background: C.main, borderRadius: 50, padding: '16px 52px',
            display: 'flex', alignItems: 'center', gap: 16,
            boxShadow: btnGlow, cursor: 'pointer',
          }}>
            <span style={{ fontSize: 36 }}>💬</span>
            <span style={{ fontSize: 34, fontWeight: 900, color: '#000' }}>댓글로 남겨주세요</span>
          </div>
        </div>
      </div>

      {/* 자막 바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[
          { o: cap1, text: <>AI 에이전트 직원들 — <span style={{ color: C.main }}>24시간 일합니다</span></> },
          { o: cap2, text: <>아침에 일어나면 <span style={{ color: C.main }}>이미 모든 게 정리돼 있습니다</span></> },
          { o: cap3, text: <>따로 영상으로 올려드릴게요 — <span style={{ color: C.main }}>댓글로 남겨주세요</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{ position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center', paddingInline: 80, opacity: o, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
