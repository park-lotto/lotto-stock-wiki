// GB02 — 씬2 Whisper 싱크 (34.90s + 30f = 1077프레임)
// Whisper: f0~159 펀드소개/f159~506 섹터12개/f506~598 30조/f598~849 혜택/f849~904 조건/f904~1047 ETF
// Phase1 f0~480 / Phase2 f490~660 / Phase3 f660~1077
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO     = 'audio/국씬2.m4a';
const HAS_AUDIO = true;

const fi = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const fo = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const lr = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

const SECTORS = [
  { icon: '🤖', name: 'AI' },
  { icon: '💻', name: '반도체' },
  { icon: '🧬', name: '바이오' },
  { icon: '🔋', name: '이차전지' },
  { icon: '🦾', name: '로봇' },
  { icon: '🛡️', name: '방산' },
  { icon: '🚗', name: '미래차' },
  { icon: '⚡', name: '수소' },
  { icon: '📱', name: '디스플레이' },
  { icon: '💉', name: '백신' },
  { icon: '🎬', name: '콘텐츠' },
  { icon: '⛏️', name: '핵심광물' },
];

export const GB02_Checklist = () => {
  const f = useCurrentFrame();
  const bgGlow = Math.sin(f * 0.03) * 0.03 + 0.04;

  // ─── Phase 전환 (Whisper 기준) ───
  const ph1 = f < 440 ? fi(0, 20)(f) : fo(440, 490)(f);
  const ph2 = f < 490 ? 0 : f < 620 ? fi(490, 525)(f) : fo(620, 660)(f);
  const ph3 = f < 660 ? 0 : fi(660, 695)(f);

  // ─── 스캔라인 ───
  const scanX  = lr(-2, 104, 0, 36)(f);
  const scanOp = f < 36 ? interpolate(f, [0, 4, 30, 36], [0, 1, 1, 0]) : 0;

  // ─── Phase1 — 섹터 stagger (Whisper f159 "AI, 반도체") ───
  const p1TitleOp = fi(15, 50)(f);
  const p1TitleY  = lr(30, 0, 15, 50)(f);
  // 섹터 카드: f155 시작, 18프레임 간격 (완료 ~f375)
  const sectorCards = SECTORS.map((_, i) => {
    const start = 155 + i * 18;
    return {
      op:    fi(start, start + 18)(f),
      scale: lr(0.5, 1, start, start + 18)(f),
      y:     lr(24, 0, start, start + 22)(f),
    };
  });
  // 순환 글로우 (f400 이후, 48프레임 주기)
  const sectorGlow = (i: number) => {
    if (f < 400) return 0;
    const phase = ((f - 400) % 48) / 48;
    const center = i / 12;
    const dist = Math.min(Math.abs(phase - center), 1 - Math.abs(phase - center));
    return Math.max(0, 1 - dist * 12 * 1.8);
  };

  // ─── Phase2 — 수치 (Whisper f506 "30조") ───
  const p2TitleOp = fi(500, 535)(f);
  const p2Num1Op  = fi(540, 580)(f);
  const p2Num1Y   = lr(30, 0, 540, 585)(f);
  const p2Num2Op  = fi(575, 618)(f);
  const p2Num2Y   = lr(30, 0, 575, 618)(f);
  const p2SubOp   = fi(610, 648)(f);
  const p2CountPulse = Math.sin(f * 0.08) * 0.5 + 0.5;

  // ─── Phase3 — 혜택 + 반전 (Whisper f598 "소득공제", f849 "조건") ───
  const p3TitleOp = fi(670, 705)(f);
  const p3C1Op    = fi(705, 745)(f);
  const p3C1X     = lr(-80, 0, 705, 745)(f);
  const p3C2Op    = fi(745, 785)(f);
  const p3C2X     = lr(80, 0, 745, 785)(f);
  const p3WarnOp  = fi(850, 890)(f);   // Whisper f849 "조건이 있습니다"
  const p3WarnY   = lr(24, 0, 850, 890)(f);
  const p3VerdOp  = fi(905, 945)(f);   // Whisper f904 "ETF가 더"
  const p3VerdY   = lr(20, 0, 905, 945)(f);
  const cardGlow  = (i: number) => {
    if (f < 760) return 0;
    const ph = ((f - 760) % 60) / 60;
    const center = i / 2 + 0.25;
    const dist = Math.min(Math.abs(ph - center), 1 - Math.abs(ph - center));
    return Math.max(0, 1 - dist * 2 * 1.8);
  };

  // ─── 자막 (Whisper 타이밍) ───
  const cap1 = ph1 > 0.5 ? fi(355, 395)(f) : 0;   // f350 "순환 글로우"
  const cap2 = ph2 > 0.1 ? fi(555, 595)(f) : 0;   // f506 "30조 집행"
  const cap3 = ph3 > 0.1 ? fi(920, 960)(f) : 0;    // Whisper f904 "조건 안 맞으면 ETF"

  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, overflow: 'hidden' }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}

      {/* 배경 */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)`,
        opacity: bgGlow }} />

      {/* 수직 스캔라인 */}
      {f < 36 && <div style={{
        position: 'absolute', top: 0, bottom: 0, left: `${scanX}%`, width: 2,
        background: 'linear-gradient(180deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)', opacity: scanOp, zIndex: 10,
      }} />}

      {/* ═══ PHASE 1 — 12개 섹터 이모지 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph1, padding: '0 100px' }}>
        <div style={{ opacity: p1TitleOp, transform: `translateY(${p1TitleY}px)`, marginBottom: 32 }}>
          <div style={{ fontSize: 36, color: C.textSub, fontWeight: 500, textAlign: 'center', letterSpacing: 3 }}>
            이 펀드가 투자하는 곳
          </div>
          <div style={{ fontSize: 88, fontWeight: 900, color: C.textPrimary, textAlign: 'center', lineHeight: 1.1, marginTop: 4 }}>
            <span style={{ color: C.main, textShadow: GLOW.mid.text }}>12개</span> 첨단전략산업
          </div>
        </div>

        {/* 섹터 4×3 그리드 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 16, width: '100%' }}>
          {SECTORS.map((s, i) => {
            const g = sectorGlow(i);
            return (
              <div key={i} style={{
                opacity: sectorCards[i].op,
                transform: `translateY(${sectorCards[i].y}px) scale(${sectorCards[i].scale})`,
                background: g > 0.3 ? 'rgba(0,255,208,0.1)' : 'rgba(255,255,255,0.04)',
                border: `1.5px solid ${g > 0.3 ? C.main : C.borderSub}`,
                borderRadius: 16, padding: '16px 8px',
                textAlign: 'center',
                boxShadow: g > 0.2 ? `0 0 ${14 * g}px rgba(0,255,208,${0.5 * g})` : 'none',
              }}>
                <div style={{ fontSize: 44, lineHeight: 1 }}>{s.icon}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: g > 0.3 ? C.main : C.textPrimary, marginTop: 8 }}>{s.name}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ═══ PHASE 2 — 150조 / 30조 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph2, gap: 0 }}>
        <div style={{ opacity: p2TitleOp, fontSize: 38, color: C.textSub, fontWeight: 600, marginBottom: 32, textAlign: 'center' }}>
          정부가 쏟아붓는 규모
        </div>

        {/* 150조 */}
        <div style={{ opacity: p2Num1Op, transform: `translateY(${p2Num1Y}px)`, textAlign: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 28, color: C.textSub, letterSpacing: 4, marginBottom: 8 }}>5년간 총</div>
          <div style={{ fontSize: 180, fontWeight: 900, color: C.main, lineHeight: 0.9, textShadow: `0 0 ${interpolate(p2CountPulse, [0, 1], [20, 60])}px rgba(0,255,208,0.6)` }}>
            150조
          </div>
        </div>

        {/* 30조 */}
        <div style={{ opacity: p2Num2Op, transform: `translateY(${p2Num2Y}px)`, textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24, justifyContent: 'center' }}>
            <div style={{ fontSize: 28, color: C.textSub }}>올해만</div>
            <div style={{ fontSize: 120, fontWeight: 900, color: C.textPrimary }}>30조</div>
            <div style={{ fontSize: 28, color: C.textSub }}>집행</div>
          </div>
        </div>

        <div style={{ opacity: p2SubOp, marginTop: 28, fontSize: 34, color: C.main, fontWeight: 700, textShadow: GLOW.weak.text }}>
          🚀 지금 집행 시작 중입니다
        </div>
      </div>

      {/* ═══ PHASE 3 — 혜택 + 반전 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph3, padding: '0 120px', gap: 0 }}>
        <div style={{ opacity: p3TitleOp, fontSize: 80, fontWeight: 900, color: C.textPrimary, textAlign: 'center', lineHeight: 1.15, marginBottom: 32 }}>
          들으면 무조건&nbsp;
          <span style={{ color: C.main, textShadow: GLOW.mid.text }}>넣어야 할 것 같죠?</span>
        </div>

        {/* 혜택 카드 2개 */}
        <div style={{ display: 'flex', gap: 24, width: '100%', marginBottom: 20 }}>
          {[
            { o: p3C1Op, tx: p3C1X, icon: '📈', title: '소득공제 40%', desc: '납입액 40% 소득공제\n절세 효과 연 최대 264만원', g: cardGlow(0) },
            { o: p3C2Op, tx: p3C2X, icon: '🛡️', title: '정부 손실 방어', desc: '원금 손실 일부를 정부 보전\n하락장에도 안전망', g: cardGlow(1) },
          ].map(({ o, tx, icon, title, desc, g }) => (
            <div key={title} style={{
              flex: 1, opacity: o, transform: `translateX(${tx}px)`,
              background: g > 0.3 ? 'rgba(0,255,208,0.1)' : C.cardBg,
              border: `1.5px solid ${g > 0.3 ? C.main : C.borderSub}`,
              borderRadius: 20, padding: '28px 36px',
              boxShadow: g > 0.2 ? `0 0 ${16 * g}px rgba(0,255,208,${0.5 * g})` : 'none',
            }}>
              <div style={{ fontSize: 72, marginBottom: 14 }}>{icon}</div>
              <div style={{ fontSize: 40, fontWeight: 700, color: g > 0.3 ? C.main : C.textPrimary, marginBottom: 10 }}>{title}</div>
              <div style={{ fontSize: 26, color: C.textSub, lineHeight: 1.65, whiteSpace: 'pre-line' }}>{desc}</div>
            </div>
          ))}
        </div>

        {/* 반전 박스 */}
        <div style={{
          opacity: p3WarnOp, transform: `translateY(${p3WarnY}px)`,
          width: '100%', background: 'rgba(255,184,0,0.06)',
          border: '1.5px solid rgba(255,184,0,0.5)', borderRadius: 16, padding: '20px 36px',
          display: 'flex', alignItems: 'center', gap: 20,
        }}>
          <div style={{ fontSize: 52 }}>⚠️</div>
          <div style={{ fontSize: 36, fontWeight: 700, color: '#FFB800' }}>
            조건이 있습니다 — 이 조건 안 맞으면 <span style={{ color: C.textPrimary }}>ETF가 더 법니다</span>
          </div>
        </div>

        {/* 판결 */}
        <div style={{
          opacity: p3VerdOp, transform: `translateY(${p3VerdY}px)`,
          display: 'flex', gap: 0, width: '100%', marginTop: 16,
          background: 'rgba(0,255,208,0.04)', border: `1px solid ${C.borderSub}`,
          borderRadius: 14, overflow: 'hidden',
        }}>
          <div style={{ flex: 1, padding: '18px 32px', textAlign: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 22, marginBottom: 6 }}>조건 해당되면</div>
            <div style={{ color: C.main, fontSize: 36, fontWeight: 900, textShadow: GLOW.weak.text }}>✅ 펀드 GO</div>
          </div>
          <div style={{ width: 1, background: 'rgba(255,255,255,0.12)' }} />
          <div style={{ flex: 1, padding: '18px 32px', textAlign: 'center' }}>
            <div style={{ color: C.textSub, fontSize: 22, marginBottom: 6 }}>조건 안 맞으면</div>
            <div style={{ color: '#FFB800', fontSize: 36, fontWeight: 900 }}>⚡ ETF가 낫다</div>
          </div>
        </div>
      </div>

      {/* ═══ 하단 자막 바 ═══ */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[
          { o: cap1, text: <><span style={{ color: C.main }}>12개 첨단전략산업</span> — AI·반도체·바이오·이차전지·로봇·방산</> },
          { o: cap2, text: <>5년간 <span style={{ color: C.main }}>150조</span> — 올해만 30조 집행 시작</> },
          { o: cap3, text: <>조건이 있습니다 — <span style={{ color: '#FFB800' }}>안 맞으면 ETF가 더 법니다</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{
            position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700,
            textAlign: 'center', paddingInline: 80, opacity: o,
            textShadow: '0 2px 8px rgba(0,0,0,0.9)',
          }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
