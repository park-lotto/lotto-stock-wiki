// YT_AI_S04_데모 — 씬4 데모 (7200프레임 / 240초)
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

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
  { s: 0,   e: 150, text: '자, 그럼 지금부터 STOCK BRAIN이 매일 새벽 4시에 어떻게 여러분의 아침을 바꿔놓는지 직접 보여드리겠습니다.' },
  { s: 210, e: 390, text: '보시는 화면이 바로 새벽 4시에 자동으로 생성된 \'오늘의 핵심 브리핑\' 최종 요약본입니다.' },
  { s: 390, e: 540, text: '뉴스, 텔레그램, 증권사 리포트, 그리고 수급 데이터까지.' },
  { s: 600, e: 840, text: '수백 개의 파편적인 정보들이 AI에 의해 통합 분석되어, 이렇게 단 한 장의 대시보드로 압축됩니다.' },
  { s: 840, e: 1020, text: '여기 보시면 \'오늘의 주요 섹터\'와 \'핵심 종목\'이 한눈에 들어오시죠?' },
  { s: 1020, e: 1260, text: '예를 들어, \'유리기판\' 섹터가 왜 오늘 주목받아야 하는지 궁금하시다면,' },
  { s: 1320, e: 1500, text: '이렇게 \'유리기판\' 섹터를 딸깍 한 번 클릭해 보세요.' },
  { s: 1500, e: 1860, text: '그러면 AI가 분석한 \'유리기판\' 관련 핵심 뉴스 기사, 텔레그램 메시지, 그리고 증권사 리포트 발췌 내용이 한눈에 팝업됩니다.' },
  { s: 1860, e: 2220, text: '어떤 정보들을 AI가 종합해서 이 섹터를 추천했는지, 그 원천 데이터를 크로스 레퍼런싱할 수 있는 것이죠.' },
  { s: 2280, e: 2520, text: '일일이 기사를 찾아볼 필요 없이, AI가 이미 다 핵심만 뽑아준 겁니다.' },
  { s: 2520, e: 2880, text: '다음으로, 제가 가장 중요하게 생각하는 기능 중 하나인 \'수급 빈집 추적\' 기능을 보여드리겠습니다.' },
  { s: 2880, e: 3180, text: '여러분, 주식 시장에서 수급은 곧 주가의 방향을 결정하는 핵심 요소라는 것을 잘 아실 겁니다.' },
  { s: 3180, e: 3660, text: '하지만 개인 투자자가 외국인이나 기관의 실시간 수급을 파악하고, 특정 종목의 \'빈집\'을 찾아내기란 사실상 불가능에 가깝죠.' },
  { s: 3720, e: 3900, text: '하지만 STOCK BRAIN은 다릅니다.' },
  { s: 3900, e: 4140, text: '여기 \'수급 빈집 추적\' 필터를 딸깍 적용하면,' },
  { s: 4200, e: 4560, text: '보시는 것처럼 AI가 자체 알고리즘으로 포착한 특정 조건을 만족하는 종목들이 실시간으로 하이라이트됩니다.' },
  { s: 4560, e: 4980, text: '이 종목들은 곧 외국인이나 기관의 매수세가 강하게 유입될 가능성이 높은, 소위 \'수급 빈집\' 상태인 종목들입니다.' },
  { s: 5040, e: 5460, text: '관련 수급 데이터는 이렇게 그래프로 시각화되어, 외국인과 기관의 순매수 동향을 직관적으로 확인할 수 있습니다.' },
  { s: 5520, e: 5940, text: '단순히 종목을 나열하는 것이 아니라, 왜 이 종목이 \'수급 빈집\'인지, 그 근거까지 명확하게 보여주는 것이죠.' },
  { s: 6000, e: 6480, text: '이처럼 STOCK BRAIN은 단순 정보 요약을 넘어, AI의 심층 분석으로 여러분이 놓치기 쉬운 \'숨겨진 기회\'까지 찾아드립니다.' },
  { s: 6480, e: 6900, text: '매일 아침 5분, 이 딸깍 한 번으로 여러분은 이미 시장의 선두에 서게 됩니다.' },
];

