// GB01 — 씬1 훅 Whisper 싱크 (25.88s + 30f 여백 = 806프레임)
// Whisper: f0~167 완판/f167~341 10분/f341~510 이틀/f510~595 못들어가셨죠/f595~661 진짜기회/f661~776 5분만
// Phase1 f0~480 / Phase2 f510~620 / Phase3 f630~806
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO     = 'audio/국씬1.m4a';
const HAS_AUDIO = true;

const fi = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const fo = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const lr = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

export const GB01_Hook = () => {
  const f = useCurrentFrame();
  const bgGlow = Math.sin(f * 0.035) * 0.03 + 0.045;

  // ─── Phase 전환 (Whisper 기준) ───
  // f510 "실망하실 거 없어요" → Phase2 / f630 "진짜 기회" → Phase3
  const ph1 = f < 468 ? fi(0, 18)(f) : fo(468, 510)(f);
  const ph2 = f < 510 ? 0 : f < 598 ? fi(510, 535)(f) : fo(598, 628)(f);
  const ph3 = f < 628 ? 0 : fi(628, 655)(f);

  // 스캔라인
  const scanY  = lr(-2, 104, 0, 36)(f);
  const scanOp = f < 36 ? interpolate(f, [0, 4, 30, 36], [0, 1, 1, 0]) : 0;

  // ─── Phase1 ───
  const p1Icon   = fi(12, 45)(f);
  const p1TitleOp= fi(30, 65)(f);
  const p1TitleX = lr(-200, 0, 30, 65)(f);
  const p1Sub1Op = fi(100, 140)(f);  // f100: 완판 설명 완료 후
  const p1Sub1Y  = lr(20, 0, 100, 140)(f);

  // 10분 카드: f145~185 (Whisper f167 "10분")
  const p1C1Op   = fi(145, 185)(f);
  const p1C1Y    = lr(30, 0, 145, 185)(f);
  // 이틀 카드: f318~358 (Whisper f341 "이틀")
  const p1C2Op   = fi(318, 358)(f);
  const p1C2Y    = lr(30, 0, 318, 358)(f);

  // 글로우 버스트 (이틀 카드 등장 시)
  const burstOp    = interpolate(f, [352, 360, 392], [0, 0.5, 0], { extrapolateRight: 'clamp' });
  const burstScale = lr(0.2, 2.8, 352, 392)(f);

  const p1Pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const p1GlowSz = interpolate(p1Pulse, [0, 1], [10, 36]);
  const p1DynGlow = `0 0 ${p1GlowSz}px #00FFD0, 0 0 ${p1GlowSz*2}px rgba(0,255,208,0.55), 0 0 ${p1GlowSz*4}px rgba(0,191,154,0.3)`;

  // ─── Phase2 (f510~628) ───
  // f510 "실망하실 거 없어요" / f595 "진짜 기회는"
  const p2Icon  = fi(515, 545)(f);
  const p2IconY = lr(40, 0, 515, 545)(f);
  const p2TextOp= fi(548, 582)(f);
  const p2TextY = lr(30, 0, 548, 582)(f);
  const p2SubOp = fi(570, 608)(f);
  const p2Breathe = Math.sin(f * 0.09) * 0.025 + 1;

  // ─── Phase3 (f628~806) ───
  // f595 "진짜 기회" / f661 "5분만"
  const p3Icon  = fi(632, 660)(f);
  const p3L1Op  = fi(642, 678)(f);
  const p3L1Y   = lr(36, 0, 642, 678)(f);
  const p3L2Op  = fi(678, 715)(f);
  const p3L2Y   = lr(36, 0, 678, 715)(f);
  const p3L2Pulse = Math.sin(f * 0.08) * 0.025 + 1;
  // CTA박스: f665 "5분만" Whisper
  const p3BoxOp = fi(668, 706)(f);
  const p3BoxY  = lr(20, 0, 668, 706)(f);
  const p3DynGlow = `0 0 ${p1GlowSz}px #00FFD0, 0 0 ${p1GlowSz*2}px rgba(0,255,208,0.55)`;

  // ─── 자막 (Whisper 타임스탬프 기준, 요약 텍스트) ───
  const cap1 = ph1 > 0.5 ? fi(155, 190)(f) : 0;   // f167 10분 카드 등장 시
  const cap2 = ph2 > 0.1 ? fi(522, 555)(f) : 0;   // f510 "실망하실 거 없어요"
  const cap3 = ph3 > 0.1 ? fi(655, 688)(f) : 0;   // f661 "5분만"

  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, overflow: 'hidden' }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}

      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)`,
        opacity: bgGlow }} />

      {f < 36 && <div style={{
        position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2,
        background: 'linear-gradient(90deg, transparent 0%, #00FFD0 20%, #80FFE8 50%, #00FFD0 80%, transparent 100%)',
        boxShadow: '0 0 10px rgba(0,255,208,0.9)', opacity: scanOp, zIndex: 10,
      }} />}

      <div style={{
        position: 'absolute', top: '42%', left: '50%',
        width: 600, height: 600, marginLeft: -300, marginTop: -300, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,255,208,0.3) 0%, transparent 70%)',
        opacity: burstOp, transform: `scale(${burstScale})`, pointerEvents: 'none',
      }} />

      {/* ═══ PHASE 1 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph1, gap: 0 }}>
        <div style={{ fontSize: 100, lineHeight: 1, marginBottom: 10, opacity: p1Icon, filter: GLOW.mid.filter }}>💸</div>

        <div style={{ opacity: p1TitleOp, transform: `translateX(${p1TitleX}px)`, textAlign: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 28, color: C.textSub, letterSpacing: 5, marginBottom: 8 }}>국민성장펀드 1차 판매</div>
          <div style={{ fontSize: 120, fontWeight: 900, color: C.main, lineHeight: 1, textShadow: p1TitleOp > 0.5 ? p1DynGlow : 'none' }}>
            완판
          </div>
        </div>

        <div style={{ opacity: p1Sub1Op, transform: `translateY(${p1Sub1Y}px)`, fontSize: 32, color: C.textSub, marginBottom: 28 }}>
          두 가지 완판이 있었습니다 👇
        </div>

        {/* 두 완판 카드 */}
        <div style={{ display: 'flex', gap: 28 }}>
          {/* 10분 완판 */}
          <div style={{
            opacity: p1C1Op, transform: `translateY(${p1C1Y}px)`,
            background: 'rgba(255,255,255,0.04)', border: `1.5px solid ${C.borderSub}`,
            borderRadius: 20, padding: '24px 36px', textAlign: 'center', minWidth: 340,
          }}>
            <div style={{ fontSize: 44 }}>📱</div>
            <div style={{ fontSize: 64, fontWeight: 900, color: C.textPrimary, marginTop: 8 }}>10분</div>
            <div style={{ fontSize: 22, color: C.main, fontWeight: 700, marginTop: 4 }}>모바일 앱 물량</div>
            <div style={{ fontSize: 17, color: C.textSub, marginTop: 8, lineHeight: 1.5 }}>
              일부 증권사 비대면 물량<br />오픈하자마자 폭주 → 10분 완판
            </div>
          </div>

          {/* 이틀 완판 */}
          <div style={{
            opacity: p1C2Op, transform: `translateY(${p1C2Y}px)`,
            background: 'rgba(0,255,208,0.06)', border: `2px solid ${C.main}`,
            borderRadius: 20, padding: '24px 36px', textAlign: 'center', minWidth: 340,
            boxShadow: GLOW.weak.box,
          }}>
            <div style={{ fontSize: 44 }}>🏦</div>
            <div style={{ fontSize: 64, fontWeight: 900, color: C.main, marginTop: 8, textShadow: GLOW.mid.text }}>이틀</div>
            <div style={{ fontSize: 22, color: C.textPrimary, fontWeight: 700, marginTop: 4 }}>전체 1차 물량</div>
            <div style={{ fontSize: 17, color: C.textSub, marginTop: 8, lineHeight: 1.5 }}>
              시중은행 창구 포함 6,000억 기준<br />97.5% 소진 → 사실상 완판
            </div>
          </div>
        </div>
      </div>

      {/* ═══ PHASE 2 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph2 }}>
        <div style={{ fontSize: 120, lineHeight: 1, marginBottom: 24, opacity: p2Icon, transform: `translateY(${p2IconY}px)` }}>😔</div>
        <div style={{ opacity: p2TextOp, transform: `translateY(${p2TextY}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 140, fontWeight: 900, color: C.textPrimary, lineHeight: 1.1 }}>못 들어가셨죠?</div>
        </div>
        <div style={{ opacity: p2SubOp, marginTop: 32, fontSize: 44, color: C.textSub, fontWeight: 600, transform: `scale(${p2Breathe})` }}>
          아직 늦지 않았습니다 →
        </div>
      </div>

      {/* ═══ PHASE 3 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph3 }}>
        <div style={{ fontSize: 108, lineHeight: 1, marginBottom: 18, opacity: p3Icon, filter: GLOW.strong.filter }}>🎯</div>
        <div style={{ fontSize: 96, fontWeight: 900, color: C.textSub, lineHeight: 1.1, opacity: p3L1Op, transform: `translateY(${p3L1Y}px)`, textAlign: 'center' }}>진짜 기회는</div>
        <div style={{ fontSize: 108, fontWeight: 900, color: C.main, lineHeight: 1.1, marginTop: 6, opacity: p3L2Op, transform: `translateY(${p3L2Y}px) scale(${p3L2Pulse})`, textShadow: p3DynGlow, textAlign: 'center' }}>따로 있습니다</div>
        <div style={{
          opacity: p3BoxOp, transform: `translateY(${p3BoxY}px)`, marginTop: 40,
          background: 'rgba(0,255,208,0.07)', border: `1.5px solid ${C.main}`,
          borderRadius: 20, padding: '20px 56px', boxShadow: GLOW.weak.box,
        }}>
          <div style={{ fontSize: 38, fontWeight: 700, color: C.textPrimary, textAlign: 'center' }}>
            ⏱️ 2차 나오기 전에, <span style={{ color: C.main, textShadow: GLOW.mid.text }}>딱 5분만</span> 시간 내주세요
          </div>
        </div>
      </div>

      {/* 자막 바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[
          { o: cap1, text: <><span style={{ color: C.main }}>모바일 10분 / 전체 이틀</span> — 6,000억 완판</> },
          { o: cap2, text: <>못 들어가셨죠? <span style={{ color: C.main }}>아직 늦지 않았습니다</span></> },
          { o: cap3, text: <>진짜 기회는 따로 있습니다 — <span style={{ color: C.main }}>5분만 시간 내주세요</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{ position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center', paddingInline: 80, opacity: o, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
