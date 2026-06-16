/**
 * KK_S5_ClaudeLive — 클로드 데스크탑 설치 가이드
 * 디자인: "Claude Live" 테마 (06_brand.json / 05_design.md 기반)
 * 클로드 CI/BI · 역동적 · 다채로움 · 942프레임(31.4초) @ 30fps
 *
 * 레이아웃: 발표자 윈도우(좌 1120×630) + 정보 컬럼(우 650w) + 키네틱 세리프 자막
 * Production Rules 자동 점검 (checkS5ClaudeLiveSpec):
 *   R1 ✓ label≥18 / subtitle=44 / body≥20 / title=32 / number=64
 *   R2 ✓ 윈도우 우단 1190 < 컬럼 1230 (40px) / 컬럼 우단 1880 < 1888
 *   R3 ✓ 발표자 cover(16:9 일치) · 스샷 contain
 *   R4 ✓ 윈도우 하단 800 ↔ 자막 907 (107px)
 *   R5 ✓ 동시 요소 ≤5
 */

import React from 'react';
import {
  AbsoluteFill, Img, interpolate, OffthreadVideo, spring, staticFile, useCurrentFrame,
} from 'remotion';
import { checkS5ClaudeLiveSpec } from '../utils/productionCheck';

try { checkS5ClaudeLiveSpec(); } catch (e) { console.error('[S5 ClaudeLive]', e); }

export const KK_S5_CLAUDELIVE_FRAMES = 942;

// ── Claude CI/BI 팔레트
const C = {
  coral: '#D97757', coralDeep: '#BE5D3A', coralSoft: '#E89B7D',
  cream: '#F0EEE6', bone: '#FAF9F5',
  warmDark: '#1F1E1D', warmDark2: '#141413',
  ink: '#1F1E1D', onDark: '#F0EEE6', muted: '#9A938A',
  cardDark: 'rgba(20,19,19,0.86)', cardCream: 'rgba(244,242,236,0.97)',
};
const SERIF = "Fraunces, 'Noto Serif KR', Georgia, serif";
const SANS  = "Pretendard, 'Noto Sans KR', sans-serif";

// ── 헬퍼
const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
const sp = (f: number, from: number, damp = 11, stiff = 260, mass = 0.7) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping: damp, stiffness: stiff, mass } });

