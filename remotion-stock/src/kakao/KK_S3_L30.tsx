/**
 * KK_S3_L30 — S3 AI신화파괴 + 진짜이유 (LIFE 3.0 오버레이)
 * 실제 대본 (Whisper 추출, 2026-06-15):
 *   f0~118   시장에 보면 AI가 알아서 매수 매도 타점 잡아준다는 프로그램들 많죠.
 *   f118~216 단언컨대 주식판에 그런 절대 치트키는 존재하지 않습니다.
 *   f216~340 주식은 살아있는 생물이라 AI가 수치만으로 계산할 수 없는
 *   f340~446 인간의 심리와 수급의 힘이 있다는 게 핵심이거든요.
 *   f446~528 그리고 제가 이 아침 자동화를 돌리는 진짜 이유는
 *   f528~607 AI에게 종목을 추천받으려는 게 아닙니다.
 *   f607~727 저희는 간밤에 쌓아진 수많은 뉴스 아이템과 주요 이벤트들을 선별하기 위해
 *   f727~790 시장이 열리기 전 제한된 시간 안에
 *   f790~934 수많은 뉴스와 이벤트들을 스크리닝해 두려는 겁니다.
 *   f934~1006 이제 힘든 자료 수집일은 AI에게 시키고
 *   f1006~1141 우리는 장이 열렸을 때 오직 돈의 흐름에만 집중하면 되는 겁니다.
 *   f1141~1212 주식도 이제 스마트한 시대가 된 겁니다.
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

export const KK_S3_L30_FRAMES = 1212;

const LIME   = '#AAFF00';
const LIME50 = 'rgba(170,255,0,0.5)';
const LIME20 = 'rgba(170,255,0,0.2)';
const RED    = '#FF4455';
const RED20  = 'rgba(255,68,85,0.2)';
const CARD   = 'rgba(0,0,0,0.84)';
const BORDER = 'rgba(170,255,0,0.45)';

const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (f: number, from: number, damping = 9, stiffness = 270, mass = 0.7) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping, stiffness, mass } });

// ── 실제 대본 자막 (Whisper segments × 30fps) ──
const SUBS = [
  { from: 0,    to: 118,  text: 'AI가 알아서 매수·매도 타점 잡아준다는 프로그램들 많죠.',        accent: '프로그램들' },
  { from: 118,  to: 216,  text: '단언컨대 주식판에 그런 절대 치트키는 존재하지 않습니다.',        accent: '치트키는 존재하지 않습니다' },
  { from: 216,  to: 340,  text: '주식은 살아있는 생물이라 AI가 수치만으로 계산할 수 없는',        accent: '살아있는 생물' },
  { from: 340,  to: 446,  text: '인간의 심리와 수급의 힘이 있다는 게 핵심이거든요.',              accent: '심리와 수급' },
  { from: 446,  to: 528,  text: '제가 이 아침 자동화를 돌리는 진짜 이유는',                      accent: '진짜 이유' },
  { from: 528,  to: 607,  text: 'AI에게 종목을 추천받으려는 게 아닙니다.',                        accent: '아닙니다' },
  { from: 607,  to: 790,  text: '간밤에 쌓인 뉴스·이벤트들을 장 열리기 전 제한된 시간 안에',     accent: '제한된 시간 안에' },
  { from: 790,  to: 934,  text: '스크리닝해 두려는 겁니다.',                                      accent: '스크리닝' },
  { from: 934,  to: 1006, text: '힘든 자료 수집일은 AI에게 시키고',                               accent: 'AI에게' },
  { from: 1006, to: 1141, text: '우리는 장이 열렸을 때 오직 돈의 흐름에만 집중하면 됩니다.',     accent: '돈의 흐름' },
  { from: 1141, to: 1212, text: '주식도 이제 스마트한 시대가 된 겁니다.',                         accent: '스마트한 시대' },
];

// ── AI 한계 항목 ──
const AI_LIMITS = [
  { icon: '🧠', label: '인간 심리',    sub: '공포·탐욕 비선형',  delay: 228 },
  { icon: '📡', label: '수급의 힘',    sub: '세력·외인 움직임',  delay: 248 },
  { icon: '💬', label: '시장 분위기',  sub: '정성적 맥락',       delay: 268 },
  { icon: '⚡', label: '뉴스 뉘앙스',  sub: '맥락 해석',         delay: 288 },
];

// ── 스크리닝 대상 목록 ──
const SCREEN_ITEMS = [
  { icon: '🌐', label: '미국·유럽 간밤 증시',  delay: 618 },
  { icon: '📰', label: '오버나이트 뉴스 필터', delay: 640 },
  { icon: '📋', label: '주요 이벤트 캘린더',   delay: 662 },
  { icon: '🏢', label: '국내 공시·실적',        delay: 684 },
  { icon: '📊', label: '관심 종목 동향',        delay: 706 },
];

const ClaudeLogo: React.FC<{ size?: number }> = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 40 40">
    <rect width="40" height="40" rx="9" fill="#D97757" />
    <rect x="8" y="8" width="6" height="24" rx="3" fill="white" />
    <rect x="17" y="8" width="6" height="24" rx="3" fill="white" />
    <rect x="26" y="8" width="6" height="24" rx="3" fill="white" />
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

export const KK_S3_L30: React.FC = () => {
  const f = useCurrentFrame();

  const activeSub = SUBS.find(s => f >= s.from && f < s.to);

  const panelOp = (start: number, end: number) =>
    ci(f, start, start + 20) * ci(f, end - 16, end, 1, 0);
  const slideX = (start: number, dir: 1 | -1) =>
    dir * (1 - sp(f, start)) * 40;

  /* ── Phase 1: DEBUNK — AI 치트키 없음 (f5~215) ── */
  const debunkOp    = panelOp(5, 215);
  const debunkScale = 0.84 + sp(f, 5, 8, 280, 0.6) * 0.16;
  // X 아이콘 펄스
  const xPulse = 1 + Math.sin(f * 0.18) * 0.06;

  /* ── Phase 2: AI 한계 LEFT + 핵심 RIGHT (f220~445) ── */
  const limitLeftOp  = panelOp(220, 445);
  const coreRightOp  = panelOp(250, 445);

  /* ── Phase 3: "진짜 이유" 임팩트 (f450~606) ── */
  const realOp    = panelOp(450, 606);
  const realScale = 0.72 + sp(f, 450, 7, 290, 0.5) * 0.28;

  /* ── Phase 4: 스크리닝 목록 (f610~933) ── */
  const screenOp = panelOp(610, 933);

  /* ── Phase 5: 결론 분할 (f938~1140) ── */
  const aiDivOp  = panelOp(938, 1140);
  const flowDivOp = panelOp(970, 1140);

  /* ── Phase 6: CTA (f1145~1210) ── */
  const ctaOp    = panelOp(1145, 1210);
  const ctaScale = 0.84 + sp(f, 1145, 8, 280, 0.6) * 0.16;

  return (
    <AbsoluteFill style={{ fontFamily: "'Inter', sans-serif", overflow: 'hidden', background: '#000' }}>

      <OffthreadVideo
        src={staticFile('kakao/s3scene.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.2) 0%, transparent 28%, transparent 60%, rgba(0,0,0,0.55) 100%)',
      }} />

      {/* ══ Phase 1: DEBUNK 카드 (f5~215) ══ */}
      <div style={{
        position: 'absolute', top: 80, left: '50%',
        transform: `translateX(-50%) scale(${debunkScale})`,
        transformOrigin: 'center top',
        ...panel({ position: 'relative', width: 780, padding: '0' }),
        opacity: debunkOp,
      }}>
        {/* AI 자동매매 → X */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 24px',
          borderBottom: `1px solid rgba(255,68,85,0.25)`,
        }}>
          <div>
            <div style={{ fontFamily: "'Courier New',monospace", fontSize: 10, color: 'rgba(255,68,85,0.6)',
              letterSpacing: 3, textTransform: 'uppercase', marginBottom: 6 }}>
              MYTH · 시장의 착각
            </div>
            <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 20, fontWeight: 800,
              color: 'rgba(255,255,255,0.85)', lineHeight: 1.4 }}>
              AI가 알아서 매수·매도 타점 잡아준다?
            </div>
          </div>
          <div style={{
            fontSize: 52, lineHeight: 1,
            transform: `scale(${xPulse})`,
            filter: 'drop-shadow(0 0 12px rgba(255,68,85,0.8))',
            opacity: ci(f, 40, 60),
          }}>
            ✗
          </div>
        </div>

        {/* 결론 */}
        <div style={{
          padding: '14px 24px',
          background: 'rgba(255,68,85,0.08)',
          opacity: ci(f, 120, 145),
        }}>
          <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 22, fontWeight: 900,
            color: RED, textShadow: `0 0 16px rgba(255,68,85,0.6)`, letterSpacing: -0.5 }}>
            단언컨대 — 절대 치트키는 없습니다
          </div>
        </div>
      </div>

      {/* ══ Phase 2 LEFT: AI 한계 목록 (f220~445) ══ */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 420, height: 300 }),
        opacity: limitLeftOp,
        transform: `translateX(${slideX(220, -1)}px)`,
      }}>
        <div style={kicker}>AI의 한계 · 수치로 못 잡는 것</div>
        {AI_LIMITS.map((item, i) => {
          const rowOp = ci(f, item.delay, item.delay + 18);
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              opacity: rowOp,
            }}>
              <span style={{ fontSize: 18, width: 24, textAlign: 'center' }}>{item.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 14, fontWeight: 700,
                  color: '#fff', textShadow: '0 1px 8px rgba(0,0,0,0.9)' }}>{item.label}</div>
                <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                  color: 'rgba(255,255,255,0.35)', letterSpacing: 1.5 }}>{item.sub}</div>
              </div>
              <div style={{ fontFamily: "'Courier New',monospace", fontSize: 10,
                color: RED, letterSpacing: 1, textShadow: `0 0 8px ${RED20}` }}>
                계산 불가
              </div>
            </div>
          );
        })}
      </div>

      {/* ══ Phase 2 RIGHT: 핵심 메시지 (f250~445) ══ */}
      <div style={{
        ...panel({ right: 36, top: 80, width: 360, height: 240 }),
        opacity: coreRightOp,
        transform: `translateX(${slideX(250, 1)}px)`,
        padding: '22px 24px',
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
          color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 14 }}>
          CORE · 핵심
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 20, fontWeight: 800,
          color: '#fff', lineHeight: 1.55 }}>
          주식은<br />
          <span style={{ color: LIME, textShadow: `0 0 14px rgba(170,255,0,0.7)` }}>
            살아있는 생물
          </span>
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 13, fontWeight: 500,
          color: 'rgba(255,255,255,0.45)', marginTop: 10, lineHeight: 1.5 }}>
          심리 × 수급의 힘<br />이건 AI가 수치로 못 잡습니다
        </div>
        <div style={{
          height: 2, background: LIME, borderRadius: 1, marginTop: 16,
          width: `${ci(f, 310, 350, 0, 100)}%`,
          boxShadow: `0 0 10px ${LIME50}`,
        }} />
      </div>

      {/* ══ Phase 3: "진짜 이유" 임팩트 (f450~606) ══ */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        opacity: realOp, pointerEvents: 'none',
        paddingBottom: '12%',
        transform: `scale(${realScale})`,
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 12, color: LIME50,
          letterSpacing: 4, textTransform: 'uppercase', marginBottom: 12 }}>
          REAL REASON · 진짜 이유 공개
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 72, fontWeight: 900,
          color: '#fff', letterSpacing: -3, textAlign: 'center',
          textShadow: '0 6px 28px rgba(0,0,0,0.95)' }}>
          종목 추천이
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 72, fontWeight: 900,
          color: RED, letterSpacing: -3,
          textShadow: `0 0 32px rgba(255,68,85,0.6)` }}>
          아닙니다
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 26, fontWeight: 700,
          color: LIME, marginTop: 18, letterSpacing: 1,
          textShadow: `0 0 14px rgba(170,255,0,0.7)`,
          opacity: ci(f, 510, 530) }}>
          그럼 진짜 이유는? 👇
        </div>
      </div>

      {/* ══ Phase 4: 스크리닝 목록 (f610~933) ══ */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 480, height: 350 }),
        opacity: screenOp,
        transform: `translateX(${slideX(610, -1)}px)`,
      }}>
        <div style={{ ...kicker, display: 'flex', alignItems: 'center', gap: 10 }}>
          <ClaudeLogo size={30} />
          <span>MORNING SCREENING · 아침 스크리닝</span>
        </div>

        <div style={{ padding: '8px 18px 4px',
          fontFamily: "'Inter',sans-serif", fontSize: 12, fontWeight: 600,
          color: 'rgba(255,255,255,0.38)', opacity: ci(f, 615, 630) }}>
          장 열리기 전 제한된 시간 안에 처리
        </div>

        {SCREEN_ITEMS.map((item, i) => {
          const rowOp  = ci(f, item.delay, item.delay + 18);
          const doneOp = ci(f, item.delay + 16, item.delay + 28);
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              opacity: rowOp,
            }}>
              <span style={{ fontSize: 17, width: 22, textAlign: 'center' }}>{item.icon}</span>
              <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 14, fontWeight: 700,
                color: '#fff', flex: 1, textShadow: '0 1px 8px rgba(0,0,0,0.9)' }}>
                {item.label}
              </span>
              <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
                color: LIME, letterSpacing: 1.5, opacity: doneOp,
                textShadow: `0 0 8px ${LIME50}` }}>✓ DONE</span>
            </div>
          );
        })}

        {/* 처리 시간 표시 */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '10px 18px',
          borderTop: `1px solid ${LIME20}`,
          opacity: ci(f, 740, 760),
        }}>
          <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
            color: 'rgba(255,255,255,0.35)', letterSpacing: 2 }}>처리 시간</span>
          <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 18, fontWeight: 900,
            color: LIME, textShadow: `0 0 12px ${LIME50}` }}>~3분</span>
        </div>
      </div>

      {/* ══ Phase 5: 결론 — AI 분업 (f938~1140) ══ */}
      {/* LEFT: AI가 하는 것 */}
      <div style={{
        ...panel({ left: 36, top: 80, width: 420, height: 240 }),
        opacity: aiDivOp,
        transform: `translateX(${slideX(938, -1)}px)`,
        padding: '20px 22px',
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
          color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 12 }}>
          AI · 담당
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 22, fontWeight: 800,
          color: 'rgba(255,255,255,0.7)', lineHeight: 1.5, marginBottom: 12 }}>
          힘든 자료 수집<br />스크리닝 노가다
        </div>
        <div style={{
          background: LIME20, border: `1px solid ${LIME50}`,
          borderRadius: 4, padding: '8px 14px',
          fontFamily: "'Courier New',monospace", fontSize: 10,
          color: LIME, letterSpacing: 1.5,
          opacity: ci(f, 960, 975),
        }}>
          ✓ AUTOMATED
        </div>
      </div>

      {/* RIGHT: 우리가 하는 것 */}
      <div style={{
        ...panel({ right: 36, top: 80, width: 420, height: 240 }),
        opacity: flowDivOp,
        transform: `translateX(${slideX(970, 1)}px)`,
        padding: '20px 22px',
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
          color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 12 }}>
          우리 · 담당
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 22, fontWeight: 800,
          color: '#fff', lineHeight: 1.5, marginBottom: 12 }}>
          오직<br />
          <span style={{ color: LIME, textShadow: `0 0 16px rgba(170,255,0,0.7)` }}>
            돈의 흐름만
          </span>
        </div>
        <div style={{
          height: 2, background: LIME, borderRadius: 1,
          width: `${ci(f, 1000, 1040, 0, 100)}%`,
          boxShadow: `0 0 10px ${LIME50}`,
        }} />
      </div>

      {/* ══ Phase 6: CTA (f1145~1210) ══ */}
      <div style={{
        position: 'absolute',
        bottom: 140, left: '50%',
        transform: `translateX(-50%) scale(${ctaScale})`,
        transformOrigin: 'center bottom',
        opacity: ctaOp,
        ...panel({ position: 'relative', width: 800, padding: '20px 36px', textAlign: 'center' }),
      }}>
        <div style={{ fontFamily: "'Courier New',monospace", fontSize: 10, color: LIME50,
          letterSpacing: 3, textTransform: 'uppercase', marginBottom: 10 }}>
          주식도 이제 스마트하게
        </div>
        <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 36, fontWeight: 900,
          color: LIME, letterSpacing: -1,
          textShadow: `0 0 28px rgba(170,255,0,0.6), 0 3px 16px rgba(0,0,0,0.95)` }}>
          아침 루틴을 스마트하게 👇
        </div>
      </div>

      {/* ══ 자막 바 ══ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '17%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontFamily: "'Inter',sans-serif",
            fontSize: 36, fontWeight: 700, color: '#fff',
            textAlign: 'center', paddingInline: 80,
            textShadow: '0 2px 16px rgba(0,0,0,0.95)',
            lineHeight: 1.4,
          }}>
            {activeSub.text.split(activeSub.accent).map((part, i, arr) => (
              <React.Fragment key={i}>
                {part}
                {i < arr.length - 1 && (
                  <span style={{ color: LIME, textShadow: `0 0 12px rgba(170,255,0,0.85)` }}>
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
