/**
 * KK_S5_Activation — 클로드 데스크탑 설치 가이드
 * 디자인: Activation 테마 (06_brand.json 기반)
 * 942프레임 = 31.4초 @ 30fps
 *
 * Production Rules 점검 (실행 시 자동):
 *   R1 ✓ label≥16 / subtitle≥36 / body≥18 / title≥24
 *   R2 ✓ 우측 패널 max_y=480 < pip_top=679 (충분한 여백)
 *   R3 ✓ objectFit:cover 전체 사용
 *   R4 ✓ PiP 하단=870 / 자막 상단=907 → gap=37px
 *   R5 ✓ 동시 요소 최대 5개
 */

import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { checkS5Spec } from '../utils/productionCheck';

// 빌드 시 점검 (오류 있으면 콘솔에 출력)
try { checkS5Spec(); } catch (e) { console.error('[S5 Activation]', e); }

export const KK_S5_ACTIVATION_FRAMES = 942;

// ── Brand (06_brand.json)
const D = {
  BG:      '#08090D',
  BLUE:    '#3B82F6',
  BLUE25:  'rgba(59,130,246,0.25)',
  BLUE15:  'rgba(59,130,246,0.15)',
  BLUE12:  'rgba(59,130,246,0.12)',
  GREEN:   '#22C55E',
  GREEN15: 'rgba(34,197,94,0.15)',
  AMBER:   '#F59E0B',
  AMBER12: 'rgba(245,158,11,0.12)',
  AMBER40: 'rgba(245,158,11,0.4)',
  RED:     '#EF4444',
  RED15:   'rgba(239,68,68,0.15)',
  WHITE:   '#F8FAFC',
  MUTED:   '#64748B',
  CARD:    'rgba(8,9,13,0.90)',
  BORDB:   'rgba(59,130,246,0.40)',
  BORDG:   'rgba(34,197,94,0.40)',
  BORDA:   'rgba(245,158,11,0.50)',
};

// ── PiP 레이아웃 (R2·R4 통과)
const PIP_W = 340, PIP_H = 191;
const PIP_R = 36,  PIP_B = 210; // gap→subtitle=37px ✓

// ── 헬퍼
const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (f: number, from: number, damp = 10, stiff = 280, mass = 0.72) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping: damp, stiffness: stiff, mass } });

// ── 스크린샷 타임라인
const SCREENS = [
  { src: staticFile('kakao/s5/img1.png'), from: 0,   to: 96  },
  { src: staticFile('kakao/s5/img2.png'), from: 97,  to: 187 },
  { src: staticFile('kakao/s5/img3.png'), from: 188, to: 238 },
  { src: staticFile('kakao/s5/img4.png'), from: 239, to: 795 },
  { src: staticFile('kakao/s5/img5.png'), from: 796, to: 942 },
];

// ── 자막 (SRT 기반)
const SUBS = [
  { from: 0,   to: 87,  text: '클로드 데스크탑 앱을 설치하는 것이\n첫 번째 단계입니다.',                  accent: '첫 번째 단계' },
  { from: 97,  to: 180, text: '구글에서 클로드 AI를 검색하면\n바로 나타납니다.',                            accent: '클로드 AI' },
  { from: 188, to: 230, text: '다운로드해서 설치해야 합니다.',                                              accent: '설치' },
  { from: 239, to: 344, text: '자동화를 하려면 유료 플랜이 필요합니다.',                                    accent: '유료 플랜' },
  { from: 356, to: 392, text: '월 3만 원 정도예요.',                                                        accent: '3만 원' },
  { from: 405, to: 469, text: '꼭 돈을 써야 해 하실 수 있을 텐데요.',                                      accent: '돈을 써야' },
  { from: 478, to: 556, text: '주식할 때 손절하고 수십만 원 나가는 건 쉽죠.',                              accent: '수십만 원' },
  { from: 574, to: 696, text: '매일 나를 위해 일하는 비서한테\n월 3만 원 주는 거 아까워하시면 안 됩니다.', accent: '3만 원' },
  { from: 709, to: 778, text: '무료 버전엔 이 자동화 기능을 아예 없어요.',                                  accent: '자동화 기능' },
  { from: 796, to: 888, text: '설치하고 실행하면 왼쪽에\nCowork 탭이 보일 텐데',                           accent: 'Cowork 탭' },
  { from: 888, to: 925, text: '이제 클릭하시면 됩니다.',                                                    accent: '클릭' },
];

