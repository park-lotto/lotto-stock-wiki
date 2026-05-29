// S02 — 씬2 정보 카오스 + 텔레그램 (45초 = 1350프레임)
// B1 수준 재작성: prog 페이즈 시스템 + 텔레그램 UI 정밀 재현 + 뉴스 패널
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const PHASE5 = 0.78; // prog 기준 고점 페이즈 시작

// 텔레그램 다크 색상 (B1 동일)
const TG = {
  bg:     '#0E1621',
  panel:  '#17212B',
  side:   '#0F1A24',
  text:   '#FFFFFF',
  sub:    '#7F92A1',
  accent: '#5288C1',
};

// 알림 카드 데이터 (12장)
const CARDS = [
  { ch: '반도체 인사이트', msg: 'SK하이닉스 HBM4 NVIDIA 독점 공급 확실시 — 내부 일정 6월 말 확정', time: '04:12', tag: '#반도체', warn: false },
  { ch: '뉴스속보 ⓜ',     msg: '연준 6월 기준금리 동결 확정...달러 강세 전망 지속',                time: '04:31', tag: '#매크로', warn: false },
  { ch: '조선 데일리',     msg: '한화오션 카타르 LNG선 $2.1B 신규수주 — 연간 수주 목표 72% 달성',  time: '04:45', tag: '#조선',   warn: false },
  { ch: '글로벌 시황',     msg: 'Nasdaq +0.8% · S&P500 +0.5% · NVDA +2.1% 마감',                  time: '05:02', tag: '#미장',   warn: false },
  { ch: '리포트 모음',     msg: 'NH투자증권 반도체 섹터 TP 상향 — 삼성전자 9만원',                 time: '05:14', tag: '#리포트', warn: false },
  { ch: '방산 정책',       msg: 'KAI 인도 FA-50 수출 협상 최종단계 — 계약 규모 $3.2B',             time: '05:28', tag: '#방산',   warn: false },
  { ch: 'AI 섹터',         msg: 'NVIDIA Blackwell 출하 가속 — HBM3e 수요 분기 대비 40% 급증',      time: '05:41', tag: '#AI',     warn: false },
  { ch: '2차전지',         msg: 'LG에너지솔루션 미국 ESS 프로젝트 1.2조 수주 확정',               time: '05:55', tag: '#2차전지',warn: false },
  { ch: '리딩방 ★★★',    msg: '🔥 지금 즉시 OO 담아!! 오늘 무조건 폭발 — 내가 책임짐',          time: '06:03', tag: '⚠️',      warn: true  },
  { ch: '자동차 인사이트', msg: '현대차 인도시장 점유율 역대 최고 22% — SDV 전환 가속화',          time: '06:15', tag: '#자동차', warn: false },
  { ch: '헬스케어 클럽',   msg: 'HLB 리보세라닙 FDA 심사 최종단계 — 다음 주 승인 결정',           time: '06:28', tag: '#바이오', warn: false },
  { ch: '리딩방 VIP 💎',  msg: 'XXX 3일 내 20-30% 확실 — 지금 담지 않으면 후회함',              time: '07:01', tag: '⚠️',      warn: true  },
];

// 카드 등장 prog 타이밍 (가속 효과)
const CARD_PROGS = [
  0.030, 0.065, 0.100,   // Row 0 (조용히)
  0.148, 0.176, 0.205,   // Row 1 (보통)
  0.290, 0.310, 0.330,   // Row 2 (빠르게)
  0.410, 0.422, 0.434,   // Row 3 (폭발)
];

