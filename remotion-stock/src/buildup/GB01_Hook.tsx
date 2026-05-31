// GB01 — 씬1 훅 v3 (30초 = 930프레임)
// Phase1: 💸 "이틀 만에 완판" 임팩트 (f0~300)
//   - 10분 완판(모바일 앱) / 이틀 완판(전체 6,000억) 구분 표시
// Phase2: 😔 "못 들어가셨죠?" 공감 (f300~540)
// Phase3: 🎯 "진짜 기회는 따로" 반전 (f540~900)
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO     = 'audio/국씬1.m4a';
const HAS_AUDIO = false;

const fi = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const fo = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const lr = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

export const GB01_Hook = () => {
  const f = useCurrentFrame();
  const bgGlow = Math.sin(f * 0.035) * 0.03 + 0.045;

  // ─── Phase 전환 ───
  const ph1 = f < 255 ? fi(0, 18)(f) : fo(255, 300)(f);
  const ph2 = f < 300 ? 0 : f < 490 ? fi(300, 330)(f) : fo(490, 540)(f);
  const ph3 = f < 540 ? 0 : fi(540, 570)(f);

  // 스캔라인
  const scanY  = lr(-2, 104, 0, 36)(f);
  const scanOp = f < 36 ? interpolate(f, [0, 4, 30, 36], [0, 1, 1, 0]) : 0;

  // ─── Phase1 ───
  const p1Icon   = fi(12, 45)(f);
  const p1TitleOp= fi(30, 65)(f);
  const p1TitleX = lr(-200, 0, 30, 65)(f);
  const p1Sub1Op = fi(65, 100)(f);
  const p1Sub1Y  = lr(20, 0, 65, 100)(f);

  // 10분 카드 (f110~155)
  const p1C1Op   = fi(110, 155)(f);
  const p1C1Y    = lr(30, 0, 110, 155)(f);
  // 이틀 카드 (f155~200)
  const p1C2Op   = fi(155, 200)(f);
  const p1C2Y    = lr(30, 0, 155, 200)(f);

  // 글로우 버스트
  const burstOp    = interpolate(f, [195, 202, 232], [0, 0.5, 0], { extrapolateRight: 'clamp' });
  const burstScale = lr(0.2, 2.8, 195, 232)(f);

  const p1Pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const p1GlowSz = interpolate(p1Pulse, [0, 1], [10, 36]);
  const p1DynGlow = `0 0 ${p1GlowSz}px #00FFD0, 0 0 ${p1GlowSz*2}px rgba(0,255,208,0.55), 0 0 ${p1GlowSz*4}px rgba(0,191,154,0.3)`;

  // ─── Phase2 ───
  const p2Icon  = fi(305, 335)(f);
  const p2IconY = lr(40, 0, 305, 335)(f);
  const p2TextOp= fi(345, 385)(f);
  const p2TextY = lr(30, 0, 345, 385)(f);
  const p2SubOp = fi(415, 455)(f);
  const p2Breathe = Math.sin(f * 0.09) * 0.025 + 1;

  // ─── Phase3 ───
  const p3Icon  = fi(548, 578)(f);
  const p3L1Op  = fi(582, 622)(f);
  const p3L1Y   = lr(36, 0, 582, 622)(f);
  const p3L2Op  = fi(635, 675)(f);
  const p3L2Y   = lr(36, 0, 635, 675)(f);
  const p3L2Pulse = Math.sin(f * 0.08) * 0.025 + 1;
  const p3BoxOp = fi(708, 752)(f);
  const p3BoxY  = lr(20, 0, 708, 752)(f);
  const p3DynGlow = `0 0 ${p1GlowSz}px #00FFD0, 0 0 ${p1GlowSz*2}px rgba(0,255,208,0.55)`;

  // ─── 자막 ───
  const cap1 = ph1 > 0.5 ? fi(170, 210)(f) : 0;
  const cap2 = ph2 > 0.1 ? fi(400, 440)(f) : 0;
  const cap3 = ph3 > 0.1 ? fi(690, 730)(f) : 0;

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
          { o: cap1, text: <><span style={{ color: C.main }}>모바일 10분 / 전체 ��틀</span> — 6,000억 완판</> },
          { o: cap2, text: <>못 들어가셨죠? <span style={{ color: C.main }}>아직 늦지 않았습니다</span></> },
          { o: cap3, text: <>진짜 기회는 따로 있습니다 — <span style={{ color: C.main }}>5분만 시간 내주세요</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{ position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center', paddingInline: 80, opacity: o, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
