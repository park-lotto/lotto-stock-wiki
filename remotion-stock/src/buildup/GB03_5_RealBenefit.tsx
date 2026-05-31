// GB03_5 — 씬3_5 "진짜 수혜주" Sequence 오디오 연결 (183초 = 5529프레임)
// Whisper:
//   f0~2028:    국씬3-1.m4a (67.6s) — 총알장전 / DSC 비상장
//   f2028~3219: 국씨3-2.m4a (39.7s) — 저리대출 호재조건 / 엘앤에프 LFP
//   f3219~3699: 국씬3-3.m4a (16.0s) — 엘앤에프 차트
//   f3699~4815: 국씬3-4.m4a (37.2s) — 에코프로비엠
//   f4815~5499: 국씬3-5.m4a (22.8s) — 효성중공업·LS
// Phase1 f0~700    💰 총알 장전
// Phase2 f700~2028 🚫 비상장 함정 / DSC
// Phase3 f2028~3699 🔑 호재조건 + 엘앤에프
// Phase4 f3699~4815 🔋 에코프로비엠
// Phase5 f4815~5529 ⚡ 효성중공업·LS
import { AbsoluteFill, Audio, Easing, interpolate, Sequence, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

// 오디오 파일 구간 (프레임)
const A1_START = 0;    const A1_DUR = 2028; // 국씬3-1 67.6s
const A2_START = 2028; const A2_DUR = 1191; // 국씨3-2 39.7s
const A3_START = 3219; const A3_DUR = 480;  // 국씬3-3 16.0s
const A4_START = 3699; const A4_DUR = 1116; // 국씬3-4 37.2s
const A5_START = 4815; const A5_DUR = 684;  // 국씬3-5 22.8s

const fi = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const fo = (fa: number, fb: number) => (f: number) =>
  interpolate(f, [fa, fb], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const lr = (a: number, b: number, fa: number, fb: number, ea = Easing.out(Easing.cubic)) =>
  (f: number) => interpolate(f, [fa, fb], [a, b], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ea });

export const GB03_5_RealBenefit = () => {
  const f = useCurrentFrame();
  const bgGlow = Math.sin(f * 0.025) * 0.025 + 0.04;

  // ─── Phase 전환 ───
  const ph1 = f < 700 ? fi(0, 20)(f) : fo(700, 760)(f);
  const ph2 = f < 720 ? 0 : f < 1980 ? fi(720, 768)(f) : fo(1980, 2028)(f);
  const ph3 = f < 2028 ? 0 : f < 3650 ? fi(2028, 2075)(f) : fo(3650, 3699)(f);
  const ph4 = f < 3699 ? 0 : f < 4768 ? fi(3699, 3747)(f) : fo(4768, 4815)(f);
  const ph5 = f < 4815 ? 0 : fi(4815, 4862)(f);

  // 스캔라인
  const scanY  = lr(-2, 104, 0, 36)(f);
  const scanOp = f < 36 ? interpolate(f, [0, 4, 30, 36], [0, 1, 1, 0]) : 0;

  // ─── Phase1: 총알 장전 ───
  const p1Icon   = fi(12, 45)(f);
  const p1L1Op   = fi(35, 72)(f);
  const p1L1Y    = lr(36, 0, 35, 72)(f);
  const p1L2Op   = fi(75, 115)(f);
  const p1L2X    = lr(220, 0, 75, 115)(f);
  const p1Pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const p1GSz    = interpolate(p1Pulse, [0, 1], [10, 38]);
  const p1Glow   = `0 0 ${p1GSz}px #00FFD0, 0 0 ${p1GSz*2}px rgba(0,255,208,0.55), 0 0 ${p1GSz*4}px rgba(0,191,154,0.3)`;
  const p1Breathe = p1L2Op > 0.9 ? Math.sin(f * 0.08) * 0.02 + 1 : 1;
  // f360: "펀드 설정 6/12" Whisper / f581: "총알 장전" Whisper
  const p1D1Op   = fi(340, 380)(f);
  const p1D2Op   = fi(560, 600)(f);
  const p1Bullet = fi(610, 650)(f);
  const p1BulPulse = Math.sin(f * 0.12) * 0.04 + 1;

  // ─── Phase2: 비상장 함정 ───
  const p2ScanY  = lr(-2, 104, 720, 758)(f);
  const p2ScanOp = f >= 720 && f < 758 ? interpolate(f, [720, 724, 752, 758], [0, 1, 1, 0]) : 0;
  const p2Icon   = fi(770, 803)(f);
  const p2TitleOp= fi(810, 847)(f);
  // f871: 퓨리오사AI Whisper / f1025: 창투사 → DSC 카드
  const p2C1Op   = fi(875, 915)(f);
  const p2ArrowOp= fi(930, 965)(f);
  const p2C2Op   = fi(980, 1020)(f);
  // f1348: DSC / f1474: 상한가→윗꼬리 (단일 봉: 양봉 상승→윗꼬리→음봉 전환)
  const p2Chart      = fi(1330, 1380)(f);
  const p2Warn       = fi(1490, 1530)(f);
  const candleBodyH  = Math.round(130 * lr(0, 1, 1340, 1430)(f));       // 양봉 몸통 성장
  const candleTailH  = Math.round(90  * lr(0, 1, 1430, 1500)(f));       // 윗꼬리 성장
  const isNegCandle  = f > 1490;                                          // 1490 이후 음봉 전환
  const candleColor  = isNegCandle ? C.dataDown : C.dataUp;
  // f1757: "고점 물리면 긴 시간"
  const p2CautionOp = fi(1740, 1790)(f);

  // ─── Phase3: 호재조건 + 엘앤에프 ───
  const p3ScanY  = lr(-2, 104, 2028, 2066)(f);
  const p3ScanOp = f >= 2028 && f < 2066 ? interpolate(f, [2028, 2032, 2060, 2066], [0, 1, 1, 0]) : 0;

  // Phase3a: 호재조건 박스 (f2028~2498)
  const p3aBoxSc  = lr(0.82, 1, 2038, 2103)(f);
  const p3aTextOp = fi(2106, 2153)(f);
  const p3aPulse  = Math.sin(f * 0.1) * 0.025 + 1;
  const p3aVis = f >= 2028 && f < 2498 ? fi(2028, 2060)(f) : (f >= 2498 ? fo(2498, 2548)(f) : 0);

  // Phase3b: 엘앤에프 (f2498~3699)
  // f2498: "LNF" / f2639: "LFP 공장" / f2800: "2200억" / f3116: "국내 처음"
  const p3bVis = f < 2498 ? 0 : f < 3650 ? fi(2498, 2548)(f) : fo(3650, 3699)(f);
  const p3bBadgeOp= fi(2510, 2555)(f);
  const p3bIcon   = fi(2560, 2595)(f);
  const p3bL1Op   = fi(2600, 2640)(f);
  const p3bL1Y    = lr(40, 0, 2600, 2640)(f);
  const p3bN1Op   = fi(2650, 2695)(f);
  const p3bN1Sc   = interpolate(f, [2650, 2705], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const p3bN2Op   = fi(2800, 2845)(f);
  const p3bN2Sc   = interpolate(f, [2800, 2855], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const p3bN3Op   = fi(3116, 3161)(f);
  const p3bN3Sc   = interpolate(f, [3116, 3171], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const p3bLFPOp  = fi(2970, 3020)(f);
  // f3219: 국씬3-3 시작 "60일선 쌍바닥"
  const p3bChartOp= fi(3219, 3269)(f);

  // ─── Phase4: 에코프로비엠 ───
  const p4ScanY  = lr(-2, 104, 3699, 3737)(f);
  const p4ScanOp = f >= 3699 && f < 3737 ? interpolate(f, [3699, 3703, 3731, 3737], [0, 1, 1, 0]) : 0;
  // f3699: "에코프로비엠" / f3925: "코스닥 중소형" / f4076: "6/15 자금" / f4346: "11% 유지"
  const p4BadgeOp= fi(3711, 3756)(f);
  const p4Icon   = fi(3761, 3796)(f);
  const p4L1Op   = fi(3803, 3846)(f);
  const p4L1Y    = lr(40, 0, 3803, 3846)(f);
  const p4ChipOp = fi(3965, 4015)(f);
  const p4ArrowOp= fi(4090, 4140)(f);
  const p4NoteOp = fi(4346, 4396)(f);
  const p4ChartOp= fi(4561, 4611)(f);
  const p4Pulse  = Math.sin(f * 0.09) * 0.5 + 0.5;

  // ─── Phase5: 효성중공업·LS ───
  const p5ScanY  = lr(-2, 104, 4815, 4853)(f);
  const p5ScanOp = f >= 4815 && f < 4853 ? interpolate(f, [4815, 4819, 4847, 4853], [0, 1, 1, 0]) : 0;
  // f4815: "효성중공업·LS" / f5073: "스마일게이트" / f5287: "발주공시 시점"
  const p5Icon   = fi(4825, 4860)(f);
  const p5L1Op   = fi(4865, 4905)(f);
  const p5L1Y    = lr(40, 0, 4865, 4905)(f);
  const p5C1Op   = fi(4930, 4970)(f);
  const p5C2Op   = fi(5073, 5113)(f);
  const p5NoteOp = fi(5287, 5327)(f);
  const p5Pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;

  // 자막
  const cap1 = ph1 > 0.5  ? fi(560, 600)(f) : 0;   // "총알 장전 — 6/15 집행"
  const cap2 = ph2 > 0.1  ? fi(1757, 1797)(f) : 0;  // "고점 물리면 긴 시간"
  const cap3 = ph3 > 0.1  ? fi(2800, 2840)(f) * fo(3100, 3160)(f) : 0;  // "이 대출" — f3160 전에 사라져 cap4와 겹침 방지
  const cap4 = fi(3219, 3259)(f) * fo(3640, 3699)(f); // "엘앤에프 — 60일선 지지" — Phase3 끝 전 fadeout
  const cap5 = ph4 > 0.1  ? fi(4346, 4386)(f) : 0;  // "에코프로비엠 — 완판날 11%"
  const cap6 = ph5 > 0.1  ? fi(5073, 5113)(f) : 0;  // "발주공시 나오는 시점 주목"

  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, overflow: 'hidden' }}>
      {/* ─── 오디오 Sequence 연결 ─── */}
      <Sequence from={A1_START} durationInFrames={A1_DUR}>
        <Audio src={staticFile('audio/국씬3-1.m4a')} />
      </Sequence>
      <Sequence from={A2_START} durationInFrames={A2_DUR}>
        <Audio src={staticFile('audio/국씨3-2.m4a')} />
      </Sequence>
      <Sequence from={A3_START} durationInFrames={A3_DUR}>
        <Audio src={staticFile('audio/국씬3-3.m4a')} />
      </Sequence>
      <Sequence from={A4_START} durationInFrames={A4_DUR}>
        <Audio src={staticFile('audio/국씬3-4.m4a')} />
      </Sequence>
      <Sequence from={A5_START} durationInFrames={A5_DUR}>
        <Audio src={staticFile('audio/국씬3-5.m4a')} />
      </Sequence>

      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: `radial-gradient(ellipse 70% 50% at 50% 50%, rgba(0,255,208,${bgGlow}) 0%, transparent 70%)` }} />
      {f < 36 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: scanOp, zIndex: 10 }} />}

      {/* Phase2 스캔라인 */}
      {f >= 720 && f < 758 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${p2ScanY}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: p2ScanOp, zIndex: 10 }} />}
      {/* Phase3 스캔라인 */}
      {f >= 2028 && f < 2066 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${p3ScanY}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: p3ScanOp, zIndex: 10 }} />}
      {/* Phase4 스캔라인 */}
      {f >= 3699 && f < 3737 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${p4ScanY}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: p4ScanOp, zIndex: 10 }} />}
      {/* Phase5 스캔라인 */}
      {f >= 4815 && f < 4853 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${p5ScanY}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: p5ScanOp, zIndex: 10 }} />}

      {/* ═══ PHASE 1 — 총알 장전 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph1, gap: 12 }}>
        <div style={{ fontSize: 140, lineHeight: 1, opacity: p1Icon, filter: GLOW.strong.filter }}>💰</div>
        <div style={{ fontSize: 48, color: C.textSub, fontWeight: 600, opacity: p1L1Op, transform: `translateY(${p1L1Y}px)` }}>6,000억 들어왔는데 왜 조용한가요?</div>
        <div style={{ fontSize: 140, fontWeight: 900, color: C.main, lineHeight: 1, opacity: p1L2Op, transform: `translateX(${p1L2X}px) scale(${p1Breathe})`, textShadow: p1L2Op > 0.5 ? p1Glow : 'none', textAlign: 'center' }}>아직 안 쐈습니다</div>

        <div style={{ display: 'flex', gap: 28, marginTop: 20 }}>
          {[
            { o: p1D1Op, date: '6월 12일', label: '펀드 설정', active: false, icon: '📋' },
            { o: p1D2Op, date: '6월 15일', label: '실제 집행 시작', active: true, icon: '🚀' },
          ].map(({ o, date, label, active, icon }) => (
            <div key={date} style={{ opacity: o, background: active ? 'rgba(0,255,208,0.08)' : 'rgba(255,255,255,0.04)', border: `2px solid ${active ? C.main : C.borderSub}`, borderRadius: 20, padding: '22px 44px', textAlign: 'center', boxShadow: active ? GLOW.weak.box : 'none' }}>
              <div style={{ fontSize: 44, marginBottom: 8 }}>{icon}</div>
              <div style={{ fontSize: 44, fontWeight: 900, color: active ? C.main : C.textSub, textShadow: active ? GLOW.mid.text : 'none' }}>{date}</div>
              <div style={{ fontSize: 22, color: active ? C.textPrimary : '#555', marginTop: 4 }}>{label}</div>
            </div>
          ))}
        </div>

        <div style={{ opacity: p1Bullet, fontSize: 32, color: C.main, transform: `scale(${p1BulPulse})`, textShadow: GLOW.weak.text, marginTop: 8 }}>
          ⚡ 총알 장전 상태 — 아직 안 쐈습니다
        </div>
      </div>

      {/* ═══ PHASE 2 — 비상장 함정 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph2, padding: '0 100px', gap: 20 }}>
        <div style={{ fontSize: 120, lineHeight: 1, opacity: p2Icon, filter: GLOW.mid.filter }}>🚫</div>
        <div style={{ opacity: p2TitleOp, fontSize: 48, fontWeight: 800, color: C.textSub, textAlign: 'center' }}>여기서 다들 오해합니다</div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ opacity: p2C1Op, background: 'rgba(255,255,255,0.04)', border: '1.5px solid #333', borderRadius: 20, padding: '24px 36px', textAlign: 'center', minWidth: 240 }}>
            <div style={{ fontSize: 56 }}>🤖</div>
            <div style={{ fontSize: 32, fontWeight: 900, color: C.textPrimary, marginTop: 10 }}>퓨리오사AI</div>
            <div style={{ fontSize: 22, color: '#FF6B6B', fontWeight: 700, marginTop: 8 }}>❌ 비상장 — 직접 투자 불가</div>
          </div>

          <div style={{ opacity: p2ArrowOp, fontSize: 52, color: C.textSub }}>→</div>

          <div style={{ opacity: p2C2Op, background: 'rgba(255,255,255,0.04)', border: '1.5px solid #333', borderRadius: 20, padding: '24px 36px', textAlign: 'center', minWidth: 260 }}>
            <div style={{ fontSize: 56 }}>🏦</div>
            <div style={{ fontSize: 32, fontWeight: 900, color: C.textPrimary, marginTop: 10 }}>DSC인베스트먼트</div>
            <div style={{ fontSize: 18, color: C.textSub, marginTop: 6 }}>지분 투자사 → IPO 시 수익</div>
          </div>

          {/* 단일 봉 (양봉 올라가다 윗꼬리 달고 음봉 전환) */}
          <div style={{ opacity: p2Chart, display: 'flex', flexDirection: 'column', alignItems: 'center', marginLeft: 24, gap: 0 }}>
            <div style={{ width: 4, height: candleTailH, background: candleColor, borderRadius: 2 }} />
            <div style={{ width: 48, height: Math.max(4, candleBodyH), background: candleColor, borderRadius: 3, boxShadow: `0 0 14px ${candleColor}80` }} />
            <div style={{ opacity: p2Warn, marginTop: 10, fontSize: 18, color: '#FF6B6B', fontWeight: 700, whiteSpace: 'nowrap' }}>윗꼬리 → 음봉</div>
          </div>
        </div>

        <div style={{ opacity: p2CautionOp, fontSize: 32, color: '#FF9800', fontWeight: 600, textAlign: 'center', marginTop: 12 }}>
          ⚠️ 고점에 물리면 긴 시간 필요 — 변동성 주의
        </div>
      </div>

      {/* ═══ PHASE 3a — 호재 조건 (f2028~2548 독립) ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: p3aVis }}>
        <div style={{ transform: `scale(${p3aBoxSc * p3aPulse})`, background: 'rgba(0,255,208,0.05)', border: `2px solid ${C.main}`, borderRadius: 28, padding: '60px 100px', textAlign: 'center', boxShadow: GLOW.mid.box, maxWidth: 920 }}>
          <div style={{ fontSize: 28, color: C.textSub, marginBottom: 24, fontWeight: 500, letterSpacing: 2 }}>저리대출이 진짜 호재가 되는 조건</div>
          <div style={{ fontSize: 56, fontWeight: 900, color: C.textPrimary, lineHeight: 1.5, opacity: p3aTextOp }}>
            <span style={{ color: C.main }}>"이 대출 없었으면</span><br />못 했을 사업을<br /><span style={{ color: C.main }}>이제 할 수 있게 됐다"</span>
          </div>
        </div>
      </div>

      {/* ═══ PHASE 3b — 엘앤에프 (f2498~3699 독립) ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: p3bVis, paddingInline: 100, gap: 16 }}>
        <div style={{ opacity: p3bBadgeOp, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ background: C.dataUp, color: '#fff', fontSize: 18, fontWeight: 900, padding: '6px 20px', borderRadius: 30 }}>🔴 1군</div>
          <div style={{ fontSize: 22, color: C.textSub }}>직접 확정 + 인과관계 명확</div>
        </div>

        <div style={{ opacity: p3bIcon, fontSize: 64, lineHeight: 1 }}>🏭</div>

        <div style={{ opacity: p3bL1Op, transform: `translateY(${p3bL1Y}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 88, fontWeight: 900, color: C.main, lineHeight: 1 }}>엘앤에프</div>
          <div style={{ fontSize: 24, color: C.textSub, marginTop: 4 }}>코스피 · 이차전지 양극재</div>
        </div>

        <div style={{ display: 'flex', gap: 20, marginTop: 4 }}>
          {[
            { o: p3bN1Op, sc: p3bN1Sc, v: '2,200억', l: '저리대출', icon: '💰' },
            { o: p3bN2Op, sc: p3bN2Sc, v: '12년',    l: '장기 대출', icon: '📅' },
            { o: p3bN3Op, sc: p3bN3Sc, v: '국내 최초', l: 'LFP 공장', icon: '🏗️' },
          ].map(({ o, sc, v, l, icon }) => (
            <div key={l} style={{ opacity: o, transform: `scale(${sc})`, background: '#111', border: '1px solid #333', borderRadius: 14, padding: '18px 32px', textAlign: 'center' }}>
              <div style={{ fontSize: 32 }}>{icon}</div>
              <div style={{ fontSize: 40, fontWeight: 900, color: C.main, marginTop: 6 }}>{v}</div>
              <div style={{ fontSize: 18, color: C.textSub, marginTop: 4 }}>{l}</div>
            </div>
          ))}
        </div>

        <div style={{ opacity: p3bLFPOp, background: '#111', border: '1px solid #2a2a2a', borderRadius: 12, padding: '14px 28px' }}>
          <div style={{ fontSize: 22, color: '#888', fontWeight: 600 }}>중국 장악 LFP 시장 — 이 대출 없으면 못 하는 국내 첫 공장</div>
        </div>

        <div style={{ opacity: p3bChartOp, display: 'flex', gap: 16 }}>
          {['📊 60일선 쌍바닥 지지', '🎯 20일선 저항 돌파 주목'].map(t => (
            <div key={t} style={{ background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 8, padding: '10px 18px', fontSize: 18, color: '#666' }}>{t}</div>
          ))}
        </div>
      </div>

      {/* ═══ PHASE 4 — 에코프로비엠 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph4, padding: '0 80px', gap: 14 }}>
        <div style={{ opacity: p4BadgeOp, display: 'flex', alignItems: 'center', gap: 16, marginBottom: 4 }}>
          <div style={{ background: '#FF9800', color: '#fff', fontSize: 20, fontWeight: 900, padding: '8px 24px', borderRadius: 30 }}>🟠 2군</div>
          <div style={{ fontSize: 24, color: C.textSub }}>자금 유입 최전선 — 개별 확정 아님</div>
        </div>

        <div style={{ opacity: p4Icon, fontSize: 80, lineHeight: 1 }}>🔋</div>

        <div style={{ opacity: p4L1Op, transform: `translateY(${p4L1Y}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 96, fontWeight: 900, color: '#FF9800', lineHeight: 1, textShadow: `0 0 ${interpolate(p4Pulse, [0, 1], [8, 24])}px rgba(255,152,0,0.5)` }}>에코프로비엠</div>
          <div style={{ fontSize: 28, color: C.textSub, marginTop: 4 }}>코스닥 시총 1위</div>
        </div>

        <div style={{ opacity: p4ChipOp, display: 'flex', gap: 18, flexWrap: 'wrap', justifyContent: 'center' }}>
          {[
            { t: '코스닥 중소형 집중 펀드', c: C.main },
            { t: '6/15 이후 자금 유입', c: '#FF9800' },
            { t: '시총 대장 먼저 흡수', c: C.dataUp },
          ].map(({ t, c }) => (
            <div key={t} style={{ background: `${c}20`, border: `1.5px solid ${c}55`, borderRadius: 24, padding: '10px 24px', fontSize: 22, color: c, fontWeight: 700 }}>{t}</div>
          ))}
        </div>

        <div style={{ opacity: p4ArrowOp, display: 'flex', alignItems: 'center', gap: 16, fontSize: 26 }}>
          {['코스닥 자금 흘러들 때', '→', '시총 대장', '→', '에코프로비엠 최전선'].map((t, i) => (
            <div key={i} style={{ color: i % 2 === 0 ? C.textPrimary : C.main, fontWeight: i % 2 === 0 ? 700 : 400 }}>{t}</div>
          ))}
        </div>

        <div style={{ opacity: p4NoteOp, background: 'rgba(255,152,0,0.06)', border: '1.5px solid rgba(255,152,0,0.3)', borderRadius: 16, padding: '16px 32px', textAlign: 'center' }}>
          <div style={{ fontSize: 24, color: '#FF9800', fontWeight: 700 }}>✅ 완판날 +11% · 지금도 유지 중</div>
        </div>

        <div style={{ opacity: p4ChartOp, display: 'flex', gap: 20 }}>
          {['📊 정배열 완성', '🎯 장대양봉 하나', '📈 신고가 가능 자리'].map(t => (
            <div key={t} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid #222', borderRadius: 10, padding: '10px 20px', fontSize: 20, color: C.textSub }}>{t}</div>
          ))}
        </div>
      </div>

      {/* ═══ PHASE 5 — 효성중공업·LS ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph5, padding: '0 80px', gap: 20 }}>
        <div style={{ opacity: p5Icon, fontSize: 100, lineHeight: 1, filter: GLOW.mid.filter }}>⚡</div>

        <div style={{ opacity: p5L1Op, transform: `translateY(${p5L1Y}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 28, color: C.textSub, marginBottom: 8 }}>데이터센터 관련</div>
          <div style={{ fontSize: 88, fontWeight: 900, color: C.textPrimary, lineHeight: 1.1, textShadow: `0 0 ${interpolate(p5Pulse, [0, 1], [8, 20])}px rgba(0,255,208,0.3)` }}>
            효성중공업 · <span style={{ color: C.main }}>LS일렉트릭</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 24, opacity: p5C1Op }}>
          {[
            { icon: '🏗️', name: '효성중공업', tag: '전력기기' },
            { icon: '⚡', name: 'LS일렉트릭', tag: '전력·자동화' },
          ].map(({ icon, name, tag }) => (
            <div key={name} style={{ background: 'rgba(255,255,255,0.04)', border: '1.5px solid #333', borderRadius: 20, padding: '28px 48px', textAlign: 'center' }}>
              <div style={{ fontSize: 60 }}>{icon}</div>
              <div style={{ fontSize: 36, fontWeight: 900, color: C.textPrimary, marginTop: 10 }}>{name}</div>
              <div style={{ fontSize: 20, color: C.textSub, marginTop: 6 }}>{tag}</div>
            </div>
          ))}
        </div>

        <div style={{ opacity: p5C2Op, background: 'rgba(0,255,208,0.05)', border: `1.5px solid ${C.borderSub}`, borderRadius: 16, padding: '20px 36px', textAlign: 'center' }}>
          <div style={{ fontSize: 28, color: C.textSub, fontWeight: 600 }}>
            📡 스마일게이트 발주 구체화 → 기대감 트리거
          </div>
        </div>

        <div style={{ opacity: p5NoteOp, background: 'rgba(255,184,0,0.06)', border: '1.5px solid rgba(255,184,0,0.3)', borderRadius: 16, padding: '16px 32px' }}>
          <div style={{ fontSize: 26, color: '#FFB800', fontWeight: 700, textAlign: 'center' }}>
            ⏱️ 지금 당장보다 발주 공시 나오는 시점을 보세요
          </div>
        </div>
      </div>

      {/* 자막 바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[
          { o: cap1, text: <>총알 장전 상태 — <span style={{ color: C.main }}>6월 15일 실제 집행 시작</span></> },
          { o: cap2, text: <>비상장 연결 — <span style={{ color: '#FF9800' }}>고점에 물리면 긴 시간 필요</span></> },
          { o: cap3, text: <><span style={{ color: C.main }}>"이 대출 없었으면 못 했을 사업"</span></> },
          { o: cap4, text: <>엘앤에프 — <span style={{ color: C.main }}>국내 최초 LFP 공장 · 60일선 지지</span></> },
          { o: cap5, text: <>에코프로비엠 — <span style={{ color: '#FF9800' }}>완판날 +11% · 자금 유입 최전선</span></> },
          { o: cap6, text: <>효성·LS — <span style={{ color: '#FFB800' }}>발주 공시 나오는 시점 주목</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{ position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center', paddingInline: 80, opacity: o, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