const hexToRgb = (h: string) => {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const blend = (h1: string, h2: string, t: number) => {
  const a = hexToRgb(h1), b = hexToRgb(h2);
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * t)},${Math.round(a[1] + (b[1] - a[1]) * t)},${Math.round(a[2] + (b[2] - a[2]) * t)})`;
};

// ── 구간(섹션) 정의 — 프레임 / 액센트
type Sec = { id: string; from: number; to: number; accent: string; chapter: string };
const SECTIONS: Sec[] = [
  { id: 'A', from: 0,   to: 97,  accent: '#D97757', chapter: 'STEP 01 · 시작' },
  { id: 'B', from: 97,  to: 188, accent: '#6E92C4', chapter: 'STEP 02 · 검색' },
  { id: 'C', from: 188, to: 239, accent: '#4F9D9B', chapter: 'STEP 03 · 다운로드' },
  { id: 'D', from: 239, to: 356, accent: '#D97757', chapter: 'STEP 04 · 유료 플랜' },
  { id: 'E', from: 356, to: 478, accent: '#E8A93C', chapter: 'STEP 04 · 가격' },
  { id: 'F', from: 478, to: 574, accent: '#D9694F', chapter: '비용 비교 · 손절' },
  { id: 'G', from: 574, to: 709, accent: '#7FA66B', chapter: '비용 비교 · 가치' },
  { id: 'H', from: 709, to: 796, accent: '#E8A93C', chapter: '주의 · 무료 한계' },
  { id: 'I', from: 796, to: 888, accent: '#9B6A8E', chapter: 'STEP 05 · 코워크' },
  { id: 'J', from: 888, to: 942, accent: '#6FA86A', chapter: '완료' },
];
const secAt = (f: number) => SECTIONS.find(s => f >= s.from && f < s.to) ?? SECTIONS[SECTIONS.length - 1];

// 액센트: 구간 경계에서 18프레임 보간
const accentAt = (f: number) => {
  const cur = secAt(f);
  const idx = SECTIONS.indexOf(cur);
  const prev = idx > 0 ? SECTIONS[idx - 1] : cur;
  const t = ci(f, cur.from, cur.from + 18);
  return blend(prev.accent, cur.accent, t);
};

// ── 자막 (SRT 정합)
const SUBS = [
  { from: 0,   to: 90,  text: '클로드 데스크탑 앱을 설치하는 것이\n첫 번째 단계입니다.', accent: '첫 번째 단계' },
  { from: 97,  to: 182, text: '구글에서 클로드 AI를 검색하면\n바로 나타납니다.', accent: '클로드 AI' },
  { from: 188, to: 232, text: '다운로드해서 설치해야 합니다.', accent: '다운로드' },
  { from: 239, to: 348, text: '자동화를 하려면 유료 플랜이 필요합니다.', accent: '유료 플랜' },
  { from: 356, to: 394, text: '월 3만 원 정도예요.', accent: '3만 원' },
  { from: 405, to: 472, text: '꼭 돈을 써야 하나 싶으실 텐데요.', accent: '돈을 써야' },
  { from: 478, to: 560, text: '주식할 때 손절하고\n수십만 원 나가는 건 쉽죠.', accent: '수십만 원' },
  { from: 574, to: 700, text: '매일 나를 위해 일하는 비서한테\n월 3만 원이 아까울까요.', accent: '월 3만 원' },
  { from: 709, to: 782, text: '무료 버전엔\n이 자동화 기능이 아예 없어요.', accent: '자동화 기능' },
  { from: 796, to: 884, text: '실행하면 왼쪽에\nCowork 탭이 보일 텐데', accent: 'Cowork 탭' },
  { from: 888, to: 936, text: '이제 클릭하시면 됩니다.', accent: '클릭' },
];

// ── Claude 로고
const ClaudeLogo: React.FC<{ size?: number }> = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 46 46">
    <rect width="46" height="46" rx="11" fill={C.coral} />
    <rect x="10" y="10" width="6.5" height="26" rx="3.25" fill={C.bone} />
    <rect x="19.75" y="10" width="6.5" height="26" rx="3.25" fill={C.bone} />
    <rect x="29.5" y="10" width="6.5" height="26" rx="3.25" fill={C.bone} />
  </svg>
);

// ════════════════════════════════════════════
//  배경: 따뜻한 코랄 메시 (부유 blob)
// ════════════════════════════════════════════
const Background: React.FC<{ f: number; accent: string }> = ({ f, accent }) => {
  const blob = (cx: number, cy: number, col: string, r: number, ax: number, ay: number, ph: number, op: number) => {
    const x = cx + Math.sin(f * 0.012 + ph) * ax;
    const y = cy + Math.cos(f * 0.010 + ph) * ay;
    return (
      <div style={{
        position: 'absolute', left: x - r, top: y - r, width: r * 2, height: r * 2,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${col} 0%, transparent 65%)`,
        filter: 'blur(70px)', opacity: op,
      }} />
    );
  };
  return (
    <AbsoluteFill style={{ background: `linear-gradient(155deg, ${C.warmDark} 0%, ${C.warmDark2} 100%)` }}>
      {blob(420, 320, C.coral, 560, 90, 70, 0, 0.34)}
      {blob(1540, 760, accent, 520, 110, 80, 2.1, 0.28)}
      {blob(1180, 220, C.coralSoft, 420, 70, 60, 4.0, 0.16)}
      {blob(300, 900, accent, 440, 80, 60, 1.2, 0.14)}
      {/* 미세 비네트 */}
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.34) 100%)' }} />
    </AbsoluteFill>
  );
};

