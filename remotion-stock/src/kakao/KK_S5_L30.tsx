/**
 * KK_S5_L30 — S5 클로드 설치 (STEP 1 오버레이)
 * 영상: 31.37s → 942프레임 @30fps
 *
 * Whisper 전사 (수정 적용):
 *   f0~87    클로드 데스크탑 앱을 설치하는 것이 첫 번째 단계입니다.
 *   f97~180  구글에서 클로드 AI를 검색하면 바로 나타납니다.
 *   f188~230 다운로드해서 설치해야 합니다.
 *   f239~344 하나 말씀드릴 건 자동화를 하려면 유료 플랜이 필요합니다.
 *   f356~392 월 3만 원 정도예요.
 *   f405~469 꼭 돈을 써야 해 하실 수 있을 텐데요.
 *   f478~556 주식할 때 손절하고 수십만 원 나가는 건 쉽죠.
 *   f574~696 매일 나를 위해 일하는 비서한테 월 3만 원 주는 거 아까워하시면 안 됩니다.
 *   f709~778 무료 버전엔 이 자동화 기능을 아예 없어요.
 *   f796~888 설치하고 실행하면 왼쪽에 Computer Use 탭이 보일 텐데
 *   f888~925 이제 클릭하시면 됩니다.
 */

import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
} from 'remotion';

export const KK_S5_L30_FRAMES = 942;

const LIME   = '#AAFF00';
const LIME50 = 'rgba(170,255,0,0.5)';
const LIME20 = 'rgba(170,255,0,0.2)';
const CARD   = 'rgba(0,0,0,0.84)';
const BORDER = 'rgba(170,255,0,0.45)';
const RED20  = 'rgba(255,80,80,0.18)';
const REDBR  = 'rgba(255,80,80,0.45)';

const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (f: number, from: number, damping = 9, stiffness = 270, mass = 0.7) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping, stiffness, mass } });

// ── 자막 세그먼트 (Whisper × 30fps, 오인식 수정 적용) ──
const SUBS = [
  { from: 0,   to: 87,  text: '클로드 데스크탑 앱을 설치하는 것이\n첫 번째 단계입니다.',          accent: '첫 번째 단계' },
  { from: 97,  to: 180, text: '구글에서 클로드 AI를 검색하면\n바로 나타납니다.',                  accent: '클로드 AI' },
  { from: 188, to: 230, text: '다운로드해서 설치해야 합니다.',                                    accent: '설치' },
  { from: 239, to: 344, text: '자동화를 하려면 유료 플랜이 필요합니다.',                          accent: '유료 플랜' },
  { from: 356, to: 392, text: '월 3만 원 정도예요.',                                              accent: '3만 원' },
  { from: 405, to: 469, text: '꼭 돈을 써야 해 하실 수 있을 텐데요.',                            accent: '돈을 써야' },
  { from: 478, to: 556, text: '주식할 때 손절하고 수십만 원 나가는 건 쉽죠.',                    accent: '수십만 원' },
  { from: 574, to: 696, text: '매일 나를 위해 일하는 비서한테\n월 3만 원 주는 거 아까워하시면 안 됩니다.', accent: '3만 원' },
  { from: 709, to: 778, text: '무료 버전엔 이 자동화 기능을 아예 없어요.',                       accent: '자동화 기능' },
  { from: 796, to: 888, text: '설치하고 실행하면 왼쪽에\nComputer Use 탭이 보일 텐데',            accent: 'Computer Use' },
  { from: 888, to: 925, text: '이제 클릭하시면 됩니다.',                                          accent: '클릭' },
];

// ── 다운로드 단계 ──
const STEPS = [
  { icon: '🔍', label: 'Google 검색',   sub: '"Claude AI" 또는 "Claude Desktop"', delay: 100 },
  { icon: '⬇️', label: '다운로드',      sub: 'Download 버튼 클릭',                 delay: 132 },
  { icon: '⚙️', label: '설치 실행',     sub: 'installer 실행 → 완료',              delay: 164 },
];

// ── 유료 플랜 기능 ──
const PLAN_FEATS = [
  { label: '자동화 (MCP 연결)',   delay: 260 },
  { label: 'Computer Use 탭',    delay: 278 },
  { label: '외부 앱 제어',        delay: 296 },
  { label: '장 전 브리핑 자동화', delay: 314 },
];

