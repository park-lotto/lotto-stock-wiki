// GB04 — 씬4 "저 이런 거 어떻게 알았냐고요?" (50초 = 1500프레임)
// Phase1 (f0~420):   🤔 질문 임팩트 "어떻게 알았냐고요?" + "5/28 그날 이미"
// Phase2 (f420~1080): 📨 4개 브리핑 카드 텔레그램식 입장
// Phase3 (f1080~1500): 💥 "전부 자동으로요." 클라이맥스
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO     = 'audio/국씬4.m4a';
const HAS_AUDIO = false;

const fi = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const fo = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const lr = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

const MSGS = [
  { icon: '📊', tag: '리포트', title: '증권사 리포트 수십 개', body: '자동 요약 → 핵심 종목·섹터 변경사항 추출' },
  { icon: '🔑', tag: '키워드', title: '뉴스 키워드 정리',     body: '오늘 상위 키워드 → 증시 핫이슈 흐름 파악' },
  { icon: '📺', tag: '유튜브', title: '주요 채널 자동 요약', body: '핵심 채널 12곳 → 최다 언급 종목 추출' },
  { icon: '📈', tag: '시장심리', title: '증시 센티 트렌드',  body: '핫 키워드 방향성 → 섹터별 분위기 정리' },
];

export const GB04_Telegram = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const bgGlow = Math.sin(f * 0.04) * 0.03 + 0.04;

  const showPh1 = f < 370 ? fi(0, 18)(f) : fo(370, 420)(f);
  const showPh2 = f < 420 ? 0 : f < 1040 ? fi(420, 460)(f) : fo(1040, 1080)(f);
  const showPh3 = f < 1080 ? 0 : fi(1080, 1120)(f);

  // ─── Phase1 ───
  const scan1Y  = lr(-2, 104, 0, 36)(f);
  const scan1Op = f < 36 ? interpolate(f, [0, 4, 30, 36], [0, 1, 1, 0]) : 0;

  const p1Icon  = fi(12, 48)(f);
  const p1IconY = lr(30, 0, 12, 48)(f);
  const p1L1Op  = fi(50, 85)(f);
  const p1L1X   = lr(-200, 0, 50, 85)(f);
  const p1L2Op  = fi(85, 122)(f);
  const p1L2X   = lr(200, 0, 85, 122)(f);
  const p1Pulse = Math.sin(f * 0.07) * 0.5 + 0.5;
  const p1GSz   = interpolate(p1Pulse, [0, 1], [10, 36]);
  const p1Glow  = `0 0 ${p1GSz}px #00FFD0, 0 0 ${p1GSz*2}px rgba(0,255,208,0.55), 0 0 ${p1GSz*4}px rgba(0,191,154,0.3)`;
  const p1Breathe = p1L2Op > 0.9 ? Math.sin(f * 0.08) * 0.018 + 1 : 1;
  const burstOp    = interpolate(f, [125, 132, 162], [0, 0.5, 0], { extrapolateRight: 'clamp' });
  const burstScale = lr(0.2, 2.8, 125, 162)(f);
  const p1SubOp = fi(200, 250)(f);
  const p1SubY  = lr(20, 0, 200, 250)(f);

  // ─── Phase2 ───
  const scan2Y  = lr(-2, 104, 420, 458)(f);
  const scan2Op = f >= 420 && f < 458 ? interpolate(f, [420, 424, 452, 458], [0, 1, 1, 0]) : 0;

  const msgAnims = MSGS.map((_, i) => {
    const s = 470 + i * 100;
    return {
      op:    fi(s, s + 40)(f),
      tx:    lr(320, 0, s, s + 40)(f),
      scale: lr(0.92, 1, s, s + 40)(f),
      scanY: lr(0, 110, s + 10, s + 30)(f),
      scanO: f >= s + 10 && f < s + 30 ? interpolate(f, [s+10, s+14, s+26, s+30], [0, 0.9, 0.9, 0]) : 0,
    };
  });

  const allMsgs = f >= 870;
  const ringPh  = allMsgs ? ((f - 870) % 60) / 60 : 0;
  const msgGlow = (i: number) => {
    if (!allMsgs) return 0;
    const center = i / 4 + 0.125;
    const dist = Math.min(Math.abs(ringPh - center), 1 - Math.abs(ringPh - center));
    return Math.max(0, 1 - dist * 4 * 1.8);
  };

  // ─── Phase3 ───
  const p3scan1Y  = lr(-2, 104, 1080, 1118)(f);
  const p3scan1Op = f >= 1080 && f < 1118 ? interpolate(f, [1080, 1084, 1112, 1118], [0, 1, 1, 0]) : 0;
  const p3scan2X  = lr(-2, 104, 1080, 1118)(f);

  const p3Icon  = fi(1122, 1155)(f);
  const p3Pre   = fi(1160, 1200)(f);
  const p3PreY  = lr(20, 0, 1160, 1200)(f);
  const p3L1Op  = fi(1208, 1248)(f);
  const p3L1Y   = lr(-70, 0, 1208, 1248)(f);
  const p3L1Ls  = lr(18, 0, 1208, 1248)(f);
  const p3L2Op  = fi(1268, 1308)(f);
  const p3L2Y   = lr(70, 0, 1268, 1308)(f);
  const p3Breathe = p3L2Op > 0.9 ? Math.sin(f * 0.08) * 0.022 + 1 : 1;
  const p3Pulse = Math.sin(f * 0.08) * 0.5 + 0.5;
  const p3GSz   = interpolate(p3Pulse, [0, 1], [14, 42]);
  const p3Glow  = `0 0 ${p3GSz}px #00FFD0, 0 0 ${p3GSz*2}px rgba(0,255,208,0.6), 0 0 ${p3GSz*4}px rgba(0,191,154,0.35)`;
  const burstOp3    = interpolate(f, [1320, 1328, 1358], [0, 0.6, 0], { extrapolateRight: 'clamp' });
  const burstScale3 = lr(0.2, 3.0, 1320, 1358)(f);

  // 자막
  const cap1 = showPh1 > 0.5 ? fi(220, 260)(f) : 0;
  const cap2 = showPh2 > 0.1 ? fi(870, 910)(f) : 0;
  const cap3 = showPh3 > 0.1 ? fi(1370, 1410)(f) : 0;

  return (
    <AbsoluteFill style={{ background: C.bg, opacity: fadeIn, fontFamily: FONT, overflow: 'hidden' }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: `radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)`, opacity: bgGlow }} />

      {/* 스캔라인들 */}
      {f < 36 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${scan1Y}%`, height: 2, background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)', boxShadow: '0 0 10px rgba(0,255,208,0.9)', opacity: scan1Op, zIndex: 10 }} />}
      {f >= 420 && f < 458 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${scan2Y}%`, height: 2, background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)', boxShadow: '0 0 10px rgba(0,255,208,0.9)', opacity: scan2Op, zIndex: 10 }} />}
      {f >= 1080 && f < 1118 && <>
        <div style={{ position: 'absolute', left: 0, right: 0, top: `${p3scan1Y}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: p3scan1Op, zIndex: 10 }} />
        <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${p3scan2X}%`, width: 2, background: 'linear-gradient(180deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: p3scan1Op, zIndex: 10 }} />
      </>}

      {/* 버스트 */}
      {[{ op: burstOp, sc: burstScale }, { op: burstOp3, sc: burstScale3 }].map(({ op, sc }, i) => (
        <div key={i} style={{ position: 'absolute', top: '44%', left: '50%', width: 560, height: 560, marginLeft: -280, marginTop: -280, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,255,208,0.28) 0%, transparent 70%)', opacity: op, transform: `scale(${sc})`, pointerEvents: 'none' }} />
      ))}

      {/* ═══ PHASE 1 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: showPh1, gap: 8 }}>
        <div style={{ fontSize: 110, lineHeight: 1, opacity: p1Icon, transform: `translateY(${p1IconY}px)`, filter: GLOW.mid.filter }}>🤔</div>
        <div style={{ fontSize: 36, color: C.textSub, fontWeight: 500, letterSpacing: 4, marginBottom: 8, opacity: p1L1Op }}>저 이런 거</div>
        <div style={{ fontSize: 120, fontWeight: 900, color: C.textPrimary, lineHeight: 1, opacity: p1L1Op, transform: `translateX(${p1L1X}px)` }}>어떻게 알았냐고요?</div>
        <div style={{ fontSize: 120, fontWeight: 900, color: C.main, lineHeight: 1, marginTop: 6, opacity: p1L2Op, transform: `translateX(${p1L2X}px) scale(${p1Breathe})`, textShadow: p1L2Op > 0.5 ? p1Glow : 'none' }}>전부 자동으로요.</div>
        <div style={{ opacity: p1SubOp, transform: `translateY(${p1SubY}px)`, marginTop: 20, fontSize: 30, color: C.textSub }}>
          5월 28일 발표 그날 — 이미 모든 브리핑이 도착해 있었거든요
        </div>
      </div>

      {/* ═══ PHASE 2 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: showPh2, paddingInline: 100, gap: 18 }}>
        <div style={{ fontSize: 40, color: C.textSub, fontWeight: 600, alignSelf: 'flex-start', opacity: fi(460, 500)(f) }}>매일 아침 자동으로 도착합니다</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
          {MSGS.map((m, i) => {
            const g = msgGlow(i);
            return (
              <div key={i} style={{
                opacity: msgAnims[i].op, transform: `translateX(${msgAnims[i].tx}px) scale(${msgAnims[i].scale})`,
                background: g > 0.3 ? 'rgba(0,255,208,0.08)' : 'rgba(255,255,255,0.04)',
                border: `1.5px solid ${g > 0.3 ? C.main : C.borderSub}`,
                borderRadius: 16, padding: '20px 28px',
                display: 'flex', alignItems: 'center', gap: 20,
                position: 'relative', overflow: 'hidden',
                boxShadow: g > 0.2 ? `0 0 ${16*g}px rgba(0,255,208,${0.5*g})` : 'none',
              }}>
                <div style={{ position: 'absolute', left: 0, right: 0, top: `${msgAnims[i].scanY}%`, height: 1, background: 'linear-gradient(90deg, transparent, rgba(0,255,208,0.6), transparent)', opacity: msgAnims[i].scanO }} />
                <div style={{ fontSize: 52 }}>{m.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
                    <div style={{ background: C.main, color: '#000', fontSize: 14, fontWeight: 900, padding: '3px 10px', borderRadius: 6 }}>{m.tag}</div>
                    <div style={{ fontSize: 26, fontWeight: 700, color: g > 0.3 ? C.main : C.textPrimary }}>{m.title}</div>
                  </div>
                  <div style={{ fontSize: 20, color: C.textSub }}>{m.body}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ═══ PHASE 3 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: showPh3, gap: 8 }}>
        <div style={{ fontSize: 110, lineHeight: 1, opacity: p3Icon, filter: GLOW.strong.filter }}>⚡</div>
        <div style={{ opacity: p3Pre, transform: `translateY(${p3PreY}px)`, fontSize: 36, color: C.textSub, letterSpacing: 3 }}>리포트·뉴스·유튜브·심리까지</div>
        <div style={{ fontSize: 140, fontWeight: 900, color: C.textPrimary, lineHeight: 1, opacity: p3L1Op, transform: `translateY(${p3L1Y}px)`, letterSpacing: p3L1Ls }}>전부</div>
        <div style={{ fontSize: 160, fontWeight: 900, color: C.main, lineHeight: 1, opacity: p3L2Op, transform: `translateY(${p3L2Y}px) scale(${p3Breathe})`, textShadow: p3L2Op > 0.5 ? p3Glow : 'none' }}>자동으로요.</div>
      </div>

      {/* 자막 바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[
          { o: cap1, text: <>5/28 그날 — <span style={{ color: C.main }}>이미 브리핑이 도착해 있었거든요</span></> },
          { o: cap2, text: <>매일 아침 <span style={{ color: C.main }}>자동으로 정리돼 있습니다</span></> },
          { o: cap3, text: <>리포트·뉴스·유튜브·심리까지 — <span style={{ color: C.main }}>전부 자동으로요.</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{ position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center', paddingInline: 80, opacity: o, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