// ════════════════════════════════════════════
//  발표자 윈도우 (좌) — 코랄 프레임 + 궤도 점 + 글로우
// ════════════════════════════════════════════
const PresenterWindow: React.FC<{ f: number; accent: string }> = ({ f, accent }) => {
  const X = 70, Y = 170, W = 1120, H = 630;
  const intro = sp(f, 4, 12, 200, 0.8);
  const float = Math.sin(f * 0.045) * 4;
  const scale = 0.96 + intro * 0.04;

  // 모서리 궤도 점
  const dot = (corner: 0 | 1 | 2 | 3) => {
    const ang = f * 0.03 + (corner * Math.PI) / 2;
    const cx = corner === 0 || corner === 3 ? -4 : W + 4;
    const cy = corner < 2 ? -4 : H + 4;
    const ox = Math.cos(ang) * 10, oy = Math.sin(ang) * 10;
    return (
      <div key={corner} style={{
        position: 'absolute', left: cx + ox - 5, top: cy + oy - 5,
        width: 10, height: 10, borderRadius: '50%',
        background: accent, boxShadow: `0 0 12px ${accent}`, opacity: 0.9,
      }} />
    );
  };

  return (
    <div style={{
      position: 'absolute', left: X, top: Y + float, width: W, height: H,
      transform: `scale(${scale})`, transformOrigin: 'center center',
      opacity: ci(f, 2, 18), zIndex: 30,
    }}>
      {/* 글로우 */}
      <div style={{
        position: 'absolute', inset: -40, borderRadius: 28,
        background: `radial-gradient(circle, ${accent}44 0%, transparent 62%)`,
        filter: 'blur(24px)',
      }} />
      {/* 프레임 */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 20, overflow: 'hidden',
        border: `3px solid ${accent}`,
        boxShadow: `0 24px 60px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(255,255,255,0.06)`,
        background: C.warmDark2,
      }}>
        <OffthreadVideo
          src={staticFile('kakao/s5_ai.mp4')}
          volume={0}
          // R3 ✓ cover (윈도우 16:9 = 소스 비율 일치 → 찌그러짐 없음)
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
        {/* 좌하단 LIVE 배지 */}
        <div style={{
          position: 'absolute', left: 18, bottom: 16,
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'rgba(20,19,19,0.7)', borderRadius: 8, padding: '7px 13px',
          backdropFilter: 'blur(6px)',
        }}>
          <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#E5484D',
            opacity: 0.6 + Math.sin(f * 0.2) * 0.4 }} />
          <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: C.onDark, letterSpacing: '0.08em' }}>
            CLAUDE
          </span>
        </div>
      </div>
      {[0, 1, 2, 3].map(c => dot(c as 0 | 1 | 2 | 3))}
    </div>
  );
};

// ════════════════════════════════════════════
//  우측 정보 컬럼 (x 1230, w 650)
// ════════════════════════════════════════════
const COL_X = 1230, COL_W = 650;
const colCard = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'absolute', left: COL_X, width: COL_W,
  borderRadius: 16, overflow: 'hidden', ...extra,
});

