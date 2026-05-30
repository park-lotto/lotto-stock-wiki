// AG_S04_2_Collect — 씬4-2 수집 직원 v3 (1690프레임 / 56.3초)
// 구간별 완전히 다른 비주얼 (레이더→카드→뉴스→유튜브→미국장→폴더→클락→클라이맥스)
// 오디오: voice/ag_s4-2.m4a (기존 녹음 그대로)
//
// Whisper 싱크:
// [01] f0000~0167  "자료 수집 직원. 이 친구는 24시간 대기 중입니다."
// [02] f0181~0356  "증권사 리포트, 텔레그램 채널 내용 — 올라오면 바로 받아요."
// [03] f0376~0520  "키워드 설정 넣으면 네이버 뉴스에서도 바로 가져와요."
// [04] f0537~0658  "유튜브 채널 인사이트도 뜨자마자 바로 가져와요."
// [05] f0677~0776  "제가 자는 동안엔 미국장을 추적합니다."
// [06] f0776~1008  "섹터 움직임 추적하고 미국 실적 발표 나오면 바로 긁어와요."
// [07] f1008~1120  "이게 제 서버 지식베이스에 계속 쌓입니다."
// [08] f1149~1328  "낮 2시에도, 밤 11시에도, 새벽 1시에도 — 다 찍혀있어요."
// [09] f1354~1400  "제가 자는 동안만이 아닙니다."
// [10] f1426~1611  "밥 먹고 운동하는 시간에도 새 정보 들어오면 바로 처리해요."
// [11] f1611~1660  "끊기는 게 없어요."

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

const SUBS = [
  { s: 0,    e: 167,  text: '자료 수집 직원. 이 친구는 24시간 대기 중입니다.' },
  { s: 181,  e: 356,  text: '증권사 리포트, 텔레그램 채널 내용 — 올라오면 바로 받아요.' },
  { s: 376,  e: 520,  text: '키워드 설정 넣으면 네이버 뉴스에서도 바로 가져와요.' },
  { s: 537,  e: 658,  text: '유튜브 채널 인사이트도 뜨자마자 바로 가져와요.' },
  { s: 677,  e: 776,  text: '제가 자는 동안엔 미국장을 추적합니다.' },
  { s: 776,  e: 1008, text: '섹터 움직임 추적하고 미국 실적 발표 나오면 바로 긁어와요.' },
  { s: 1008, e: 1120, text: '이게 제 서버 지식베이스에 계속 쌓입니다.' },
  { s: 1149, e: 1328, text: '낮 2시에도, 밤 11시에도, 새벽 1시에도 — 다 찍혀있어요.' },
  { s: 1354, e: 1400, text: '제가 자는 동안만이 아닙니다.' },
  { s: 1426, e: 1611, text: '밥 먹고 운동하는 시간에도 새 정보 들어오면 바로 처리해요.' },
  { s: 1611, e: 1660, text: '끊기는 게 없어요.' },
];
function getSub(f: number) {
  const seg = SUBS.find(s => f >= s.s && f <= s.e);
  if (!seg) return null;
  return { text: seg.text, op: Math.min((f - seg.s) / 8, 1, (seg.e - f) / 8) };
}