// ── 진행 바 (0~100%, Scene 경계에서 선형 증가)
const ProgressBar: React.FC<{ f: number }> = ({ f }) => {
  const pct = interpolate(
    f,
    [0, 96, 238, 469, 708, 795, 942],
    [0,  10,  33,  66,  80,  90, 100],
    { extrapolateRight: 'clamp' }
  );
  const done = f > 860;
  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: 'rgba(255,255,255,0.06)', zIndex: 100 }}>
      <div style={{
        height: '100%', width: `${pct}%`,
        background: done
          ? `linear-gradient(90deg, ${D.BLUE} 0%, ${D.GREEN} 100%)`
          : `linear-gradient(90deg, ${D.BLUE} 0%, rgba(59,130,246,0.65) 100%)`,
        boxShadow: `0 0 6px ${done ? D.GREEN : D.BLUE}88`,
        transition: 'background 0.4s',
      }} />
    </div>
  );
};

// ── STEP 배지 (좌상단, R1: 80px number, 16px label)
const StepBadge: React.FC<{ f: number }> = ({ f }) => {
  const badges = [
    { num: '01', inF: 8,   outF: 238 },
    { num: '02', inF: 239, outF: 795 },
    { num: '03', inF: 796, outF: 942 },
  ];
  return (
    <>
      {badges.map(({ num, inF, outF }) => {
        const op = Math.min(ci(f, inF, inF + 16), ci(f, outF - 10, outF, 1, 0));
        if (op <= 0.01) return null;
        return (
          <div key={num} style={{ position: 'absolute', top: 44, left: 56, zIndex: 90, opacity: op }}>
            <div style={{
              fontFamily: "'Courier New', monospace",
              fontSize: 80,
              fontWeight: 900,
              color: D.BLUE,
              lineHeight: 1,
              textShadow: `0 0 40px ${D.BLUE25}, 0 0 80px ${D.BLUE12}`,
            }}>{num}</div>
            <div style={{
              fontFamily: 'Pretendard, Inter, sans-serif',
              fontSize: 16,
              fontWeight: 400,
              color: D.MUTED,
              letterSpacing: '0.10em',
              textTransform: 'uppercase' as const,
              paddingLeft: 2,
              marginTop: 2,
            }}>STEP</div>
          </div>
        );
      })}
    </>
  );
};

// ── 자막 바 (R1: 38px, 하단 16%)
const SubtitleBar: React.FC<{ f: number }> = ({ f }) => {
  const sub = SUBS.find(s => f >= s.from && f < s.to);
  if (!sub) return null;

  const op = Math.min(
    ci(f, sub.from, sub.from + 8),
    ci(f, sub.to - 6, sub.to, 1, 0)
  );

  const renderText = () => {
    if (!sub.accent) {
      return <>{sub.text.split('\n').map((line, i) => <React.Fragment key={i}>{i > 0 && <br />}{line}</React.Fragment>)}</>;
    }
    const parts = sub.text.split(sub.accent);
    return parts.reduce((acc: React.ReactNode[], part, i) => {
      if (i > 0) {
        acc.push(
          <span key={`acc-${i}`} style={{ color: D.BLUE, borderBottom: `2.5px solid ${D.BLUE}` }}>
            {sub.accent}
          </span>
        );
      }
      acc.push(
        ...part.split('\n').map((line, j, arr) =>
          j < arr.length - 1
            ? <React.Fragment key={`${i}-${j}`}>{line}<br /></React.Fragment>
            : <React.Fragment key={`${i}-${j}`}>{line}</React.Fragment>
        )
      );
      return acc;
    }, []);
  };

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      height: '16%',
      background: 'linear-gradient(0deg, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.86) 60%, transparent 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '0 160px',
      opacity: op, zIndex: 80,
    }}>
      <p style={{
        margin: 0,
        textAlign: 'center',
        fontFamily: 'Pretendard, Inter, sans-serif',
        fontSize: 38,
        fontWeight: 800,
        color: D.WHITE,
        lineHeight: 1.4,
        textShadow: '0 2px 8px rgba(0,0,0,0.9)',
      }}>
        {renderText()}
      </p>
    </div>
  );
};