// ── 비용 비교 ──
const COST_COMPARE = [
  { icon: '🔴', label: '손절 한 번',      value: '수십만 원',  delay: 498 },
  { icon: '🟢', label: 'AI 비서 한 달',   value: '월 3만 원',  delay: 528 },
];

const ClaudeLogo: React.FC<{ size?: number }> = ({ size = 46 }) => (
  <svg width={size} height={size} viewBox="0 0 46 46">
    <rect width="46" height="46" rx="10" fill="#D97757" />
    <rect x="10" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="19.5" y="10" width="7" height="26" rx="3.5" fill="white" />
    <rect x="29" y="10" width="7" height="26" rx="3.5" fill="white" />
  </svg>
);

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'absolute',
  background: CARD,
  border: `1.5px solid ${BORDER}`,
  borderRadius: 6,
  overflow: 'hidden',
  ...extra,
});

const kicker: React.CSSProperties = {
  fontFamily: "'Courier New', monospace",
  fontSize: 10,
  color: LIME,
  letterSpacing: 3,
  textTransform: 'uppercase',
  padding: '12px 18px 10px',
  borderBottom: `1px solid ${LIME20}`,
};

export const KK_S5_L30: React.FC = () => {
  const f = useCurrentFrame();

  const activeSub = SUBS.find(s => f >= s.from && f < s.to);

  const panelOp = (start: number, end: number) =>
    ci(f, start, start + 20) * ci(f, end - 16, end, 1, 0);
  const slideX = (start: number, dir: 1 | -1) =>
    dir * (1 - sp(f, start)) * 40;
  const slideY = (start: number) =>
    (1 - sp(f, start, 10, 260, 0.6)) * -30;

  /* ── Phase 1: STEP 배지 (f0~90) ── */
  const stepOp    = panelOp(4, 90);
  const stepScale = 0.82 + sp(f, 4, 8, 280, 0.6) * 0.18;

  /* ── Phase 2: 다운로드 단계 패널 (f95~235) ── */
  const dlOp = panelOp(95, 235);

  /* ── Phase 3a: 유료 플랜 카드 (f240~470) ── */
  const planOp  = panelOp(240, 470);
  /* ── Phase 3b: 비용 임팩트 (f480~700) ── */
  const costOp  = panelOp(480, 700);
  /* ── Phase 3c: 비서 임팩트 (f578~700) ── */
  const secOp   = panelOp(578, 700);

  /* ── Phase 4: 무료 경고 (f705~785) ── */
  const warnOp    = panelOp(705, 785);
  const warnScale = 0.75 + sp(f, 705, 7, 290, 0.5) * 0.25;

  /* ── Phase 5: 완료 안내 (f795~941) ── */
  const doneOp  = panelOp(795, 936);

  return (
    <AbsoluteFill style={{ fontFamily: "'Inter', sans-serif", overflow: 'hidden', background: '#000' }}>

      <OffthreadVideo
        src={staticFile('kakao/s5scene.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.18) 0%, transparent 30%, transparent 58%, rgba(0,0,0,0.6) 100%)',
      }} />

      {/* ══ Phase 1: STEP 1 배지 (f4~90) ══ */}
      <div style={{
        position: 'absolute', top: 72, left: '50%',
        transform: `translateX(-50%) scale(${stepScale})`,
        transformOrigin: 'center top',
        ...panel({ position: 'relative', width: 600, padding: '18px 36px', textAlign: 'center' }),
        opacity: stepOp,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14, marginBottom: 10 }}>
          <ClaudeLogo size={36} />
          <div style={{ fontFamily: "'Courier New',monospace", fontSize: 10, color: LIME50,
            letterSpacing: 3, textTransform: 'uppercase' }}>
            STOCK BRAIN · 셋업 가이드
          </div>
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 28, fontWeight: 800,
          color: '#fff', textShadow: '0 2px 12px rgba(0,0,0,0.9)', lineHeight: 1.4 }}>
          <span style={{ color: LIME, textShadow: `0 0 18px rgba(170,255,0,0.7)` }}>STEP 1</span>
          {' — 클로드 데스크탑 설치'}
        </div>
      </div>

      {/* ══ Phase 2: 다운로드 단계 패널 (f95~235) ══ */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 440, height: 230 }),
        opacity: dlOp,
        transform: `translateX(${slideX(95, -1)}px)`,
      }}>
        <div style={kicker}>DOWNLOAD · 설치 방법</div>
        {STEPS.map((step, i) => {
          const rowOp = ci(f, step.delay, step.delay + 20);
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              opacity: rowOp,
            }}>
              <span style={{ fontSize: 18, width: 26, textAlign: 'center' }}>{step.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 14, fontWeight: 700,
                  color: '#fff', textShadow: '0 1px 8px rgba(0,0,0,0.9)' }}>{step.label}</div>
                <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                  color: 'rgba(255,255,255,0.35)', letterSpacing: 1.5 }}>{step.sub}</div>
              </div>
              <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                color: LIME, letterSpacing: 1.5,
                opacity: ci(f, step.delay + 16, step.delay + 28),
                textShadow: `0 0 8px ${LIME50}` }}>✓ DONE</div>
            </div>
          );
        })}
      </div>

      {/* ══ Phase 3a: 유료 플랜 카드 (f240~470) ══ */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 440, height: 280 }),
        opacity: planOp,
        transform: `translateX(${slideX(240, -1)}px)`,
      }}>
        <div style={{ ...kicker, display: 'flex', alignItems: 'center', gap: 10 }}>
          <ClaudeLogo size={28} />
          <span>PRO PLAN · 유료 플랜</span>
        </div>

        <div style={{ padding: '8px 18px 4px',
          fontFamily: "'Inter',sans-serif", fontSize: 12, fontWeight: 600,
          color: 'rgba(255,255,255,0.36)', opacity: ci(f, 244, 258) }}>
          자동화에 필요한 기능들
        </div>

        {PLAN_FEATS.map((ft, i) => {
          const rowOp   = ci(f, ft.delay, ft.delay + 16);
          const checkOp = ci(f, ft.delay + 12, ft.delay + 24);
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '9px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              opacity: rowOp,
            }}>
              <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                color: LIME50, width: 18 }}>{String(i + 1).padStart(2, '0')}</span>
              <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 14, fontWeight: 700,
                color: '#fff', flex: 1, textShadow: '0 1px 8px rgba(0,0,0,0.9)' }}>
                {ft.label}
              </span>
              <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                color: LIME, letterSpacing: 1.5, opacity: checkOp,
                textShadow: `0 0 8px ${LIME50}` }}>✓ UNLOCK</span>
            </div>
          );
        })}

        {/* 가격 */}
        <div style={{
          padding: '12px 18px',
          display: 'flex', alignItems: 'center', gap: 8,
          opacity: ci(f, 356, 372),
        }}>
          <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 36, fontWeight: 900,
            color: LIME, letterSpacing: -1.5,
            textShadow: `0 0 24px rgba(170,255,0,0.65)` }}>₩30,000</span>
          <span style={{ fontFamily: "'Courier New',monospace", fontSize: 10,
            color: 'rgba(255,255,255,0.4)', letterSpacing: 1 }}>/ MONTH</span>
        </div>
      </div>

      {/* ══ Phase 3b: 비용 비교 카드 (f480~700) ══ */}
      <div style={{
        ...panel({ right: 36, top: 80, width: 380, height: 220 }),
        opacity: costOp,
        transform: `translateX(${slideX(480, 1)}px)`,
      }}>
        <div style={kicker}>COST COMPARE · 비용 비교</div>
        {COST_COMPARE.map((item, i) => {
          const rowOp = ci(f, item.delay, item.delay + 20);
          const isGreen = i === 1;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '16px 18px',
              borderBottom: i < COST_COMPARE.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
              opacity: rowOp,
              background: isGreen ? 'rgba(170,255,0,0.05)' : 'transparent',
            }}>
              <span style={{ fontSize: 20 }}>{item.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                  color: 'rgba(255,255,255,0.35)', letterSpacing: 2, marginBottom: 3 }}>
                  {item.label}
                </div>
                <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 20, fontWeight: 800,
                  color: isGreen ? LIME : 'rgba(255,100,100,0.9)',
                  textShadow: isGreen ? `0 0 14px rgba(170,255,0,0.6)` : '0 0 14px rgba(255,60,60,0.5)' }}>
                  {item.value}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ══ Phase 3c: 비서 임팩트 (f578~700) ══ */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        opacity: secOp, pointerEvents: 'none',
        paddingBottom: '14%',
        transform: `translateY(${slideY(578)}px)`,
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 11, color: LIME50,
          letterSpacing: 4, textTransform: 'uppercase', marginBottom: 12 }}>
          YOUR AI SECRETARY · 매일 일하는 비서
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 64, fontWeight: 900, lineHeight: 1.1,
          color: '#fff', letterSpacing: -2, textAlign: 'center',
          textShadow: '0 0 40px rgba(255,255,255,0.1), 0 6px 28px rgba(0,0,0,0.95)' }}>
          월 3만 원으로
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 64, fontWeight: 900, lineHeight: 1.1,
          color: LIME, letterSpacing: -2,
          textShadow: `0 0 40px rgba(170,255,0,0.55)` }}>
          AI 비서 고용
        </div>
      </div>

      {/* ══ Phase 4: 무료 경고 임팩트 (f705~785) ══ */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: `translate(-50%, -50%) scale(${warnScale})`,
        ...panel({ position: 'relative', width: 640, padding: '28px 36px', textAlign: 'center' }),
        opacity: warnOp,
        background: RED20,
        border: `1.5px solid ${REDBR}`,
        paddingBottom: '14%',
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 10,
          color: 'rgba(255,100,100,0.7)', letterSpacing: 3, textTransform: 'uppercase', marginBottom: 12 }}>
          ⚠️ FREE PLAN · 무료 버전 한계
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 30, fontWeight: 800,
          color: '#fff', lineHeight: 1.45 }}>
          무료 버전엔{' '}
          <span style={{ color: 'rgba(255,100,100,0.9)', textShadow: '0 0 18px rgba(255,60,60,0.6)' }}>
            자동화 기능
          </span>
          이<br />아예 없어요.
        </div>
      </div>

      {/* ══ Phase 5: 설치 완료 안내 (f795~941) ══ */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 480, height: 180 }),
        opacity: doneOp,
        transform: `translateX(${slideX(795, -1)}px)`,
      }}>
        <div style={{ ...kicker, display: 'flex', alignItems: 'center', gap: 10 }}>
          <ClaudeLogo size={28} />
          <span>SETUP COMPLETE · 설치 완료</span>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{
            fontFamily: "'Inter',sans-serif", fontSize: 15, fontWeight: 700, color: '#fff',
            opacity: ci(f, 800, 816),
          }}>
            실행 후 왼쪽 사이드바 확인
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            fontFamily: "'Inter',sans-serif", fontSize: 16, fontWeight: 800,
            color: LIME, textShadow: `0 0 12px rgba(170,255,0,0.7)`,
            opacity: ci(f, 820, 840),
          }}>
            <span style={{ fontSize: 20 }}>👆</span>
            <span>Computer Use 탭 클릭</span>
          </div>
          <div style={{
            height: 2, background: LIME, borderRadius: 1,
            width: `${ci(f, 840, 885, 0, 100)}%`,
            boxShadow: `0 0 10px ${LIME50}`,
          }} />
        </div>
      </div>

      {/* ══ 자막 바 ══ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '18%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontFamily: "'Inter',sans-serif",
            fontSize: 36, fontWeight: 700, color: '#fff',
            textAlign: 'center', paddingInline: 80,
            textShadow: '0 2px 18px rgba(0,0,0,0.98), 0 0 40px rgba(0,0,0,0.9)',
            lineHeight: 1.45,
            whiteSpace: 'pre-line',
          }}>
            {activeSub.text.split(activeSub.accent).map((part, i, arr) => (
              <React.Fragment key={i}>
                {part}
                {i < arr.length - 1 && (
                  <span style={{ color: LIME, textShadow: `0 0 14px rgba(170,255,0,0.9)` }}>
                    {activeSub.accent}
                  </span>
                )}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