function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// ── 강조 키워드 ──────────────────────────────────────────────────
const KEYWORDS = {
  STOCK_BRAIN: { text: 'STOCK BRAIN', color: C.main },
  DAWN_4AM: { text: '새벽 4시', color: C.main },
  BRIEFING: { text: '오늘의 핵심 브리핑', color: C.main },
  INTEGRATED_ANALYSIS: { text: '통합 분석', color: C.main },
  DASHBOARD: { text: '한 장의 대시보드', color: C.main },
  MAIN_SECTOR: { text: '오늘의 주요 섹터', color: C.main },
  CORE_STOCK: { text: '핵심 종목', color: C.main },
  GLASS_SUBSTRATE: { text: '유리기판', color: C.main },
  CLICK: { text: '딸깍', color: C.main },
  CROSS_REFERENCE: { text: '크로스 레퍼런싱', color: C.main },
  SUPPLY_EMPTY_HOUSE_TRACKING: { text: '수급 빈집 추적', color: C.main },
  SUPPLY: { text: '수급', color: C.main },
  SUPPLY_EMPTY_HOUSE: { text: '수급 빈집', color: C.main },
  HIDDEN_OPPORTUNITY: { text: '숨겨진 기회', color: C.main },
  CLICK_ONCE: { text: '딸깍 한 번', color: C.main },
};