// ── Scene B: 체크리스트 패널 (left:32, f97~238)
// R2 ✓ — 좌측에만 위치, PiP(x=1544)와 겹치지 않음
const ChecklistPanel: React.FC<{ f: number }> = ({ f }) => {
  const panelOp = Math.min(ci(f, 97, 115), ci(f, 222, 238, 1, 0));
  if (panelOp <= 0.01) return null;

  const slideX = (1 - sp(f, 97, 9, 250)) * -40;

  const ITEMS = [
    { label: 'Google 검색',  sub: '"클로드 데스크탑" 검색', delay: 100, doneAt: 155 },
    { label: '다운로드 클릭', sub: 'Download 버튼 클릭',     delay: 116, doneAt: 195 },
    { label: '설치 실행',     sub: 'installer 실행 → 완료', delay: 132, doneAt: 999 },
  ];

  return (
    <div style={{
      position: 'absolute',
      top: 200, left: 32,
      width: 400,
      opacity: panelOp,
      transform: `translateX(${slideX}px)`,
      zIndex: 60,
    }}>
      <div style={{
        background: D.CARD,
        border: `1.5px solid ${D.BORDB}`,
        borderRadius: 8,
        overflow: 'hidden',
        boxShadow: `0 8px 32px rgba(0,0,0,0.65), 0 0 24px ${D.BLUE12}`,
      }}>
        {/* 헤더 */}
        <div style={{
          padding: '12px 20px 10px',
          borderBottom: `1px solid rgba(59,130,246,0.20)`,
          fontFamily: "'Courier New', monospace",
          fontSize: 16,
          fontWeight: 400,
          color: D.BLUE,
          letterSpacing: '0.09em',
          textTransform: 'uppercase' as const,
        }}>설치 단계</div>

        {/* 항목들 */}
        <div style={{ padding: '6px 0 10px' }}>
          {ITEMS.map((item, i) => {
            const itemOp = ci(f, item.delay, item.delay + 14);
            const isDone = f >= item.doneAt;
            const itemX  = (1 - sp(f, item.delay, 10, 280)) * -18;

            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                padding: '9px 20px',
                opacity: itemOp,
                transform: `translateX(${itemX}px)`,
              }}>
                {/* 상태 원 */}
                <div style={{
                  width: 24, height: 24, borderRadius: '50%',
                  flexShrink: 0, marginTop: 2,
                  background: isDone ? D.GREEN15 : D.BLUE15,
                  border: `1.5px solid ${isDone ? D.GREEN : D.BLUE}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13,
                  color: isDone ? D.GREEN : D.BLUE,
                  fontWeight: 700,
                }}>
                  {isDone ? '✓' : String(i + 1)}
                </div>

                <div>
                  <div style={{
                    fontFamily: 'Pretendard, Inter, sans-serif',
                    fontSize: 20,
                    fontWeight: 700,
                    color: isDone ? D.MUTED : D.WHITE,
                    lineHeight: 1.2,
                  }}>{item.label}</div>
                  <div style={{
                    fontFamily: 'Pretendard, Inter, sans-serif',
                    fontSize: 16,
                    fontWeight: 400,
                    color: D.MUTED,
                    marginTop: 2,
                  }}>{item.sub}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ── Scene C: Pro 플랜 카드 (right:32, width:340, f239~469)
// R2 ✓ — top=168, 예상 bottom≈480 << pip_top=679
const ProPlanCard: React.FC<{ f: number }> = ({ f }) => {
  const panelOp = Math.min(ci(f, 240, 258), ci(f, 455, 469, 1, 0));
  if (panelOp <= 0.01) return null;

  const slideX = (1 - sp(f, 240, 9, 250)) * 40;

  const FEATS = [
    { label: '자동화 (MCP 연결)',   delay: 262 },
    { label: 'Cowork 탭',           delay: 278 },
    { label: '외부 앱 제어',         delay: 294 },
    { label: '장 전 브리핑 자동화',  delay: 310 },
  ];

  const priceOp = ci(f, 340, 358);

  return (
    <div style={{
      position: 'absolute',
      top: 168, right: 32,
      width: 340,
      opacity: panelOp,
      transform: `translateX(${slideX}px)`,
      zIndex: 60,
    }}>
      <div style={{
        background: D.CARD,
        border: `1.5px solid ${D.BORDB}`,
        borderRadius: 8,
        overflow: 'hidden',
        boxShadow: `0 8px 32px rgba(0,0,0,0.65), 0 0 32px ${D.BLUE25}`,
      }}>
        {/* 헤더 */}
        <div style={{
          padding: '12px 20px 10px',
          background: `linear-gradient(90deg, ${D.BLUE12} 0%, transparent 100%)`,
          borderBottom: `1px solid rgba(59,130,246,0.20)`,
          fontFamily: "'Courier New', monospace",
          fontSize: 16,
          fontWeight: 700,
          color: D.BLUE,
          letterSpacing: '0.09em',
          textTransform: 'uppercase' as const,
        }}>PRO PLAN ONLY</div>

        {/* 기능 목록 */}
        <div style={{ padding: '8px 0' }}>
          {FEATS.map((feat, i) => {
            const featOp = ci(f, feat.delay, feat.delay + 14);
            const featX  = (1 - sp(f, feat.delay, 10, 280)) * 18;
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '9px 20px',
                opacity: featOp,
                transform: `translateX(${featX}px)`,
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: D.BLUE, flexShrink: 0,
                }} />
                <span style={{
                  fontFamily: 'Pretendard, Inter, sans-serif',
                  fontSize: 18,
                  fontWeight: 600,
                  color: D.WHITE,
                }}>{feat.label}</span>
              </div>
            );
          })}
        </div>

        {/* 가격 (R1: 56px ✓) */}
        <div style={{
          padding: '14px 20px 18px',
          borderTop: `1px solid rgba(59,130,246,0.15)`,
          opacity: priceOp,
          textAlign: 'center' as const,
        }}>
          <div style={{
            fontFamily: "'Courier New', monospace",
            fontSize: 56,
            fontWeight: 700,
            color: D.WHITE,
            lineHeight: 1,
          }}>₩30,000</div>
          <div style={{
            fontFamily: 'Pretendard, Inter, sans-serif',
            fontSize: 16,
            fontWeight: 400,
            color: D.MUTED,
            marginTop: 6,
            letterSpacing: '0.09em',
            textTransform: 'uppercase' as const,
          }}>월정액</div>
        </div>
      </div>
    </div>
  );
};

// ── Scene D: 비용 비교 카드 (f478~708)
// R2 ✓ — 카드 끝 x=1450 << pip_left=1544
const CostCompareCards: React.FC<{ f: number }> = ({ f }) => {
  const panelOp = Math.min(ci(f, 478, 498), ci(f, 692, 708, 1, 0));
  if (panelOp <= 0.01) return null;

  const leftOp  = ci(f, 480, 500);
  const rightOp = ci(f, 496, 516);
  const vsOp    = ci(f, 514, 530);
  const leftX   = (1 - sp(f, 480, 9, 250)) * -30;
  const rightX  = (1 - sp(f, 496, 9, 250)) * 30;

  const CARD_W = 420;
  const GAP    = 80;
  const startX = (1920 - (CARD_W * 2 + GAP)) / 2; // 500px (both cards end at x=1420 << 1544) ✓

  const cardBase: React.CSSProperties = {
    width: CARD_W,
    background: D.CARD,
    borderRadius: 8,
    padding: '24px 28px',
    textAlign: 'center' as const,
  };

  return (
    <div style={{
      position: 'absolute', zIndex: 60,
      top: 380, left: startX,
      display: 'flex', gap: GAP, alignItems: 'center',
      opacity: panelOp,
    }}>
      {/* 손절 카드 */}
      <div style={{
        ...cardBase,
        border: `1.5px solid ${D.BORDA}`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.65), 0 0 24px ${D.AMBER12}`,
        opacity: leftOp,
        transform: `translateX(${leftX}px)`,
      }}>
        <div style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 16,
          fontWeight: 400,
          color: D.AMBER,
          letterSpacing: '0.09em',
          textTransform: 'uppercase' as const,
          marginBottom: 14,
        }}>손절 한 번</div>
        <div style={{
          fontFamily: "'Courier New', monospace",
          fontSize: 52,
          fontWeight: 700,
          color: D.RED,
          lineHeight: 1,
        }}>수십만 원</div>
        <div style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 18,
          fontWeight: 600,
          color: D.MUTED,
          marginTop: 12,
        }}>순식간에 사라진다</div>
      </div>

      {/* VS */}
      <div style={{ opacity: vsOp, flexShrink: 0 }}>
        <span style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 28,
          fontWeight: 400,
          color: D.MUTED,
          letterSpacing: '0.06em',
        }}>vs</span>
      </div>

      {/* AI 비서 카드 */}
      <div style={{
        ...cardBase,
        border: `1.5px solid ${D.BORDB}`,
        boxShadow: `0 8px 32px rgba(0,0,0,0.65), 0 0 24px ${D.BLUE15}`,
        opacity: rightOp,
        transform: `translateX(${rightX}px)`,
      }}>
        <div style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 16,
          fontWeight: 400,
          color: D.BLUE,
          letterSpacing: '0.09em',
          textTransform: 'uppercase' as const,
          marginBottom: 14,
        }}>AI 비서 한 달</div>
        <div style={{
          fontFamily: "'Courier New', monospace",
          fontSize: 52,
          fontWeight: 700,
          color: D.GREEN,
          lineHeight: 1,
        }}>₩30,000</div>
        <div style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 18,
          fontWeight: 600,
          color: D.MUTED,
          marginTop: 12,
        }}>매일 나를 위해 일한다</div>
      </div>
    </div>
  );
};