export const S02_Chaos = () => {
  const f = useCurrentFrame();

  const fadeIn = interpolate(f, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  const prog   = interpolate(f, [10, 1310], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // 숨쉬는 배경 글로우
  const bgGlow = Math.sin(f * 0.035) * 0.018 + 0.028;

  // 카드 전체 fade out (Phase 5)
  const cardsFade = interpolate(prog, [PHASE5, PHASE5 + 0.05], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });

  // 알림 카운터 (가속)
  const counter = Math.floor(interpolate(prog, [0.02, PHASE5], [0, 473], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad),
  }));

  // 채널 수 라벨
  const chLabelOp = interpolate(prog, [0.18, 0.26], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 절정 직전 텍스트
  const p4text = interpolate(prog, [0.65, 0.72], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Phase 5 텍스트
  const p5base   = interpolate(prog, [PHASE5 + 0.02, PHASE5 + 0.06], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const p5peak   = interpolate(prog, [PHASE5 + 0.08, PHASE5 + 0.13], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const p5q      = interpolate(prog, [PHASE5 + 0.18, PHASE5 + 0.23], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 뉴스 패널 등장
  const newsPanelOp = interpolate(prog, [0.10, 0.20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 뉴스 스크롤 (prog 0→PHASE5 동안 상단으로 서서히 이동)
  const newsScroll = interpolate(prog, [0.10, PHASE5], [0, -380], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.linear),
  });

  return (
    <AbsoluteFill style={{ background: '#000', opacity: fadeIn, fontFamily: FONT }}>

      {/* 숨쉬는 배경 글로우 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,255,208,1) 0%, transparent 65%)',
        opacity: bgGlow * cardsFade,
      }} />

      {/* 스캔라인 */}
      <AbsoluteFill style={{
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,255,208,0.008) 3px, rgba(0,255,208,0.008) 4px)',
        pointerEvents: 'none',
      }} />

      {/* ── 우측 뉴스 패널 (실사) ── */}
      <div style={{
        position: 'absolute',
        right: 30, top: 70, bottom: 70,
        width: 430,
        background: TG.bg,
        borderRadius: 14,
        border: `1px solid rgba(82,136,193,0.2)`,
        overflow: 'hidden',
        opacity: newsPanelOp * cardsFade,
        boxShadow: '0 0 30px rgba(0,0,0,0.7)',
      }}>
        {/* 패널 헤더 */}
        <div style={{
          padding: '12px 18px',
          borderBottom: `1px solid rgba(255,255,255,0.06)`,
          background: `rgba(82,136,193,0.08)`,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%', background: '#FF4336',
            boxShadow: '0 0 6px rgba(255,67,54,0.9)',
          }} />
          <div style={{ color: TG.sub, fontSize: 13, fontWeight: 600, letterSpacing: 3 }}>
            뉴스속보 · 실시간
          </div>
        </div>
        {/* 뉴스 이미지 스크롤 */}
        <div style={{ position: 'relative', overflow: 'hidden', height: '100%' }}>
          <Img
            src={staticFile('images/news_realtime.png')}
            style={{
              width: '130%', height: 'auto',
              objectFit: 'cover', objectPosition: 'top left',
              // 흰 배경 → 다크모드 변환
              filter: 'invert(0.88) hue-rotate(155deg) brightness(0.6) saturate(0.65)',
              transform: `translateY(${newsScroll}px)`,
            }}
          />
          {/* 하단 페이드 */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, height: 80,
            background: `linear-gradient(180deg, transparent, ${TG.bg})`,
          }} />
        </div>
      </div>

      {/* ── 텔레그램 알림 카드 그리드 (3열 × 4행) ── */}
      <AbsoluteFill style={{ opacity: cardsFade }}>
        {CARDS.map((card, idx) => {
          const appear = CARD_PROGS[idx] ?? 0.5;
          const cardOp  = interpolate(prog, [appear, appear + 0.025], [0, 1], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          });
          const cardSlide = interpolate(prog, [appear, appear + 0.03], [18, 0], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });

          const col = idx % 3;
          const row = Math.floor(idx / 3);
          const x = 30 + col * 475;
          const y = 65  + row * 240;

          const glowIntensity = idx > 8 ? '0 0 16px rgba(0,255,208,0.3)' : '0 0 8px rgba(0,255,208,0.12)';

          return (
            <div key={idx} style={{
              position: 'absolute',
              left: x, top: y + cardSlide,
              width: 450,
              opacity: cardOp,
              background: card.warn ? 'rgba(60,15,0,0.93)' : TG.bg,
              borderRadius: 14,
              padding: '14px 18px',
              border: card.warn
                ? '1px solid rgba(255,100,0,0.45)'
                : `1px solid rgba(82,136,193,0.18)`,
              borderLeft: card.warn ? '3px solid #FF6B00' : `3px solid ${C.main}`,
              boxShadow: card.warn
                ? '0 4px 24px rgba(255,100,0,0.2)'
                : `0 4px 20px rgba(0,0,0,0.55), ${glowIntensity}`,
            }}>
              {/* 채널 헤더 */}
              <div style={{
                display: 'flex', justifyContent: 'space-between',
                alignItems: 'center', marginBottom: 8,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {/* 채널 아이콘 */}
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: card.warn
                      ? '#FF6B00'
                      : `hsl(${idx * 47}, 52%, 42%)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#fff', fontSize: 13, fontWeight: 800, flexShrink: 0,
                  }}>{card.ch.charAt(0)}</div>
                  <div style={{
                    color: card.warn ? '#FF6B00' : TG.accent,
                    fontSize: 13, fontWeight: 700,
                  }}>{card.ch}</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div style={{
                    color: card.warn ? '#FF6B00' : C.main,
                    fontSize: 11, fontWeight: 700, opacity: 0.85,
                  }}>{card.tag}</div>
                  <div style={{ color: TG.sub, fontSize: 11 }}>{card.time}</div>
                </div>
              </div>
              {/* 메시지 */}
              <div style={{
                color: card.warn ? '#FFB080' : TG.text,
                fontSize: 14, fontWeight: 500, lineHeight: 1.5,
                opacity: card.warn ? 0.95 : 0.88,
              }}>{card.msg}</div>
            </div>
          );
        })}
      </AbsoluteFill>

      {/* 알림 카운터 — 우상단 */}
      <div style={{
        position: 'absolute', top: 30, left: 60,
        opacity: cardsFade,
      }}>
        <div style={{
          color: C.textSub, fontSize: 14, fontWeight: 600, letterSpacing: 4, marginBottom: 4,
        }}>오늘 알림</div>
        <div style={{
          color: C.main, fontSize: 88, fontWeight: 900, lineHeight: 1,
          fontFamily: '"Consolas","Menlo",monospace',
          textShadow: counter > 300 ? GLOW.mid.text : GLOW.weak.text,
        }}>{counter.toLocaleString()}</div>
        <div style={{ color: C.textSub, fontSize: 14, marginTop: 2 }}>개</div>
      </div>

      {/* 채널 수 라벨 */}
      <div style={{
        position: 'absolute', bottom: 52, left: 30,
        opacity: chLabelOp * cardsFade,
      }}>
        <div style={{ color: C.textSub, fontSize: 22, fontWeight: 600 }}>
          채널&nbsp;
          <span style={{ color: C.main, fontWeight: 900, fontSize: 36 }}>100</span>
          &nbsp;개에서 동시에 쏟아집니다
        </div>
      </div>

      {/* 절정 직전 텍스트 */}
      <div style={{
        position: 'absolute', bottom: 52, left: 0, right: 0, textAlign: 'center',
        opacity: p4text * cardsFade,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 26, fontWeight: 400, opacity: 0.7 }}>
          이 많은 걸 다 보다 보면 장이 시작되고...
        </div>
      </div>

      {/* 하단 STAGE 라벨 */}
      <div style={{
        position: 'absolute', bottom: 22, left: 0, right: 0, textAlign: 'center',
        color: C.textPrimary, fontSize: 22, fontWeight: 700, opacity: 0.38 * cardsFade,
      }}>STAGE 2 · 정보 홍수</div>

      {/* ════════ PHASE 5: 또 고점 ════════ */}
      <AbsoluteFill style={{
        opacity: p5base, pointerEvents: 'none',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 44,
      }}>
        <div style={{ opacity: p5peak, textAlign: 'center' }}>
          <div style={{
            color: C.textSub, fontSize: 32, fontWeight: 400,
            letterSpacing: 1, marginBottom: 22,
          }}>뭔가 사야 할 것 같아서 눌러보면</div>
          <div style={{
            color: '#FF4336', fontSize: 108, fontWeight: 900, lineHeight: 0.92,
            textShadow: '0 0 28px rgba(255,67,54,0.9), 0 0 80px rgba(255,67,54,0.4)',
          }}>또 고점</div>
          <div style={{
            color: '#FF4336', fontSize: 44, fontWeight: 700,
            marginTop: 14, opacity: 0.82,
          }}>에 물려 있어요</div>
        </div>

        <div style={{
          opacity: p5q,
          color: C.textSub, fontSize: 34, fontWeight: 400,
          letterSpacing: 2, textAlign: 'center',
        }}>
          정보가 많을수록 왜 더 어려운 걸까요?
        </div>
      </AbsoluteFill>

    </AbsoluteFill>
  );
};