// ── 컴포넌트 ─────────────────────────────────────────────────────
export const YT_AI_S04_데모: React.FC = () => {
  const f = useCurrentFrame();
  const sub = getSub(f);

  const bgGlow  = Math.sin(f * 0.04) * 0.028 + 0.05;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 30]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`;

  // ── 애니메이션 값 ──────────────────────────────────────────────
  // Phase 1: Tablet & Dashboard Intro (0-600f)
  const tabletScale = ip(f, 0, 30, 0.5, 1, Easing.out(Easing.back));
  const tabletOpacity = ip(f, 0, 30, 0, 1);
  const dashboardIntroY = ip(f, 0, 30, 200, 0, Easing.out(Easing.cubic));
  const dawn4amOpacity = ip(f, 210, 240, 0, 1);
  const dawn4amGlow = `0 0 ${ip(f, 210, 390, 10, 30, Easing.inOut(Easing.sin))}px ${C.main}`;

  // Phase 2: Yurigipan Click & Pop-up (600-2520f)
  const yurigipanHighlightOp = ip(f, 1020, 1050, 0, 1);
  const yurigipanClickScale = ip(f, 1320, 1335, 1, 0.9, Easing.out(Easing.cubic));
  const yurigipanClickScaleBack = ip(f, 1335, 1350, 0.9, 1, Easing.out(Easing.cubic));
  const popupOpacity = ip(f, 1350, 1400, 0, 1);
  const popupScale = ip(f, 1350, 1400, 0.8, 1, Easing.out(Easing.back));
  const popupFadeOut = ip(f, 2280, 2330, 1, 0);

  // Phase 3: Filter Intro (2520-4140f)
  const filterHighlightOp = ip(f, 2520, 2550, 0, 1);
  const filterClickScale = ip(f, 3900, 3915, 1, 0.9, Easing.out(Easing.cubic));
  const filterClickScaleBack = ip(f, 3915, 3930, 0.9, 1, Easing.out(Easing.cubic));

  // Phase 4: Filtered Stocks & Graphs (4140-6000f)
  const filteredDashboardOpacity = ip(f, 3930, 3980, 0, 1); // Transition to filtered dashboard
  const stockHighlightPulse = Math.sin(f * 0.1) * 0.5 + 0.5;
  const stockHighlightGlow = `0 0 ${interpolate(stockHighlightPulse, [0, 1], [5, 20])}px ${C.red}`;
  const graphOpacity = ip(f, 5040, 5090, 0, 1);

  // Phase 5: Final Emphasis (6000-7200f)
  const ddalggakScale = ip(f, 6480, 6580, 0.5, 1.2, Easing.out(Easing.back));
  const ddalggakOpacity = ip(f, 6480, 6580, 0, 1);
  const ddalggakFadeOut = ip(f, 6780, 6880, 1, 0);

  // Dashboard visibility logic
  const initialDashboardVisibility = ip(f, 0, 30, 0, 1) * (1 - ip(f, 3900, 3950, 0, 1)); // Visible at start, fades out for filtered
  const finalDashboardVisibility = ip(f, 5950, 6000, 0, 1); // Fades in for final phase
  const mainDashboardOpacity = Math.max(initialDashboardVisibility, finalDashboardVisibility); // Ensures it's visible at start and end

  // ── 렌더링 ─────────────────────────────────────────────────────
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, overflow: 'hidden', fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/yt_ai_s04_데모.m4a')} />

      {/* Background glow */}
      <div style={{
        position: 'absolute',
        inset: -100,
        background: `radial-gradient(circle at center, rgba(0,255,208,${bgGlow}) 0%, transparent 50%)`,
        opacity: 0.5,
      }} />

      {/* Tablet/Dashboard container */}
      <div style={{
        position: 'absolute',
        width: '80%', height: '70%',
        left: '10%', top: `calc(15% + ${dashboardIntroY}px)`,
        transform: `scale(${tabletScale})`,
        opacity: tabletOpacity,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#1a1f2c', // Darker background for the tablet frame
        borderRadius: 20,
        boxShadow: dynGlow,
        overflow: 'hidden',
      }}>
        {/* Dashboard Image - Initial state */}
        <img
          src={staticFile('img/dashboard_initial.png')} // Placeholder image
          alt="Dashboard"
          style={{
            width: '98%', height: '98%', objectFit: 'contain',
            opacity: mainDashboardOpacity,
          }}
        />

        {/* Filtered Dashboard Image */}
        <img
          src={staticFile('img/dashboard_filtered.png')} // Placeholder image for filtered state
          alt="Filtered Dashboard"
          style={{
            position: 'absolute', top: '1%', left: '1%',
            width: '98%', height: '98%', objectFit: 'contain',
            opacity: filteredDashboardOpacity * ip(f, 5940, 5990, 1, 0), // Fades in after filter click, fades out before final phase
          }}
        />

        {/* "새벽 4시 자동 생성" text */}
        <div style={{
          position: 'absolute',
          top: '5%', left: '50%',
          transform: 'translateX(-50%)',
          fontFamily: `"Consolas","Menlo",monospace`,
          fontSize: 36,
          fontWeight: 700,
          color: C.main,
          opacity: dawn4amOpacity * mainDashboardOpacity,
          textShadow: dawn4amGlow,
        }}>
          새벽 4시 자동 생성
        </div>

        {/* Phase 2: Yurigipan Highlight & Pop-up */}
        {/* '유리기판' 섹터 하이라이트 (conceptual div over dashboard image) */}
        <div style={{
          position: 'absolute',
          top: '30%', left: '20%', // Example position for '유리기판' section
          width: '20%', height: '10%',
          background: C.main,
          opacity: yurigipanHighlightOp * (1 - popupOpacity) * (1 - popupFadeOut) * mainDashboardOpacity,
          borderRadius: 8,
          boxShadow: `0 0 15px ${C.main}`,
          transform: `scale(${yurigipanClickScale * yurigipanClickScaleBack})`,
        }} />

        {/* Pop-up for '유리기판' details */}
        <div style={{
          position: 'absolute',
          width: '70%', height: '80%',
          background: '#1f2430',
          borderRadius: 15,
          boxShadow: dynGlow,
          opacity: popupOpacity * (1 - popupFadeOut),
          transform: `scale(${popupScale})`,
          display: 'flex', flexDirection: 'column',
          padding: 30,
          color: '#FFF',
          fontSize: 28,
          lineHeight: 1.4,
          justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 36, fontWeight: 700, color: C.main, marginBottom: 20 }}>
            {KEYWORDS.GLASS_SUBSTRATE.text} 관련 핵심 브리핑
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <p><strong>뉴스:</strong> "유리기판, 차세대 반도체 기판으로 부상... 삼성전기 투자 확대"</p>
            <p><strong>텔레그램:</strong> "[속보] 유리기판 관련주, 장 초반 강세... 기관 매수세 유입"</p>
            <p><strong>리포트:</strong> "OO증권: 유리기판, 2025년 시장 5배 성장 전망... 핵심 기업 분석"</p>
            <p style={{marginTop: 20, color: C.amber}}>
              AI 분석: 유리기판은 고성능 반도체 수요 증가와 함께 성장 잠재력이 높은 섹터입니다.
              주요 기업들의 투자 확대와 기관 매수세가 포착되어 단기 및 중장기적 관심이 필요합니다.
            </p>
          </div>
          {/* Cross-referencing visual cue */}
          <div style={{
            position: 'absolute', bottom: 20, right: 30,
            fontSize: 24, color: '#9ca3af',
            opacity: ip(f, 1860, 1900, 0, 1) * ip(f, 2220, 2250, 1, 0),
          }}>
            {KEYWORDS.CROSS_REFERENCE.text}
          </div>
        </div>

        {/* '수급 빈집 추적' 필터 버튼 하이라이트 (conceptual div over dashboard image) */}
        <div style={{
          position: 'absolute',
          top: '10%', right: '10%', // Example position for filter button
          width: '15%', height: '7%',
          background: C.main,
          opacity: filterHighlightOp * mainDashboardOpacity * (1 - filteredDashboardOpacity),
          borderRadius: 8,
          boxShadow: `0 0 15px ${C.main}`,
          transform: `scale(${filterClickScale * filterClickScaleBack})`,
        }} />

        {/* Highlighted Stocks (conceptual divs over filtered dashboard image) */}
        {[
          { top: '30%', left: '15%' },
          { top: '45%', left: '15%' },
          { top: '60%', left: '15%' },
        ].map((pos, i) => (
          <div key={i} style={{
            position: 'absolute',
            ...pos,
            width: '25%', height: '10%',
            background: `rgba(255,71,87,0.2)`, // Red tint for highlight
            borderRadius: 8,
            boxShadow: stockHighlightGlow,
            opacity: ip(f, 4200 + i * 30, 4230 + i * 30, 0, 1) * filteredDashboardOpacity,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#FFF', fontSize: 24, fontWeight: 700,
          }}>
            종목명 {i+1}
            {/* Graph Visualization */}
            <div style={{
              position: 'absolute',
              right: '-120px', // Position next to stock name
              width: 100, height: 60,
              background: 'linear-gradient(to top, #FF4757, #FFA502)', // Example graph
              opacity: graphOpacity * filteredDashboardOpacity,
              borderRadius: 5,
            }} />
          </div>
        ))}
      </div>

      {/* Phase 5: Final Emphasis */}
      {/* "딸깍" text animation */}
      <div style={{
        position: 'absolute',
        top: '50%', left: '50%',
        transform: `translate(-50%, -50%) scale(${ddalggakScale})`,
        opacity: ddalggakOpacity * ddalggakFadeOut,
        fontFamily: FONT,
        fontSize: 120,
        fontWeight: 900,
        color: C.main,
        textShadow: dynGlow,
        zIndex: 10,
      }}>
        {KEYWORDS.CLICK.text}
      </div>

      {/* Subtitle bar */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:'16%',
        display:'flex',alignItems:'center',justifyContent:'center',paddingInline:80,
        background:'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)'}}>
        {sub&&<div style={{color:'#FFF',fontSize:40,fontWeight:700,textAlign:'center',
          opacity:sub.op,textShadow:'0 2px 8px rgba(0,0,0,0.9)'}}>{sub.text}</div>}
      </div>
    </AbsoluteFill>
  );
};