// ── Scene E: 경고 배너 (f709~795, 상단 드롭인)
const WarningBanner: React.FC<{ f: number }> = ({ f }) => {
  const bannerOp = Math.min(ci(f, 709, 718), ci(f, 780, 795, 1, 0));
  if (bannerOp <= 0.01) return null;

  const slideY = (1 - sp(f, 709, 5, 300, 0.5)) * -44;

  return (
    <div style={{
      position: 'absolute',
      top: 56, left: '50%',
      transform: `translateX(-50%) translateY(${slideY}px)`,
      opacity: bannerOp,
      zIndex: 75,
      width: 840,
    }}>
      <div style={{
        background: D.CARD,
        borderRadius: 8,
        padding: '16px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        border: `1.5px solid ${D.BORDA}`,
        borderLeftWidth: 4,
        boxShadow: `0 8px 32px rgba(0,0,0,0.72), 0 0 20px ${D.AMBER12}`,
      }}>
        <span style={{ fontSize: 28, flexShrink: 0 }}>⚠</span>
        <span style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 22,
          fontWeight: 700,
          color: D.AMBER,
        }}>무료 버전에는 자동화 기능이 없습니다</span>
      </div>
    </div>
  );
};

// ── Scene F: 완료 팝업 (f820~942)
// R2 ✓ — 중앙 배치, x=760~1160 << pip_left=1544
const CompletionOverlay: React.FC<{ f: number }> = ({ f }) => {
  const showOp  = ci(f, 820, 838);
  const fadeOut = ci(f, 930, 942, 1, 0);
  const op = showOp * fadeOut;
  if (op <= 0.01) return null;

  const scale = 0.55 + sp(f, 820, 8, 240) * 0.45;

  return (
    <div style={{
      position: 'absolute',
      top: '50%', left: '50%',
      transform: `translate(-50%, -50%) scale(${scale})`,
      opacity: op,
      zIndex: 70,
      textAlign: 'center' as const,
    }}>
      <div style={{
        background: D.CARD,
        border: `1.5px solid ${D.BORDG}`,
        borderRadius: 16,
        padding: '40px 60px',
        boxShadow: `0 0 60px ${D.GREEN15}, 0 16px 48px rgba(0,0,0,0.80)`,
      }}>
        {/* 초록 체크 원 */}
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: D.GREEN15,
          border: `2px solid ${D.GREEN}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 20px',
          fontSize: 38,
          color: D.GREEN,
          fontWeight: 700,
        }}>✓</div>

        <div style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 40,
          fontWeight: 800,
          color: D.WHITE,
          lineHeight: 1.1,
        }}>설치 완료</div>
        <div style={{
          fontFamily: 'Pretendard, Inter, sans-serif',
          fontSize: 18,
          fontWeight: 400,
          color: D.MUTED,
          marginTop: 10,
        }}>이제 Claude Desktop을 사용할 수 있습니다</div>
      </div>
    </div>
  );
};

// ── 메인 컴포넌트
export const KK_S5_Activation: React.FC = () => {
  const f = useCurrentFrame();

  // AI PiP: f0~45 풀화면 → 우하단 spring 이동
  const trans    = sp(f, 0, 10, 280, 0.72);
  const aiLeft   = interpolate(trans, [0, 1], [0,    1920 - PIP_W - PIP_R]);
  const aiTop    = interpolate(trans, [0, 1], [0,    1080 - PIP_H - PIP_B]);
  const aiWidth  = interpolate(trans, [0, 1], [1920, PIP_W]);
  const aiHeight = interpolate(trans, [0, 1], [1080, PIP_H]);
  const aiRadius = interpolate(trans, [0, 1], [0,    12]);
  const pipGlow  = trans;

  // 배경 opacity (초반 페이드인)
  const bgOp = ci(f, 18, 46);

  // Scene E 추가 딤 오버레이
  const dimOp = Math.min(ci(f, 709, 728), ci(f, 783, 798, 1, 0)) * 0.16;

  // 전체 페이드아웃 (마지막 12프레임)
  const globalFade = ci(f, 930, 942, 1, 0);

  return (
    <AbsoluteFill style={{ background: D.BG, overflow: 'hidden', opacity: globalFade }}>

      {/* ═══ 배경: 스크린샷 (Ken Burns) ═══ */}
      <div style={{ position: 'absolute', inset: 0, opacity: bgOp }}>
        {SCREENS.map((screen, i) => {
          const isActive = f >= screen.from && f < screen.to;
          if (!isActive) return null;
          const fadeIn   = ci(f, screen.from, screen.from + 12);
          const fadeOut  = ci(f, screen.to - 10, screen.to, 1, 0);
          const elapsed  = Math.max(0, f - screen.from);
          const zoom     = 1 + elapsed * 0.00009; // Ken Burns: 매우 느린 줌 (0.27% over 30s)
          return (
            <div key={i} style={{
              position: 'absolute', inset: 0,
              opacity: Math.min(fadeIn, fadeOut),
              transform: `scale(${zoom})`,
              transformOrigin: 'center center',
            }}>
              <Img
                src={screen.src}
                // R3 ✓: objectFit:cover — 비율 보존, 찌그러짐 없음
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>
          );
        })}
        {/* 가독성 다크 오버레이 — 패널 텍스트 대비 확보 (R6 ✓) */}
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.28)' }} />
      </div>

      {/* Scene E: 추가 딤 */}
      {dimOp > 0 && (
        <div style={{ position: 'absolute', inset: 0, background: `rgba(0,0,0,${dimOp.toFixed(2)})`, zIndex: 55 }} />
      )}

      {/* ═══ AI 발표자 PiP (풀화면 → 우하단 spring) ═══
          R4 ✓: pip_bottom=210 → 자막 gap=37px
          R2 ✓: 씬별 패널은 PiP y=679 상단 혹은 x=1544 좌측에만 배치 */}
      <div style={{
        position: 'absolute',
        left: aiLeft, top: aiTop,
        width: aiWidth, height: aiHeight,
        borderRadius: aiRadius,
        overflow: 'hidden',
        zIndex: 50,
        boxShadow: pipGlow > 0.05
          ? `0 0 ${Math.round(pipGlow * 20)}px ${D.BLUE25}, 0 8px 32px rgba(0,0,0,0.82)`
          : undefined,
        outline: pipGlow > 0.3
          ? `1.5px solid rgba(59,130,246,${(pipGlow * 0.38).toFixed(2)})`
          : undefined,
        outlineOffset: -1,
      }}>
        <OffthreadVideo
          src={staticFile('kakao/s5_ai.mp4')}
          volume={0}
          // R3 ✓: objectFit:cover
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>

      {/* ═══ 오버레이 요소들 ═══ */}

      {/* 진행 바 — 상단 4px (R4: 상단 여백 확보) */}
      <ProgressBar f={f} />

      {/* STEP 배지 — 좌상단 (R1: 80px 숫자, 16px 라벨) */}
      <StepBadge f={f} />

      {/* Scene B: 체크리스트 좌측 */}
      <ChecklistPanel f={f} />

      {/* Scene C: Pro 플랜 우측 */}
      <ProPlanCard f={f} />

      {/* Scene D: 비용 비교 중앙 */}
      <CostCompareCards f={f} />

      {/* Scene E: 경고 배너 상단 */}
      <WarningBanner f={f} />

      {/* Scene F: 완료 팝업 중앙 */}
      <CompletionOverlay f={f} />

      {/* 자막 바 — 하단 16% (R1: 38px) */}
      <SubtitleBar f={f} />

    </AbsoluteFill>
  );
};