// ── 레이더 sector path 헬퍼 ──────────────────────────────────────────
function sectorPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = (startDeg * Math.PI) / 180;
  const e = (endDeg   * Math.PI) / 180;
  const x1 = cx + r * Math.cos(s); const y1 = cy + r * Math.sin(s);
  const x2 = cx + r * Math.cos(e); const y2 = cy + r * Math.sin(e);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M${cx},${cy} L${x1},${y1} A${r},${r},0,${large},1,${x2},${y2} Z`;
}

// ── 미국장 차트 데이터 (SOX 가상 곡선) ────────────────────────────
const CHART_PTS = [
  [0, 520], [60, 480], [130, 510], [200, 440], [270, 460],
  [340, 400], [410, 420], [480, 360], [540, 380], [610, 320],
  [680, 340], [740, 280], [800, 300],
] as [number, number][];


// ── 24시간 클락 수집 시간대 ────────────────────────────────────────
// 시간(0~23)을 각도(degree)로: 0시 = 위(-90도) 기준, 시계방향
function hourToDeg(h: number) { return (h / 24) * 360 - 90; }
const COLLECT_TIMES = [
  { h: 14.4, col: '#6b7280', label: '14:23' },
  { h: 15.1, col: '#6b7280', label: '15:04' },
  { h: 15.7, col: '#6b7280', label: '15:41' },
  { h: 16.2, col: '#6b7280', label: '16:10' },
  { h: 23.5, col: '#FFA502', label: '23:30' },
  { h: 1.2,  col: C.main,   label: '01:14' },
  { h: 3.4,  col: C.main,   label: '03:22' },
  { h: 5.2,  col: C.main,   label: '05:11' },
];

export const AG_S04_2_Collect: React.FC = () => {
  const f   = useCurrentFrame();
  const sub = getSub(f);

  const bgGlow  = Math.sin(f * 0.04) * 0.025 + 0.04;
  const pulse   = Math.sin(f * 0.07) * 0.5 + 0.5;
  const gSz     = interpolate(pulse, [0, 1], [10, 28]);
  const dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz * 2}px rgba(0,255,208,0.5)`;
  const livePulse = Math.sin(f * 0.18) > 0;

  // ── Phase 구분 opacity 헬퍼 ────────────────────────────────────
  const fadeInOut = (inA: number, inB: number, outA: number, outB: number) =>
    ip(f, inA, inB) * (1 - ip(f, outA, outB));

  // ========== PHASE 1: 레이더 (f0~175) ==========================
  const ph1Op = fadeInOut(0, 18, 158, 178);

  // 레이더 sweep 각도 (초당 ~72도 = 0.4회전/sec @ 30fps)
  const sweepDeg = (f * 2.4) % 360;

  // ========== PHASE 2: 리포트 + 텔레그램 (f181~360) =============
  const ph2Op = fadeInOut(181, 205, 345, 365);

  const REPORTS = [
    { title: '삼성전기 리포트',   sub2: 'TP 상향 22만→27만원',    icon: '📄', f: 181 },
    { title: '한화에어로 리포트', sub2: '수주잔고 사상 최고',       icon: '📄', f: 228 },
    { title: 'HLB 투자정보',     sub2: 'PDUFA D-54 임박',         icon: '📄', f: 275 },
  ];
  const TG_MSGS = [
    { text: '삼성전기 어닝서프 예상 👀', t: '14:23', f: 260 },
    { text: 'SOX 어젯밤 +2.3% 마감',     t: '09:05', f: 298 },
    { text: 'HLB FDA 일정 확정 소식',     t: '15:04', f: 336 },
  ];

  // ========== PHASE 3: 뉴스 ticker (f376~525) ===================
  const ph3Op = fadeInOut(376, 400, 508, 528);

  // ticker 이동: 오른쪽 → 왼쪽
  const tickerX = interpolate(f, [376, 900], [1920, -2400], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.linear,
  });
  const NEWS_ITEMS = [
    '🔴 HLB 리보세라닙 FDA 승인 임박  ',
    '📈 반도체 수출 4월 +18.2% YoY  ',
    '💊 한미약품 GLP-1 美진출 검토  ',
    '🇺🇸 나스닥 3연속 상승  ',
    '⚡ 전력기기 수주 2분기 최고치  ',
  ];

  // 키워드 감지 하이라이트 (f450~525)
  const detectOp    = ip(f, 450, 480);
  const detectScale = interpolate(f, [450, 480], [0.4, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.9)),
  });

  // ========== PHASE 4: 유튜브 (f537~665) =======================
  const ph4Op = fadeInOut(537, 561, 648, 668);

  const YT_INSIGHTS = [
    { text: '실적 발표 전 수급 분리 확인', f: 575 },
    { text: '섹터 주도주 체크포인트 3가지', f: 612 },
    { text: '탑픽 판단 8가지 기준',         f: 645 },
  ];

  // 진행바 (f537~660)
  const ytProgress = ip(f, 537, 660);

  // ========== PHASE 5-6: 미국장 (f677~1012) ====================
  const ph56Op = fadeInOut(677, 700, 995, 1015);

  // 알림 팝업들
  const ALERTS = [
    { msg: '나스닥 정규장 오픈', sub2: '23:30 KST',     col: '#FFA502', f: 720  },
    { msg: 'AMD Q1 EPS 서프라이즈', sub2: '$0.96 예상↑', col: '#FF4757', f: 820  },
    { msg: '관세청 반도체 수출 갱신', sub2: '+18.2% YoY',col: C.main,    f: 940  },
  ];

  // ========== PHASE 7: 폴더 누적 (f1008~1128) ==================
  const ph7Op = fadeInOut(1008, 1030, 1112, 1132);

  const FILES = [
    { name: '삼성전기_리포트.pdf',   icon: '📄', f: 1010, col: '#9ca3af' },
    { name: 'telegram_241023.json', icon: '📱', f: 1028, col: '#FFA502' },
    { name: 'naver_news_HLB.md',    icon: '📰', f: 1046, col: '#9ca3af' },
    { name: 'yt_insight_241023.md', icon: '▶️', f: 1064, col: '#FF4757' },
    { name: 'nasdaq_close.json',    icon: '🇺🇸', f: 1082, col: '#FFA502' },
    { name: 'export_data_0430.csv', icon: '📊', f: 1100, col: C.main    },
  ];

  // ========== PHASE 8: 24시간 클락 (f1149~1340) ================
  const ph8Op = fadeInOut(1149, 1175, 1325, 1345);

  // 수집 점 순차 등장
  const dotStart = (i: number) => 1175 + i * 22;

  // ========== PHASE 9: "자는동안만이 아닙니다" (f1354~1435) ====
  const ph9Op = fadeInOut(1354, 1380, 1418, 1438);

  const LIFESTYLE = [
    { icon: '💤', label: '자는 동안' },
    { icon: '🍚', label: '밥 먹는 동안' },
    { icon: '🏃', label: '운동하는 동안' },
  ];

  // ========== PHASE 10-11: 클라이맥스 (f1426~1690) =============
  const ph10Op = ip(f, 1426, 1460);

  // 소스 아이콘 원형 배치 등장 (f1430~1550)
  const ICONS = ['📄', '📱', '📰', '▶️', '🇺🇸', '📊'];
  const iconAngle = (i: number) => (i / ICONS.length) * 360 - 90;

  const finalOp    = ip(f, 1615, 1650);
  const finalScale = interpolate(f, [1615, 1650], [0.3, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.elastic(0.75)),
  });
  const finalPulse = finalOp > 0.95 ? 1 + Math.sin(f * 0.09) * 0.022 : 1;

  return (
    <AbsoluteFill style={{ background: '#080c14', opacity: ip(f, 0, 18), fontFamily: FONT }}>
      <Html5Audio src={staticFile('voice/ag_s4-2.m4a')} volume={1} />

      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow, pointerEvents: 'none',
      }} />

      <div style={{
        position: 'absolute', top: 28, right: 48,
        color: '#4b5563', fontSize: 16, fontWeight: 600, letterSpacing: 3, opacity: ip(f, 10, 28),
      }}>SCENE 4-2 · 수집 직원</div>

      {/* ══════════ PHASE 1: 레이더 ══════════ */}
      {ph1Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph1Op }}>

          {/* SVG 레이더 */}
          <svg style={{ position: 'absolute', inset: 0, width: 1920, height: 1080 }}>
            {/* 동심원 그리드 */}
            {[120, 220, 320, 400].map(r => (
              <circle key={r} cx={960} cy={540} r={r}
                fill="none" stroke={`rgba(0,255,208,0.08)`} strokeWidth="1" />
            ))}
            {/* 십자선 */}
            <line x1={560} y1={540} x2={1360} y2={540} stroke="rgba(0,255,208,0.06)" strokeWidth="1" />
            <line x1={960} y1={140} x2={960} y2={940} stroke="rgba(0,255,208,0.06)" strokeWidth="1" />

            {/* Sweep trail — 뒤 50도 */}
            {[40, 30, 20, 10].map((trail, i) => (
              <path key={i}
                d={sectorPath(960, 540, 400, sweepDeg - trail, sweepDeg)}
                fill={`rgba(0,255,208,${0.04 + i * 0.04})`}
              />
            ))}

            {/* Sweep 메인 라인 */}
            <line
              x1={960} y1={540}
              x2={960 + 400 * Math.cos((sweepDeg * Math.PI) / 180)}
              y2={540  + 400 * Math.sin((sweepDeg * Math.PI) / 180)}
              stroke={C.main} strokeWidth="2.5"
              style={{ filter: `drop-shadow(0 0 6px ${C.main})` }}
            />

            {/* 블립 — 신호 감지 점들 */}
            {[
              { x: 960 + 220 * Math.cos(1.2), y: 540 + 220 * Math.sin(1.2) },
              { x: 960 + 310 * Math.cos(3.8), y: 540 + 310 * Math.sin(3.8) },
              { x: 960 + 160 * Math.cos(5.1), y: 540 + 160 * Math.sin(5.1) },
            ].map((b, i) => {
              // sweep가 해당 위치를 지나고 난 직후에만 빛남
              const blipGlow = Math.max(0, 1 - ((f * 2.4 % 360 - (i * 137 % 360) + 360) % 360) / 60);
              return (
                <circle key={i} cx={b.x} cy={b.y} r={8 + blipGlow * 10}
                  fill={`rgba(0,255,208,${0.15 + blipGlow * 0.7})`}
                  style={{ filter: blipGlow > 0.3 ? `drop-shadow(0 0 ${blipGlow * 16}px ${C.main})` : undefined }}
                />
              );
            })}
          </svg>

          {/* 중앙 📡 */}
          <div style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
          }}>
            <div style={{
              fontSize: 110,
              filter: `drop-shadow(0 0 ${20 + pulse * 18}px rgba(0,255,208,0.7))`,
              transform: `scale(${1 + pulse * 0.02})`,
            }}>📡</div>
            <div style={{
              color: C.main, fontSize: 44, fontWeight: 900, letterSpacing: 6,
              textShadow: dynGlow, marginTop: 16,
            }}>24시간 대기</div>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 600, letterSpacing: 4, marginTop: 8 }}>
              ALWAYS ON · LIVE MONITORING
            </div>
          </div>

          {/* LIVE 배지 */}
          <div style={{
            position: 'absolute', bottom: 170, left: '50%', transform: 'translateX(-50%)',
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 28px', borderRadius: 20,
            background: 'rgba(255,68,68,0.1)', border: '1px solid rgba(255,68,68,0.3)',
          }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ff4444',
              opacity: livePulse ? 1 : 0.2, boxShadow: livePulse ? '0 0 8px #ff4444' : undefined }} />
            <span style={{ color: '#ff6666', fontSize: 20, fontWeight: 700, letterSpacing: 3 }}>LIVE</span>
          </div>
        </div>
      )}

      {/* ══════════ PHASE 2: 리포트 + 텔레그램 ══════════ */}
      {ph2Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph2Op }}>

          {/* 왼쪽: 리포트 카드 낙하 */}
          <div style={{
            position: 'absolute', left: 80, top: 80, width: 820,
            display: 'flex', flexDirection: 'column', gap: 20,
          }}>
            <div style={{ color: '#4b5563', fontSize: 15, fontWeight: 700, letterSpacing: 6, marginBottom: 4 }}>
              📄 증권사 리포트
            </div>
            {REPORTS.map((r, i) => {
              const rOp = ip(f, r.f, r.f + 30);
              const rTy = interpolate(f, [r.f, r.f + 30], [-60, 0], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                easing: Easing.out(Easing.back(1.4)),
              });
              return (
                <div key={i} style={{
                  opacity: rOp, transform: `translateY(${rTy}px)`,
                  padding: '22px 28px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1.5px solid rgba(255,255,255,0.09)',
                  borderRadius: 18,
                  display: 'flex', alignItems: 'center', gap: 20,
                }}>
                  <span style={{ fontSize: 44, flexShrink: 0 }}>{r.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: '#e5e7eb', fontSize: 22, fontWeight: 700 }}>{r.title}</div>
                    <div style={{ color: '#6b7280', fontSize: 16, marginTop: 4 }}>{r.sub2}</div>
                  </div>
                  <div style={{
                    padding: '4px 14px', background: `${C.main}18`,
                    border: `1px solid ${C.main}30`, borderRadius: 10,
                    color: C.main, fontSize: 14, fontWeight: 700,
                  }}>수집 ✓</div>
                </div>
              );
            })}
          </div>

          {/* 오른쪽: 텔레그램 버블 */}
          <div style={{
            position: 'absolute', right: 80, top: 80, width: 820,
          }}>
            <div style={{ color: '#4b5563', fontSize: 15, fontWeight: 700, letterSpacing: 6, marginBottom: 20 }}>
              📱 텔레그램 채널
            </div>
            {/* 채팅창 배경 */}
            <div style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 20, overflow: 'hidden',
            }}>
              {/* 타이틀 바 */}
              <div style={{
                padding: '12px 20px',
                background: 'rgba(255,255,255,0.05)',
                borderBottom: '1px solid rgba(255,255,255,0.07)',
                display: 'flex', alignItems: 'center', gap: 12,
              }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#FFA50222',
                  border: '2px solid #FFA50255', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 18 }}>📡</div>
                <div>
                  <div style={{ color: '#e5e7eb', fontSize: 16, fontWeight: 700 }}>stock_alpha</div>
                  <div style={{ color: '#4b5563', fontSize: 12 }}>주식 알파 채널</div>
                </div>
              </div>
              {/* 메시지들 */}
              <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                {TG_MSGS.map((msg, i) => {
                  const mOp = ip(f, msg.f, msg.f + 28);
                  const mTx = interpolate(f, [msg.f, msg.f + 28], [40, 0], {
                    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                    easing: Easing.out(Easing.cubic),
                  });
                  return (
                    <div key={i} style={{
                      opacity: mOp, transform: `translateX(${mTx}px)`,
                      display: 'flex', gap: 12, alignItems: 'flex-end',
                    }}>
                      <div style={{
                        padding: '12px 18px',
                        background: 'rgba(0,255,208,0.08)',
                        border: '1px solid rgba(0,255,208,0.18)',
                        borderRadius: '18px 18px 18px 4px',
                        flex: 1,
                      }}>
                        <div style={{ color: '#e5e7eb', fontSize: 18, fontWeight: 600 }}>{msg.text}</div>
                      </div>
                      <div style={{ color: '#374151', fontSize: 12, flexShrink: 0, paddingBottom: 4 }}>{msg.t}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════ PHASE 3: 뉴스 ticker ══════════ */}
      {ph3Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph3Op, overflow: 'hidden' }}>

          {/* 타이틀 */}
          <div style={{
            position: 'absolute', top: 80, left: 0, right: 0, textAlign: 'center',
            opacity: ip(f, 380, 415),
          }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 8 }}>
              📰 네이버뉴스 키워드 감지
            </div>
          </div>

          {/* 티커 2행 */}
          {[0, 1].map(row => (
            <div key={row} style={{
              position: 'absolute',
              top: 250 + row * 90,
              left: 0, right: 0,
              overflow: 'hidden', height: 70,
            }}>
              <div style={{
                display: 'flex', gap: 60, whiteSpace: 'nowrap',
                transform: `translateX(${tickerX + row * -300}px)`,
              }}>
                {[...NEWS_ITEMS, ...NEWS_ITEMS].map((item, i) => (
                  <span key={i} style={{
                    color: '#6b7280', fontSize: 26, fontWeight: 600,
                    padding: '8px 20px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    borderRadius: 12,
                  }}>{item}</span>
                ))}
              </div>
            </div>
          ))}

          {/* 키워드 감지 하이라이트 */}
          {detectOp > 0.01 && (
            <div style={{
              position: 'absolute', left: '50%', top: '50%',
              transform: `translate(-50%, -50%) scale(${detectScale})`,
              opacity: detectOp,
              textAlign: 'center',
            }}>
              <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6, marginBottom: 16 }}>
                🔍 KEYWORD DETECTED
              </div>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 16,
                padding: '20px 52px',
                background: `${C.main}12`,
                border: `2px solid ${C.main}55`,
                borderRadius: 28,
                boxShadow: `0 0 30px ${C.main}33`,
              }}>
                <span style={{ fontSize: 44, fontWeight: 900, color: C.main, textShadow: dynGlow }}>HLB</span>
                <div style={{ color: '#9ca3af', fontSize: 22, fontWeight: 600 }}>— 승인 임박 기사 1건 수집</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════ PHASE 4: 유튜브 ══════════ */}
      {ph4Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph4Op }}>
          <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', width: 900 }}>

            {/* 유튜브 플레이어 카드 */}
            <div style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1.5px solid rgba(255,255,255,0.08)',
              borderRadius: 24, overflow: 'hidden',
              opacity: ip(f, 542, 575),
            }}>
              {/* 썸네일 영역 */}
              <div style={{
                height: 200, background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative',
              }}>
                <span style={{ fontSize: 72 }}>▶️</span>
                <div style={{
                  position: 'absolute', top: 16, left: 16,
                  padding: '4px 12px', background: '#FF4757', borderRadius: 6,
                  color: '#fff', fontSize: 14, fontWeight: 700,
                }}>로또의 주식인사이트</div>
                {/* 진행바 */}
                <div style={{
                  position: 'absolute', bottom: 0, left: 0, right: 0, height: 4, background: 'rgba(255,255,255,0.15)',
                }}>
                  <div style={{
                    height: '100%', width: `${ytProgress * 100}%`,
                    background: '#FF4757', transition: 'width 0.1s',
                  }} />
                </div>
              </div>

              {/* 인사이트 추출 영역 */}
              <div style={{ padding: '20px 24px' }}>
                <div style={{ color: '#4b5563', fontSize: 14, fontWeight: 700, letterSpacing: 4, marginBottom: 14 }}>
                  💡 AI 인사이트 추출 중...
                </div>
                {YT_INSIGHTS.map((ins, i) => {
                  const iOp = ip(f, ins.f, ins.f + 30);
                  return (
                    <div key={i} style={{
                      opacity: iOp,
                      transform: `translateX(${interpolate(f, [ins.f, ins.f + 30], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })}px)`,
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: '10px 0',
                      borderBottom: i < 2 ? '1px solid rgba(255,255,255,0.06)' : undefined,
                    }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: C.main,
                        boxShadow: `0 0 6px ${C.main}`, flexShrink: 0 }} />
                      <span style={{ color: '#9ca3af', fontSize: 20, fontWeight: 600 }}>{ins.text}</span>
                      <span style={{ color: C.main, fontSize: 14, marginLeft: 'auto' }}>✓</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════ PHASE 5-6: 미국장 차트 ══════════ */}
      {ph56Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph56Op }}>

          {/* 타이틀 */}
          <div style={{
            position: 'absolute', top: 60, left: 80, opacity: ip(f, 682, 715),
          }}>
            <div style={{ color: '#4b5563', fontSize: 16, fontWeight: 700, letterSpacing: 6 }}>
              🇺🇸 미국 시장 모니터링
            </div>
            <div style={{
              color: '#FFA502', fontSize: 40, fontWeight: 900, marginTop: 6, textShadow: '0 0 16px rgba(255,165,2,0.5)',
            }}>나스닥 · SOX · SMH</div>
          </div>

          {/* 차트 SVG */}
          <svg style={{ position: 'absolute', left: 80, top: 160, width: 1100, height: 500 }}>
            {/* 그리드 */}
            {[0, 1, 2, 3, 4].map(i => (
              <line key={i} x1={0} y1={i * 100 + 50} x2={900} y2={i * 100 + 50}
                stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
            ))}
            {/* 레이블 */}
            {['SOX', 'SMH', 'QQQ'].map((label, i) => {
              const lOp = ip(f, 677 + i * 60, 720 + i * 60);
              return (
                <text key={i} x={920} y={100 + i * 120}
                  fill={i === 0 ? '#FFA502' : i === 1 ? C.main : '#9ca3af'}
                  fontSize={18} fontWeight="700" opacity={lOp}>{label}</text>
              );
            })}
            {/* 차트 라인 3개 (오프셋으로 구분) */}
            {[0, 1, 2].map(track => {
              const offset = track * 120;
              const col = track === 0 ? '#FFA502' : track === 1 ? C.main : '#9ca3af';
              const prog = ip(f, 677 + track * 30, 950 + track * 20);
              const n = Math.max(2, Math.floor(CHART_PTS.length * prog));
              const pts = CHART_PTS.slice(0, n);
              const d = pts.map((p, i) =>
                `${i === 0 ? 'M' : 'L'}${p[0]},${p[1] + offset}`
              ).join(' ');
              return (
                <path key={track} d={d} fill="none"
                  stroke={col} strokeWidth={track === 0 ? 3 : 2}
                  strokeLinejoin="round"
                  style={{ filter: `drop-shadow(0 0 ${track === 0 ? 8 : 4}px ${col}66)` }}
                />
              );
            })}
          </svg>

          {/* 알림 팝업들 */}
          <div style={{
            position: 'absolute', right: 80, top: 140,
            display: 'flex', flexDirection: 'column', gap: 18, width: 650,
          }}>
            {ALERTS.map((al, i) => {
              const alOp    = ip(f, al.f, al.f + 35);
              const alScale = interpolate(f, [al.f, al.f + 35], [0.7, 1], {
                extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                easing: Easing.out(Easing.back(1.5)),
              });
              return (
                <div key={i} style={{
                  opacity: alOp, transform: `scale(${alScale})`, transformOrigin: 'right center',
                  padding: '18px 24px',
                  background: `${al.col}12`,
                  border: `1.5px solid ${al.col}40`,
                  borderRadius: 18,
                  display: 'flex', alignItems: 'center', gap: 18,
                }}>
                  <span style={{ fontSize: 30 }}>🔔</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: al.col, fontSize: 22, fontWeight: 800, textShadow: `0 0 10px ${al.col}55` }}>
                      {al.msg}
                    </div>
                    <div style={{ color: '#6b7280', fontSize: 15, marginTop: 4 }}>{al.sub2}</div>
                  </div>
                  <div style={{ color: al.col, fontSize: 13, fontWeight: 700 }}>수집 ✓</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ══════════ PHASE 7: 폴더 누적 ══════════ */}
      {ph7Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph7Op }}>
          <div style={{
            position: 'absolute', left: '50%', top: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center', width: 900,
          }}>
            <div style={{ color: '#4b5563', fontSize: 18, fontWeight: 700, letterSpacing: 6, marginBottom: 20 }}>
              🗂️ 지식베이스 · raw/ 폴더
            </div>
            {/* 폴더 영역 */}
            <div style={{
              padding: '24px',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 20,
              display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center',
            }}>
              {FILES.map((file, i) => {
                const fOp    = ip(f, file.f, file.f + 25);
                const fScale = interpolate(f, [file.f, file.f + 25], [0.2, 1], {
                  extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                  easing: Easing.out(Easing.elastic(0.9)),
                });
                return (
                  <div key={i} style={{
                    opacity: fOp, transform: `scale(${fScale})`,
                    padding: '12px 20px',
                    background: `${file.col}10`,
                    border: `1px solid ${file.col}28`,
                    borderRadius: 14,
                    display: 'flex', alignItems: 'center', gap: 10,
                  }}>
                    <span style={{ fontSize: 22 }}>{file.icon}</span>
                    <span style={{ color: file.col, fontSize: 16, fontWeight: 600,
                      fontFamily: '"Consolas","Menlo",monospace' }}>{file.name}</span>
                  </div>
                );
              })}
            </div>
            <div style={{
              marginTop: 20, color: C.main, fontSize: 22, fontWeight: 800,
              textShadow: GLOW.weak.text, opacity: ip(f, 1100, 1120),
            }}>총 31건 / 24시간 누적</div>
          </div>
        </div>
      )}

      {/* ══════════ PHASE 8: 24시간 클락 ══════════ */}
      {ph8Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph8Op }}>
          <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -56%)' }}>

            {/* 원형 시계 */}
            <svg width={540} height={540} style={{ overflow: 'visible' }}>
              {/* 바깥 링 */}
              <circle cx={270} cy={270} r={230} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="2" />
              {/* 시간 레이블 */}
              {[0, 6, 12, 18].map(h => {
                const ang = hourToDeg(h) * Math.PI / 180;
                return (
                  <text key={h}
                    x={270 + 255 * Math.cos(ang)}
                    y={270 + 255 * Math.sin(ang) + 6}
                    textAnchor="middle" fill="#374151" fontSize={16} fontWeight="700">
                    {h < 10 ? '0' + h : '' + h}시
                  </text>
                );
              })}
              {/* 수집 시간 점들 */}
              {COLLECT_TIMES.map((ct, i) => {
                const ang = hourToDeg(ct.h) * Math.PI / 180;
                const cx  = 270 + 200 * Math.cos(ang);
                const cy  = 270 + 200 * Math.sin(ang);
                const dotOp = ip(f, dotStart(i), dotStart(i) + 25);
                const dotR  = interpolate(f, [dotStart(i), dotStart(i) + 25], [0, 12], {
                  extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
                  easing: Easing.out(Easing.elastic(0.8)),
                });
                return (
                  <g key={i} opacity={dotOp}>
                    <circle cx={cx} cy={cy} r={dotR}
                      fill={ct.col}
                      style={{ filter: `drop-shadow(0 0 8px ${ct.col})` }}
                    />
                    <text x={cx + (cx - 270) * 0.22} y={cy + (cy - 270) * 0.22 + 4}
                      textAnchor="middle" fill={ct.col} fontSize={13} fontWeight="700"
                      opacity={dotOp > 0.8 ? 1 : 0}>
                      {ct.label}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* 범례 */}
            <div style={{
              display: 'flex', gap: 24, justifyContent: 'center', marginTop: 12,
              opacity: ip(f, 1280, 1320),
            }}>
              {[
                { col: '#6b7280', label: '낮' },
                { col: '#FFA502', label: '밤' },
                { col: C.main,   label: '새벽' },
              ].map((leg, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 14, height: 14, borderRadius: '50%', background: leg.col,
                    boxShadow: `0 0 8px ${leg.col}` }} />
                  <span style={{ color: leg.col, fontSize: 18, fontWeight: 700 }}>{leg.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* "다 찍혀있어요" 하단 */}
          <div style={{
            position: 'absolute', bottom: 165, left: 0, right: 0,
            textAlign: 'center', opacity: ip(f, 1260, 1300),
          }}>
            <div style={{ fontSize: 42, fontWeight: 900, color: '#e5e7eb' }}>
              낮·밤·새벽 — <span style={{ color: C.main, textShadow: GLOW.mid.text }}>다 찍혀있어요.</span>
            </div>
          </div>
        </div>
      )}

      {/* ══════════ PHASE 9: "자는 동안만이 아닙니다" ══════════ */}
      {ph9Op > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: ph9Op,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 28,
        }}>
          <div style={{ color: '#4b5563', fontSize: 20, fontWeight: 700, letterSpacing: 8 }}>
            자는 동안만이 아닙니다
          </div>
          <div style={{ display: 'flex', gap: 32 }}>
            {LIFESTYLE.map((ls, i) => {
              const lOp = ip(f, 1360 + i * 20, 1395 + i * 20);
              return (
                <div key={i} style={{
                  opacity: lOp,
                  transform: `scale(${interpolate(f, [1360 + i * 20, 1395 + i * 20], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.5)) })})`,
                  padding: '24px 36px', borderRadius: 20,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1.5px solid rgba(255,255,255,0.1)',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 60 }}>{ls.icon}</div>
                  <div style={{ color: '#9ca3af', fontSize: 20, fontWeight: 600, marginTop: 12 }}>{ls.label}</div>
                  <div style={{ color: C.main, fontSize: 18, fontWeight: 800, marginTop: 6 }}>즉시 처리 ✓</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ══════════ PHASE 10-11: 아이콘 원형 + 클라이맥스 ══════════ */}
      {ph10Op > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, opacity: ph10Op }}>

          {/* 소스 아이콘 원형 배치 */}
          {ICONS.map((icon, i) => {
            const ang = (iconAngle(i) * Math.PI) / 180;
            const r = 340;
            const cx = 960 + r * Math.cos(ang);
            const cy = 540 + r * Math.sin(ang);
            const iOp = ip(f, 1430 + i * 20, 1470 + i * 20);
            const iGlow = `drop-shadow(0 0 ${14 + pulse * 10}px ${C.main}66)`;
            return (
              <div key={i} style={{
                position: 'absolute',
                left: cx - 40, top: cy - 40,
                width: 80, height: 80,
                opacity: iOp,
                fontSize: 52,
                textAlign: 'center', lineHeight: '80px',
                filter: iOp > 0.8 ? iGlow : undefined,
              }}>{icon}</div>
            );
          })}

          {/* 연결선 SVG */}
          <svg style={{ position: 'absolute', inset: 0, width: 1920, height: 1080, pointerEvents: 'none' }}>
            {ICONS.map((_, i) => {
              const ang  = (iconAngle(i) * Math.PI) / 180;
              const r    = 340;
              const cx   = 960 + r * Math.cos(ang);
              const cy   = 540 + r * Math.sin(ang);
              const lOp  = ip(f, 1490 + i * 15, 1530 + i * 15);
              return (
                <line key={i} x1={960} y1={540} x2={cx} y2={cy}
                  stroke={`rgba(0,255,208,${lOp * 0.25})`} strokeWidth="1.5"
                  strokeDasharray="8 6" />
              );
            })}
          </svg>
        </div>
      )}

      {/* "끊기는 게 없어요" 클라이맥스 */}
      {finalOp > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          opacity: finalOp,
        }}>
          <div style={{
            transform: `scale(${finalScale * finalPulse})`,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 50, marginBottom: 18 }}>🔄</div>
            <div style={{
              fontSize: 100, fontWeight: 900,
              color: C.main, textShadow: dynGlow,
            }}>끊기는 게 없어요.</div>
            <div style={{ color: '#4b5563', fontSize: 22, fontWeight: 600, letterSpacing: 6, marginTop: 18 }}>
              24HR · ALWAYS ON · NO GAPS
            </div>
          </div>
        </div>
      )}

      {/* 자막바 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        paddingInline: 80,
        background: 'linear-gradient(to top, rgba(8,12,20,0.92) 0%, transparent 100%)',
      }}>
        {sub && (
          <div style={{
            color: '#FFF', fontSize: 40, fontWeight: 700, textAlign: 'center',
            opacity: sub.op, textShadow: '0 2px 8px rgba(0,0,0,0.9)',
          }}>{sub.text}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};