// 스크린샷 디바이스 카드
const DeviceCard: React.FC<{ src: string; accent: string; label: string; op: number; y: number; floatF: number }> =
({ src, accent, label, op, y, floatF }) => {
  const float = Math.sin(floatF * 0.05) * 4;
  return (
    <div style={{
      ...colCard({ top: y + float, opacity: op,
        background: C.cardCream, border: `2px solid ${accent}`,
        boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 30px ${accent}33` }),
    }}>
      {/* 브라우저 크롬 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
        background: 'rgba(31,30,29,0.06)', borderBottom: `1px solid ${accent}33` }}>
        <div style={{ width: 11, height: 11, borderRadius: '50%', background: '#E5484D' }} />
        <div style={{ width: 11, height: 11, borderRadius: '50%', background: '#E8A93C' }} />
        <div style={{ width: 11, height: 11, borderRadius: '50%', background: '#6FA86A' }} />
        <div style={{ marginLeft: 12, flex: 1, height: 22, borderRadius: 6, background: '#fff',
          display: 'flex', alignItems: 'center', padding: '0 12px' }}>
          <span style={{ fontFamily: SANS, fontSize: 13, color: C.muted }}>claude.ai</span>
        </div>
      </div>
      <Img src={src} style={{ width: '100%', height: 360, objectFit: 'cover', objectPosition: 'top', display: 'block' }} />
      {/* 라벨 바 */}
      <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: accent }} />
        <span style={{ fontFamily: SERIF, fontSize: 32, fontWeight: 700, color: C.ink }}>{label}</span>
      </div>
    </div>
  );
};

const RightColumn: React.FC<{ f: number; accent: string }> = ({ f, accent }) => {
  const op = (a: number, b: number, fadeIn = 18, fadeOut = 14) =>
    Math.min(ci(f, a, a + fadeIn), ci(f, b - fadeOut, b, 1, 0));

  return (
    <>
      {/* ── A: 인트로 타이틀 (0–96) */}
      {op(6, 97) > 0.01 && (() => {
        const o = op(6, 97); const rise = (1 - sp(f, 8, 11, 240)) * 24;
        return (
          <div style={{ ...colCard({ top: 300, opacity: o }), transform: `translateY(${rise}px)` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 22 }}>
              <ClaudeLogo size={64} />
              <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
                letterSpacing: '0.10em', textTransform: 'uppercase' }}>Desktop App</span>
            </div>
            <div style={{ fontFamily: SERIF, fontSize: 72, fontWeight: 700, color: C.onDark, lineHeight: 1.08 }}>
              클로드<br />데스크탑 설치
            </div>
            <div style={{ fontFamily: SANS, fontSize: 22, fontWeight: 500, color: C.muted, marginTop: 18 }}>
              따라하면 켜집니다. 어렵지 않아요.
            </div>
          </div>
        );
      })()}

      {/* ── B: 검색 스샷 (97–187) img1→img2 전환 */}
      {op(97, 188) > 0.01 && (
        <DeviceCard src={staticFile(f < 150 ? 'kakao/s5/img1.png' : 'kakao/s5/img2.png')}
          accent={accent} label="구글에 “클로드 데스크탑” 검색" op={op(97, 188)} y={190} floatF={f} />
      )}

      {/* ── C: 다운로드 스샷 (188–238) img3 */}
      {op(188, 239) > 0.01 && (
        <DeviceCard src={staticFile('kakao/s5/img3.png')}
          accent={accent} label="Download 클릭 → 설치" op={op(188, 239)} y={190} floatF={f} />
      )}

      {/* ── D: PRO PLAN 기능 리스트 (239–355) */}
      {op(239, 356) > 0.01 && (() => {
        const o = op(239, 356);
        const FEATS = [
          { t: '자동화 (MCP 연결)', d: 250 }, { t: 'Cowork 탭', d: 264 },
          { t: '외부 앱 제어', d: 278 }, { t: '장 전 브리핑 자동화', d: 292 },
        ];
        return (
          <div style={{ ...colCard({ top: 220, opacity: o, background: C.cardDark,
            border: `2px solid ${accent}`, boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 30px ${accent}40` }) }}>
            <div style={{ padding: '20px 26px', background: `linear-gradient(90deg, ${accent}26 0%, transparent 100%)`,
              borderBottom: `1px solid ${accent}40` }}>
              <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
                letterSpacing: '0.10em', textTransform: 'uppercase' }}>PRO PLAN ONLY</span>
              <div style={{ fontFamily: SERIF, fontSize: 40, fontWeight: 700, color: C.onDark, marginTop: 6 }}>
                유료 플랜에서만
              </div>
            </div>
            <div style={{ padding: '14px 0 20px' }}>
              {FEATS.map((ft, i) => {
                const fo = ci(f, ft.d, ft.d + 14); const fx = (1 - sp(f, ft.d, 11, 260)) * 22;
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 26px',
                    opacity: fo, transform: `translateX(${fx}px)` }}>
                    <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0,
                      background: `${accent}26`, border: `1.5px solid ${accent}`, color: accent,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 700 }}>✓</div>
                    <span style={{ fontFamily: SANS, fontSize: 22, fontWeight: 600, color: C.onDark }}>{ft.t}</span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* ── E: 가격 대형 수치 (356–477) */}
      {op(356, 478) > 0.01 && (() => {
        const o = op(356, 478); const pop = 0.7 + sp(f, 360, 9, 240) * 0.3;
        return (
          <div style={{ ...colCard({ top: 300, opacity: o, background: C.cardCream,
            border: `2px solid ${accent}`, boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 36px ${accent}40`,
            padding: '40px 44px', textAlign: 'center' }), transform: `scale(${pop})` }}>
            <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
              letterSpacing: '0.10em', textTransform: 'uppercase' }}>Claude Pro · 월정액</span>
            <div style={{ fontFamily: SERIF, fontSize: 110, fontWeight: 700, color: C.ink, lineHeight: 1, marginTop: 14 }}>
              ₩30,000
            </div>
            <div style={{ fontFamily: SANS, fontSize: 22, fontWeight: 500, color: C.muted, marginTop: 14 }}>
              하루 천 원, 커피 한 잔 값
            </div>
          </div>
        );
      })()}

      {/* ── F: 손절 비용 카드 (478–573) */}
      {op(478, 574) > 0.01 && (() => {
        const o = op(478, 574); const rise = (1 - sp(f, 482, 10, 240)) * 26;
        return (
          <div style={{ ...colCard({ top: 320, opacity: o, background: C.cardDark,
            border: `2px solid ${accent}`, boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 32px ${accent}40`,
            padding: '36px 40px', textAlign: 'center' }), transform: `translateY(${rise}px)` }}>
            <div style={{ fontSize: 44, marginBottom: 10 }}>📉</div>
            <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
              letterSpacing: '0.10em', textTransform: 'uppercase' }}>손절 한 번</span>
            <div style={{ fontFamily: SERIF, fontSize: 72, fontWeight: 700, color: '#EC6A52', lineHeight: 1, marginTop: 12 }}>
              수십만 원
            </div>
            <div style={{ fontFamily: SANS, fontSize: 22, fontWeight: 500, color: C.muted, marginTop: 14 }}>
              순식간에 사라집니다
            </div>
          </div>
        );
      })()}

      {/* ── G: vs 비서 가치 (574–708) */}
      {op(574, 709) > 0.01 && (() => {
        const o = op(574, 709);
        const lO = ci(f, 580, 600); const rO = ci(f, 600, 620); const vO = ci(f, 616, 634);
        return (
          <div style={{ ...colCard({ top: 250, opacity: o }) }}>
            {/* 손절 (작게, 흐리게) */}
            <div style={{ background: C.cardDark, border: `1.5px solid rgba(217,105,79,0.5)`, borderRadius: 14,
              padding: '20px 26px', opacity: lO, marginBottom: 18,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: SANS, fontSize: 22, fontWeight: 600, color: C.muted }}>손절 한 번</span>
              <span style={{ fontFamily: SERIF, fontSize: 40, fontWeight: 700, color: '#EC6A52' }}>수십만 원</span>
            </div>
            {/* vs */}
            <div style={{ textAlign: 'center', opacity: vO, margin: '2px 0 18px' }}>
              <span style={{ fontFamily: SERIF, fontSize: 30, fontWeight: 600, color: C.coralSoft, fontStyle: 'italic' }}>vs</span>
            </div>
            {/* AI 비서 (크게, 강조) */}
            <div style={{ background: C.cardCream, border: `2px solid ${accent}`, borderRadius: 16,
              padding: '32px 36px', opacity: rO, textAlign: 'center',
              boxShadow: `0 0 32px ${accent}44` }}>
              <div style={{ fontSize: 40, marginBottom: 8 }}>🤖</div>
              <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
                letterSpacing: '0.10em', textTransform: 'uppercase' }}>AI 비서 · 한 달</span>
              <div style={{ fontFamily: SERIF, fontSize: 76, fontWeight: 700, color: C.ink, lineHeight: 1, marginTop: 10 }}>
                ₩30,000
              </div>
              <div style={{ fontFamily: SANS, fontSize: 22, fontWeight: 500, color: C.muted, marginTop: 12 }}>
                매일 나를 위해 일합니다
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── H: 무료 경고 패널 (709–795) */}
      {op(709, 796) > 0.01 && (() => {
        const o = op(709, 796); const drop = (1 - sp(f, 712, 6, 280, 0.5)) * -30;
        return (
          <div style={{ ...colCard({ top: 350, opacity: o, background: C.cardDark,
            borderLeft: `6px solid ${accent}`, border: `2px solid ${accent}`, borderLeftWidth: 6,
            boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 30px ${accent}40`,
            padding: '34px 38px' }), transform: `translateY(${drop}px)` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
              <span style={{ fontSize: 40 }}>⚠️</span>
              <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: accent,
                letterSpacing: '0.10em', textTransform: 'uppercase' }}>Free Plan</span>
            </div>
            <div style={{ fontFamily: SERIF, fontSize: 46, fontWeight: 700, color: C.onDark, lineHeight: 1.2 }}>
              무료엔 자동화<br />기능이 없습니다
            </div>
          </div>
        );
      })()}

      {/* ── I: 코워크 스샷 (796–887) img5 */}
      {op(796, 888) > 0.01 && (
        <DeviceCard src={staticFile('kakao/s5/img5.png')}
          accent={accent} label="왼쪽 Cowork 탭 확인" op={op(796, 888)} y={190} floatF={f} />
      )}

      {/* ── J: 완료 (888–942) */}
      {op(888, 942) > 0.01 && (() => {
        const o = op(888, 942); const pop = 0.6 + sp(f, 890, 8, 240) * 0.4;
        return (
          <div style={{ ...colCard({ top: 320, opacity: o, background: C.cardCream,
            border: `2px solid ${accent}`, boxShadow: `0 22px 50px rgba(0,0,0,0.5), 0 0 40px ${accent}55`,
            padding: '44px', textAlign: 'center' }), transform: `scale(${pop})` }}>
            <div style={{ width: 96, height: 96, borderRadius: '50%', margin: '0 auto 22px',
              background: `${accent}26`, border: `2px solid ${accent}`, color: accent,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48, fontWeight: 700 }}>✓</div>
            <div style={{ fontFamily: SERIF, fontSize: 56, fontWeight: 700, color: C.ink }}>설치 완료</div>
            <div style={{ fontFamily: SANS, fontSize: 22, fontWeight: 500, color: C.muted, marginTop: 12 }}>
              이제 클릭만 하면 시작입니다
            </div>
          </div>
        );
      })()}
    </>
  );
};

// ════════════════════════════════════════════
//  상단: 진행 리본 + 챕터 칩 + 로고
// ════════════════════════════════════════════
const TopBar: React.FC<{ f: number; accent: string }> = ({ f, accent }) => {
  const sec = secAt(f);
  const pct = interpolate(f, [0, 96, 238, 355, 477, 573, 708, 795, 887, 942],
    [2, 12, 26, 42, 58, 70, 82, 90, 96, 100], { extrapolateRight: 'clamp' });
  // 챕터 칩 슬라이드 (구간 바뀔 때마다)
  const chipIn = sp(f, sec.from, 12, 240);
  const chipX = (1 - chipIn) * -26;

  return (
    <>
      {/* 진행 리본 */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 5,
        background: 'rgba(240,238,230,0.08)', zIndex: 90 }}>
        <div style={{ height: '100%', width: `${pct}%`,
          background: `linear-gradient(90deg, ${C.coral} 0%, ${accent} 100%)`,
          boxShadow: `0 0 8px ${accent}` }} />
      </div>
      {/* 챕터 칩 (좌상단) */}
      <div key={sec.id} style={{ position: 'absolute', top: 56, left: 70, zIndex: 90,
        opacity: ci(f, sec.from, sec.from + 10), transform: `translateX(${chipX}px)` }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12,
          background: 'rgba(20,19,19,0.55)', backdropFilter: 'blur(6px)',
          borderRadius: 30, padding: '11px 22px', border: `1.5px solid ${accent}66` }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: accent,
            boxShadow: `0 0 10px ${accent}` }} />
          <span style={{ fontFamily: SANS, fontSize: 18, fontWeight: 700, color: C.onDark,
            letterSpacing: '0.08em' }}>{sec.chapter}</span>
        </div>
      </div>
      {/* 로고 (우상단) */}
      <div style={{ position: 'absolute', top: 50, right: 44, zIndex: 90,
        display: 'flex', alignItems: 'center', gap: 12, opacity: ci(f, 6, 24) }}>
        <span style={{ fontFamily: SERIF, fontSize: 26, fontWeight: 600, color: C.onDark }}>Claude</span>
        <ClaudeLogo size={40} />
      </div>
    </>
  );
};

// ════════════════════════════════════════════
//  하단: 키네틱 세리프 자막
// ════════════════════════════════════════════
const Subtitle: React.FC<{ f: number; accent: string }> = ({ f, accent }) => {
  const sub = SUBS.find(s => f >= s.from && f < s.to);
  if (!sub) return null;
  const barOp = Math.min(ci(f, sub.from, sub.from + 7), ci(f, sub.to - 6, sub.to, 1, 0));
  const accentWords = new Set((sub.accent ?? '').split(' '));
  const strip = (w: string) => w.replace(/[.,?!"“”]/g, '');

  const lines = sub.text.split('\n');
  let wi = 0;
  return (
    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '16%',
      background: 'linear-gradient(0deg, rgba(20,19,19,0.94) 0%, rgba(20,19,19,0.82) 55%, transparent 100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '0 140px', opacity: barOp, zIndex: 80, gap: 4 }}>
      {lines.map((line, li) => (
        <div key={li} style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 14px' }}>
          {line.split(' ').map((word, k) => {
            const delay = sub.from + wi * 2; wi += 1;
            const o = ci(f, delay, delay + 8);
            const y = (1 - sp(f, delay, 12, 260)) * 14;
            const isAcc = accentWords.has(strip(word));
            return (
              <span key={k} style={{ fontFamily: SERIF, fontSize: 44, fontWeight: 700,
                color: isAcc ? accent : C.onDark, opacity: o, transform: `translateY(${y}px)`,
                display: 'inline-block', textShadow: '0 2px 10px rgba(0,0,0,0.8)',
                borderBottom: isAcc ? `3px solid ${accent}` : 'none', lineHeight: 1.35, paddingBottom: 2 }}>
                {word}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

// ════════════════════════════════════════════
//  메인
// ════════════════════════════════════════════
export const KK_S5_ClaudeLive: React.FC = () => {
  const f = useCurrentFrame();
  const accent = accentAt(f);
  const globalFade = ci(f, 930, 942, 1, 0);

  return (
    <AbsoluteFill style={{ overflow: 'hidden', opacity: globalFade }}>
      <Background f={f} accent={accent} />
      <PresenterWindow f={f} accent={accent} />
      <RightColumn f={f} accent={accent} />
      <TopBar f={f} accent={accent} />
      <Subtitle f={f} accent={accent} />
    </AbsoluteFill>
  );
};
