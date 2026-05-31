// GB03_5 — 씬NEW "진짜 수혜주" v2 (90초 = 2730프레임)
// Phase1 (f0~450):   ⚡ 총알 장전 — 6/15 날짜 BIG
// Phase2 (f450~900): 🚫 비상장 함정 — DSC 윗꼬리
// Phase3 (f900~1200): 📉 대형주 저리대출 소수점
// Phase4 (f1200~1500): 🔑 호재 조건 정의 — 큰 인용문
// Phase5 (f1500~2200): 🔴 엘앤에프 1군 — 수치 HUGE
// Phase6 (f2200~2730): 🟠 에코프로비엠 2군 — 정배열 흐름
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const AUDIO     = 'audio/GB03_5_voice.mp3';
const HAS_AUDIO = false;

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
  const ph1 = f < 390 ? fi(0, 20)(f) : fo(390, 450)(f);
  const ph2 = f < 450 ? 0 : f < 840 ? fi(450, 490)(f) : fo(840, 900)(f);
  const ph3 = f < 900 ? 0 : f < 1150 ? fi(900, 940)(f) : fo(1150, 1200)(f);
  const ph4 = f < 1200 ? 0 : f < 1450 ? fi(1200, 1245)(f) : fo(1450, 1500)(f);
  const ph5 = f < 1500 ? 0 : f < 2150 ? fi(1500, 1545)(f) : fo(2150, 2200)(f);
  const ph6 = f < 2200 ? 0 : fi(2200, 2248)(f);

  // 스캔라인
  const scanY  = lr(-2, 104, 0, 36)(f);
  const scanOp = f < 36 ? interpolate(f, [0, 4, 30, 36], [0, 1, 1, 0]) : 0;

  // ─── Phase1 ───
  const p1Icon   = fi(12, 45)(f);
  const p1L1Op   = fi(35, 72)(f);
  const p1L1Y    = lr(36, 0, 35, 72)(f);
  const p1L2Op   = fi(75, 115)(f);
  const p1L2X    = lr(220, 0, 75, 115)(f);
  const p1Pulse  = Math.sin(f * 0.07) * 0.5 + 0.5;
  const p1GSz    = interpolate(p1Pulse, [0, 1], [10, 38]);
  const p1Glow   = `0 0 ${p1GSz}px #00FFD0, 0 0 ${p1GSz*2}px rgba(0,255,208,0.55), 0 0 ${p1GSz*4}px rgba(0,191,154,0.3)`;
  const p1Breathe = p1L2Op > 0.9 ? Math.sin(f * 0.08) * 0.02 + 1 : 1;
  const p1D1Op   = fi(150, 200)(f);
  const p1D2Op   = fi(215, 265)(f);
  const p1Bullet = fi(290, 330)(f);
  const p1BulPulse = Math.sin(f * 0.12) * 0.04 + 1;

  // ─── Phase2 ───
  const p2Icon   = fi(455, 488)(f);
  const p2TitleOp= fi(495, 532)(f);
  const p2C1Op   = fi(545, 585)(f);
  const p2ArrowOp= fi(600, 635)(f);
  const p2C2Op   = fi(648, 688)(f);
  const p2Chart  = fi(710, 755)(f);
  const p2Warn   = fi(755, 798)(f);
  const candleH  = lr(0, 1, 720, 790)(f);

  // ─── Phase3 ───
  const p3Icon   = fi(908, 942)(f);
  const p3TitleOp= fi(950, 988)(f);
  const p3L1Op   = fi(1000, 1040)(f);
  const p3L1Y    = lr(30, 0, 1000, 1040)(f);
  const p3BigOp  = fi(1060, 1108)(f);
  const p3BigSc  = interpolate(f, [1060, 1108], [0.7, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });

  // ─── Phase4 ───
  const p4BoxSc  = lr(0.82, 1, 1210, 1275)(f);
  const p4TextOp = fi(1278, 1325)(f);
  const p4Pulse  = Math.sin(f * 0.1) * 0.025 + 1;

  // ─── Phase5 ───
  const p5BadgeOp= fi(1510, 1550)(f);
  const p5Icon   = fi(1555, 1590)(f);
  const p5L1Op   = fi(1595, 1635)(f);
  const p5L1Y    = lr(40, 0, 1595, 1635)(f);
  const p5N1Op   = fi(1665, 1710)(f);
  const p5N1Sc   = interpolate(f, [1665, 1720], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const p5N2Op   = fi(1730, 1775)(f);
  const p5N2Sc   = interpolate(f, [1730, 1785], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const p5N3Op   = fi(1795, 1840)(f);
  const p5N3Sc   = interpolate(f, [1795, 1850], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.elastic(1.2)) });
  const p5LFPOp  = fi(1875, 1925)(f);
  const p5Pulse  = Math.sin(f * 0.08) * 0.5 + 0.5;
  const p5GSz    = interpolate(p5Pulse, [0, 1], [12, 36]);
  const p5ChartOp= fi(1970, 2020)(f);

  // ─── Phase6 ───
  const p6BadgeOp= fi(2210, 2255)(f);
  const p6Icon   = fi(2260, 2295)(f);
  const p6L1Op   = fi(2302, 2345)(f);
  const p6L1Y    = lr(40, 0, 2302, 2345)(f);
  const p6ChipOp = fi(2365, 2415)(f);
  const p6ArrowOp= fi(2450, 2500)(f);
  const p6Pulse  = Math.sin(f * 0.09) * 0.5 + 0.5;

  // 자막
  const cap1 = ph1 > 0.5 ? fi(280, 318)(f) : 0;
  const cap2 = ph2 > 0.1 ? fi(770, 808)(f) : 0;
  const cap3 = ph3 > 0.1 ? fi(1065, 1105)(f) : 0;
  const cap4 = ph4 > 0.1 ? fi(1290, 1330)(f) : 0;
  const cap5 = ph5 > 0.1 ? fi(1940, 1980)(f) : 0;
  const cap6 = ph6 > 0.1 ? fi(2360, 2400)(f) : 0;

  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, overflow: 'hidden' }}>
      {HAS_AUDIO && <Audio src={staticFile(AUDIO)} />}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: `radial-gradient(ellipse 70% 50% at 50% 50%, rgba(0,255,208,${bgGlow}) 0%, transparent 70%)` }} />
      {f < 36 && <div style={{ position: 'absolute', left: 0, right: 0, top: `${scanY}%`, height: 2, background: 'linear-gradient(90deg, transparent, #00FFD0, #80FFE8, #00FFD0, transparent)', opacity: scanOp, zIndex: 10 }} />}

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

          {/* 봉차트 */}
          <div style={{ opacity: p2Chart, display: 'flex', alignItems: 'flex-end', gap: 8, marginLeft: 16 }}>
            {[
              { b: 40, u: 0, l: 5, up: true },
              { b: 48, u: 0, l: 6, up: true },
              { b: 14, u: Math.round(90 * candleH), l: 6, up: true, hi: true },
              { b: 24, u: 0, l: 5, up: false },
              { b: 18, u: 0, l: 4, up: false },
            ].map(({ b, u, l, up, hi }, i) => {
              const color = up ? C.dataUp : C.dataDown;
              return (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div style={{ width: 3, height: u, background: color }} />
                  <div style={{ width: hi ? 32 : 28, height: b, background: color, borderRadius: 3, boxShadow: hi ? `0 0 12px ${color}` : 'none' }} />
                  <div style={{ width: 3, height: l, background: color }} />
                </div>
              );
            })}
            <div style={{ opacity: p2Warn, marginLeft: 8, fontSize: 20, color: '#FF6B6B', fontWeight: 700 }}>← 윗꼬리</div>
          </div>
        </div>

        <div style={{ opacity: p2Warn, fontSize: 28, color: '#FF9800', fontWeight: 600, textAlign: 'center' }}>
          ⚠️ 고점에 물리면 긴 시간 필요 — 변동성 주의
        </div>
      </div>

      {/* ═══ PHASE 3 — 대형주 소수점 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph3, gap: 24 }}>
        <div style={{ fontSize: 120, lineHeight: 1, opacity: p3Icon, filter: GLOW.mid.filter }}>🏢</div>
        <div style={{ opacity: p3TitleOp, fontSize: 44, color: C.textSub, fontWeight: 700 }}>저리대출 받은 대형주는요?</div>

        <div style={{ display: 'flex', gap: 40, opacity: p3L1Op, transform: `translateY(${p3L1Y}px)` }}>
          {[{ icon: '🔵', name: '삼성전자' }, { icon: '🟢', name: '네이버' }].map(({ icon, name }) => (
            <div key={name} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid #222', borderRadius: 20, padding: '28px 56px', textAlign: 'center' }}>
              <div style={{ fontSize: 64 }}>{icon}</div>
              <div style={{ fontSize: 36, fontWeight: 900, color: C.textPrimary, marginTop: 10 }}>{name}</div>
            </div>
          ))}
        </div>

        <div style={{ opacity: p3BigOp, transform: `scale(${p3BigSc})`, textAlign: 'center' }}>
          <div style={{ fontSize: 28, color: C.textSub, marginBottom: 8 }}>이 회사들한테 대출 2,000억은</div>
          <div style={{ fontSize: 96, fontWeight: 900, color: '#555' }}>매출에서 <span style={{ color: '#FF6B6B' }}>소수점</span></div>
          <div style={{ fontSize: 28, color: C.textSub, marginTop: 8 }}>주가가 움직일 이유가 없습니다</div>
        </div>
      </div>

      {/* ═══ PHASE 4 — 호재 조건 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: ph4 }}>
        <div style={{ transform: `scale(${p4BoxSc * p4Pulse})`, background: 'rgba(0,255,208,0.06)', border: `2.5px solid ${C.main}`, borderRadius: 28, padding: '60px 80px', textAlign: 'center', boxShadow: GLOW.strong.box, maxWidth: 1000 }}>
          <div style={{ fontSize: 36, color: C.textSub, marginBottom: 24, fontWeight: 600 }}>저리대출이 진짜 호재가 되는 조건</div>
          <div style={{ fontSize: 56, fontWeight: 900, color: C.main, textShadow: GLOW.strong.text, lineHeight: 1.45, opacity: p4TextOp }}>
            "이 대출 없었으면<br />못 했을 사업을<br />이제 할 수 있게 됐다"
          </div>
        </div>
      </div>

      {/* ═══ PHASE 5 — 엘앤에프 1군 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph5, padding: '0 80px', gap: 12 }}>
        <div style={{ opacity: p5BadgeOp, display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
          <div style={{ background: C.dataUp, color: '#fff', fontSize: 20, fontWeight: 900, padding: '8px 24px', borderRadius: 30 }}>🔴 1군</div>
          <div style={{ fontSize: 24, color: C.textSub }}>직접 확정 + 인과관계 명확</div>
        </div>

        <div style={{ opacity: p5Icon, fontSize: 80, lineHeight: 1 }}>🏭</div>

        <div style={{ opacity: p5L1Op, transform: `translateY(${p5L1Y}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 96, fontWeight: 900, color: C.main, textShadow: `0 0 ${p5GSz}px rgba(0,255,208,0.5)`, lineHeight: 1 }}>엘앤에프</div>
          <div style={{ fontSize: 28, color: C.textSub, marginTop: 4 }}>코스피 · 이차전지 양극재</div>
        </div>

        <div style={{ display: 'flex', gap: 24, marginTop: 4 }}>
          {[
            { o: p5N1Op, sc: p5N1Sc, v: '2,200억', l: '저리대출', icon: '💰' },
            { o: p5N2Op, sc: p5N2Sc, v: '12년',    l: '장기 대출', icon: '📅' },
            { o: p5N3Op, sc: p5N3Sc, v: '5/28',    l: '공식 승인', icon: '✅' },
          ].map(({ o, sc, v, l, icon }) => (
            <div key={l} style={{ opacity: o, transform: `scale(${sc})`, background: 'rgba(0,255,208,0.07)', border: `1.5px solid ${C.borderSub}`, borderRadius: 16, padding: '20px 36px', textAlign: 'center' }}>
              <div style={{ fontSize: 36 }}>{icon}</div>
              <div style={{ fontSize: 48, fontWeight: 900, color: C.main, marginTop: 6, textShadow: GLOW.mid.text }}>{v}</div>
              <div style={{ fontSize: 20, color: C.textSub, marginTop: 4 }}>{l}</div>
            </div>
          ))}
        </div>

        <div style={{ opacity: p5LFPOp, background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: '16px 28px', textAlign: 'center' }}>
          <div style={{ fontSize: 24, color: C.textPrimary, fontWeight: 700 }}>국내 최초 LFP 양극재 공장 · 중국 장악 시장 · 이 대출 없으면 못 하는 사업</div>
        </div>

        <div style={{ opacity: p5ChartOp, display: 'flex', gap: 20 }}>
          {['📊 60일선 쌍바닥 지지', '🎯 20일선 저항 돌파 주목', '📈 5/27 +13% 유지'].map(t => (
            <div key={t} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid #222', borderRadius: 10, padding: '10px 20px', fontSize: 18, color: C.textSub }}>{t}</div>
          ))}
        </div>
      </div>

      {/* ═══ PHASE 6 — 에코프로비엠 2군 ═══ */}
      <div style={{ position: 'absolute', inset: 0, bottom: '16%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: ph6, padding: '0 80px', gap: 14 }}>
        <div style={{ opacity: p6BadgeOp, display: 'flex', alignItems: 'center', gap: 16, marginBottom: 4 }}>
          <div style={{ background: '#FF9800', color: '#fff', fontSize: 20, fontWeight: 900, padding: '8px 24px', borderRadius: 30 }}>🟠 2군</div>
          <div style={{ fontSize: 24, color: C.textSub }}>자금 유입 최전선 — 개별 확정 아님</div>
        </div>

        <div style={{ opacity: p6Icon, fontSize: 80, lineHeight: 1 }}>🔋</div>

        <div style={{ opacity: p6L1Op, transform: `translateY(${p6L1Y}px)`, textAlign: 'center' }}>
          <div style={{ fontSize: 96, fontWeight: 900, color: '#FF9800', lineHeight: 1, textShadow: `0 0 ${interpolate(p6Pulse, [0, 1], [8, 24])}px rgba(255,152,0,0.5)` }}>에코프로비엠</div>
          <div style={{ fontSize: 28, color: C.textSub, marginTop: 4 }}>코스닥 시총 1위</div>
        </div>

        <div style={{ opacity: p6ChipOp, display: 'flex', gap: 18, flexWrap: 'wrap', justifyContent: 'center' }}>
          {[
            { t: '5/22 완판날 +11%', c: C.dataUp },
            { t: '현재도 유지 중', c: C.main },
            { t: '코스닥 자금 최전선', c: '#FF9800' },
          ].map(({ t, c }) => (
            <div key={t} style={{ background: `${c}20`, border: `1.5px solid ${c}55`, borderRadius: 24, padding: '10px 24px', fontSize: 22, color: c, fontWeight: 700 }}>{t}</div>
          ))}
        </div>

        <div style={{ opacity: p6ArrowOp, display: 'flex', alignItems: 'center', gap: 16, fontSize: 26 }}>
          {['정배열 완성', '→', '장대양봉', '→', '신고가 가능'].map((t, i) => (
            <div key={i} style={{ color: i % 2 === 0 ? C.textPrimary : C.main, fontWeight: i % 2 === 0 ? 700 : 400 }}>{t}</div>
          ))}
        </div>
      </div>

      {/* 자막 바 */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[
          { o: cap1, text: <>총알 장전 상태 — <span style={{ color: C.main }}>6월 15일 실제 집행 시작</span></> },
          { o: cap2, text: <>비상장 연결고리 — <span style={{ color: '#FF9800' }}>고점 물리면 긴 시간 필요</span></> },
          { o: cap3, text: <>대형주 저리대출은 <span style={{ color: '#FF6B6B' }}>소수점도 안 됩니다</span></> },
          { o: cap4, text: <><span style={{ color: C.main }}>"이 대출 없었으면 못 했을 사업"</span></> },
          { o: cap5, text: <>엘앤에프 — <span style={{ color: C.main }}>직접 확정 · 국내 최초 LFP 공장</span></> },
          { o: cap6, text: <>에코프로비엠 — <span style={{ color: '#FF9800' }}>코스닥 자금 유입 최전선</span></> },
        ].map(({ o, text }, i) => (
          <div key={i} style={{ position: 'absolute', color: C.textPrimary, fontSize: 36, fontWeight: 700, textAlign: 'center', paddingInline: 80, opacity: o, textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>{text}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
