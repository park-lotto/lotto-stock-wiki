/**
 * NV_S01_Intro v3 — NVIDIA CI/BI 디자인 시스템 기반
 *
 * 디자인 시스템: NVIDIA GTC 분위기
 *   - Primary: #76B900 (NVIDIA Green)
 *   - Dark: #0A0A0A
 *   - Typography: 초대형 Bold / Monospace 데이터
 *
 * Phase 1 (f0~74):   날짜 LEFT + ChatGPT 로고 RIGHT (발표자 정상 노출)
 * Phase 2 (f74~141): 날짜 유지 + ChatGPT 임팩트 텍스트
 * Phase 3 (f141~240): 다크 그린 오버레이 + 초대형 NVIDIA + 파티클 + 시총 카운터
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

export const NV_S01_FRAMES = 241;

const NV_GREEN   = '#76B900';
const NV_GREEN5  = 'rgba(118,185,0,0.5)';
const NV_GREEN15 = 'rgba(118,185,0,0.15)';
const WHITE      = '#FFFFFF';
const WHITE7     = 'rgba(255,255,255,0.7)';
const WHITE4     = 'rgba(255,255,255,0.4)';

const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (f: number, from: number, d = 10, s = 240, m = 0.8) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping: d, stiffness: s, mass: m } });

// ── 자막
const SUBS = [
  { from: 0,   to: 74,  text: '2022년 11월 30일' },
  { from: 74,  to: 141, text: '챗GPT가 세상에 나왔습니다' },
  { from: 141, to: 241, text: '그리고 하나의 기업이 폭발했습니다' },
];

// ── 결정론적 파티클 (씨앗 기반 고정 위치)
const PARTICLES = Array.from({ length: 90 }, (_, i) => ({
  x:       (i * 61.8) % 100,
  y:       (i * 38.2) % 100,
  size:    [2, 2, 3, 4, 2, 3, 2][i % 7],
  delay:   (i * 2.3) % 40,
  isGreen: i % 6 === 0,
  alpha:   0.25 + (i % 8) * 0.09,
  speed:   0.6 + (i % 5) * 0.2,
}));

// ── ChatGPT 스월 로고 (SVG 근사)
const ChatGPTIcon: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" fill="none">
    {[0, 40, 80, 120, 160, 200, 240, 280, 320].map((angle) => (
      <rect
        key={angle}
        x="44" y="10"
        width="12" height="32"
        rx="6"
        fill="white"
        opacity={0.85}
        transform={`rotate(${angle} 50 50)`}
      />
    ))}
    <circle cx="50" cy="50" r="10" fill="white" />
  </svg>
);

// ── NVIDIA 아이 로고 (SVG 근사)
const NvidiaIcon: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" fill="none">
    <path
      d="M10 50 Q10 10 50 10 Q90 10 90 50 Q90 90 50 90 Q10 90 10 50 Z"
      stroke={NV_GREEN} strokeWidth="4" fill="none"
    />
    <path
      d="M50 10 L50 0 M90 50 L100 50 M50 90 L50 100 M10 50 L0 50
         M77 23 L84 16 M77 77 L84 84 M23 77 L16 84 M23 23 L16 16"
      stroke={NV_GREEN} strokeWidth="3" strokeLinecap="round"
    />
    <ellipse cx="50" cy="50" rx="18" ry="12" fill={NV_GREEN} />
    <ellipse cx="50" cy="50" rx="8" ry="8" fill="#0A0A0A" />
    <ellipse cx="47" cy="47" rx="3" ry="3" fill={NV_GREEN} />
  </svg>
);

export const NV_S01_Intro: React.FC = () => {
  const f = useCurrentFrame();
  const activeSub = SUBS.find(s => f >= s.from && f < s.to);

  // ══════════════════════════════
  // Phase 1+2 — 날짜 & ChatGPT (f0~141)
  // ══════════════════════════════
  const p12Op = ci(f, 0, 14) * ci(f, 128, 141, 1, 0);

  // 날짜 LEFT
  const dateOp = p12Op;
  const dateTx = (1 - sp(f, 0, 12, 260, 0.75)) * -50;

  // ChatGPT RIGHT (f0에 바로 등장, Phase 1부터 보임)
  const cgOp  = ci(f, 4, 22) * ci(f, 128, 141, 1, 0);
  const cgTx  = (1 - sp(f, 4, 11, 250, 0.78)) * 50;

  // ══════════════════════════════
  // Phase 3 — NVIDIA 폭발 (f141~241)
  // ══════════════════════════════
  const p3Op       = ci(f, 141, 152);
  const p3FadeOut  = ci(f, 226, 241, 1, 0);

  // 다크 그린 오버레이
  const darkOverlayOp = ci(f, 141, 162, 0, 0.78) * p3FadeOut;
  const greenTintOp   = ci(f, 148, 170, 0, 0.22) * p3FadeOut;

  // NVIDIA 초대형 텍스트
  const nvTextSc  = 0.5 + sp(f, 141, 7, 320, 0.6) * 0.5;
  const nvTextOp  = ci(f, 141, 158) * p3FadeOut;
  const nvGlow    = 0.4 + Math.sin(f * 0.18) * 0.6;

  // 파티클 (Phase 3에서 활성화)
  const particleOp = ci(f, 141, 168) * p3FadeOut;

  // 시총 카운터 (Phase 3 우측)
  const counterOp  = ci(f, 158, 176) * p3FadeOut;
  const counterVal = Math.round(ci(f, 162, 216, 0, 412547804));
  const counterStr = counterVal.toLocaleString('en-US');

  // NVIDIA 로고 (Phase 3 좌측)
  const nvLogoOp  = ci(f, 148, 166) * p3FadeOut;
  const nvLogoTx  = (1 - sp(f, 148, 11, 250, 0.8)) * -40;

  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: '#000', fontFamily: '"Pretendard", "Noto Sans KR", sans-serif' }}>

      {/* ── 배경 영상 */}
      <OffthreadVideo
        src={staticFile('nvidia/scene01.mp4')}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        volume={0}
      />

      {/* ══════════════════════════════
          Phase 3: 다크 오버레이 + 그린 틴트
          ══════════════════════════════ */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `rgba(0,0,0,${darkOverlayOp})`,
      }} />
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `rgba(20,40,0,${greenTintOp})`,
      }} />

      {/* ══════════════════════════════
          Phase 3: 스파클 파티클
          ══════════════════════════════ */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: particleOp }}>
        {PARTICLES.map((p, i) => {
          const twinkle = 0.3 + Math.abs(Math.sin((f * p.speed + i * 0.8) * 0.12)) * 0.7;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: `${p.x}%`,
                top: `${p.y}%`,
                width: p.size,
                height: p.size,
                background: p.isGreen ? NV_GREEN : WHITE,
                opacity: p.alpha * twinkle,
                borderRadius: 0.5,
                transform: `rotate(${i * 37}deg)`,
              }}
            />
          );
        })}
      </div>

      {/* ══════════════════════════════
          Phase 1~2: 날짜 LEFT
          ══════════════════════════════ */}
      <div style={{
        position: 'absolute', left: 48, top: 110,
        opacity: dateOp, transform: `translateX(${dateTx}px)`,
      }}>
        {/* SINCE 레이블 */}
        <div style={{
          fontFamily: '"Courier New", monospace',
          fontSize: 13, color: WHITE4, letterSpacing: 6,
          textTransform: 'uppercase', marginBottom: 16,
        }}>
          SINCE
        </div>

        {/* 2022 */}
        <div style={{
          fontSize: 110, fontWeight: 900, color: WHITE, lineHeight: 0.9,
          letterSpacing: -4,
          textShadow: '0 0 60px rgba(255,255,255,0.15)',
          opacity: ci(f, 6, 20),
          transform: `translateY(${(1 - sp(f, 6, 14, 300, 0.65)) * -30}px)`,
        }}>
          2022
        </div>

        {/* 11  30 */}
        <div style={{
          display: 'flex', alignItems: 'baseline', gap: 20, marginTop: 8,
          opacity: ci(f, 18, 34),
          transform: `translateY(${(1 - sp(f, 18, 14, 280, 0.7)) * -20}px)`,
        }}>
          <span style={{ fontSize: 72, fontWeight: 900, color: WHITE, letterSpacing: -2 }}>11</span>
          <span style={{ fontSize: 40, color: WHITE4, fontWeight: 300 }}>·</span>
          <span style={{ fontSize: 72, fontWeight: 900, color: WHITE, letterSpacing: -2 }}>30</span>
        </div>

        {/* 하단 라인 */}
        <div style={{
          width: `${ci(f, 20, 50, 0, 180)}px`, height: 2,
          background: NV_GREEN,
          boxShadow: `0 0 8px ${NV_GREEN5}`,
          marginTop: 16, borderRadius: 1,
        }} />
      </div>

      {/* ══════════════════════════════
          Phase 1~2: ChatGPT RIGHT
          ══════════════════════════════ */}
      <div style={{
        position: 'absolute', right: 56, top: 120,
        display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
        opacity: cgOp, transform: `translateX(${cgTx}px)`,
      }}>
        {/* ChatGPT 로고 + 이름 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12 }}>
          <div style={{ opacity: ci(f, 8, 24) }}>
            <ChatGPTIcon size={52} />
          </div>
          <div style={{
            fontSize: 52, fontWeight: 800, color: WHITE, letterSpacing: -1.5,
            opacity: ci(f, 12, 28),
            textShadow: '0 0 40px rgba(255,255,255,0.2)',
          }}>
            ChatGPT
          </div>
        </div>

        {/* A.I. ARRIVES */}
        <div style={{
          fontFamily: '"Courier New", monospace',
          fontSize: 12, color: WHITE4, letterSpacing: 6,
          textTransform: 'uppercase',
          opacity: ci(f, 26, 42),
        }}>
          A.I.  ARRIVES
        </div>

        {/* Phase 2에서 추가 수치 */}
        <div style={{
          marginTop: 28,
          opacity: ci(f, 78, 94) * ci(f, 128, 141, 1, 0),
        }}>
          <div style={{
            fontFamily: '"Courier New", monospace', fontSize: 10,
            color: WHITE4, letterSpacing: 3, marginBottom: 10,
            textAlign: 'right',
          }}>
            USERS GROWTH
          </div>
          {[
            { label: '1,000,000 users', sub: '5일 만에', delay: 80 },
            { label: '100,000,000 users', sub: '60일 만에', delay: 96 },
          ].map((row, i) => (
            <div key={i} style={{
              textAlign: 'right', marginBottom: 10,
              opacity: ci(f, row.delay, row.delay + 14),
            }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: WHITE, letterSpacing: -0.5 }}>
                {row.label}
              </div>
              <div style={{ fontSize: 12, color: NV_GREEN, fontFamily: '"Courier New", monospace' }}>
                {row.sub}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ══════════════════════════════
          Phase 3: 초대형 NVIDIA 중앙
          ══════════════════════════════ */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        pointerEvents: 'none',
        opacity: nvTextOp,
        transform: `scale(${nvTextSc})`,
      }}>
        <div style={{
          fontSize: 200, fontWeight: 900, color: WHITE,
          letterSpacing: 8,
          textShadow: `
            0 0 80px rgba(118,185,0,${nvGlow * 0.6}),
            0 0 160px rgba(118,185,0,${nvGlow * 0.3}),
            0 8px 40px rgba(0,0,0,0.95)
          `,
          lineHeight: 1,
          // 인물 머리 위 영역에 배치되도록 약간 위로
          marginBottom: 80,
        }}>
          NVIDIA
        </div>
      </div>

      {/* ══════════════════════════════
          Phase 3: NVIDIA 로고 LEFT
          ══════════════════════════════ */}
      <div style={{
        position: 'absolute', left: 48, top: 80,
        opacity: nvLogoOp,
        transform: `translateX(${nvLogoTx}px)`,
      }}>
        <div style={{
          fontFamily: '"Courier New", monospace', fontSize: 10,
          color: NV_GREEN, letterSpacing: 4, marginBottom: 14,
          textTransform: 'uppercase',
        }}>
          NVIDIA · STORY
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <NvidiaIcon size={64} />
          <div style={{
            fontSize: 56, fontWeight: 900, color: NV_GREEN,
            letterSpacing: 3,
            textShadow: `0 0 30px ${NV_GREEN5}`,
          }}>
            NVIDIA
          </div>
        </div>
      </div>

      {/* ══════════════════════════════
          Phase 3: 시총 카운터 RIGHT
          ══════════════════════════════ */}
      <div style={{
        position: 'absolute', right: 48, top: 72, width: 480,
        opacity: counterOp,
        transform: `translateX(${(1 - sp(f, 158, 10, 240, 0.8)) * 50}px)`,
      }}>
        {/* 헤더 */}
        <div style={{
          background: NV_GREEN,
          padding: '7px 16px',
          borderRadius: '4px 4px 0 0',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#000', letterSpacing: 1 }}>
            ⊕  2022. 11   ChatGPT Launch
          </div>
        </div>

        {/* 바디 */}
        <div style={{
          background: 'rgba(0,0,0,0.82)',
          border: `1px solid rgba(118,185,0,0.35)`,
          borderTop: 'none',
          borderRadius: '0 0 4px 4px',
          padding: '16px 18px 18px',
        }}>
          <div style={{
            fontFamily: '"Courier New", monospace', fontSize: 10,
            color: WHITE4, letterSpacing: 3, marginBottom: 8,
            textTransform: 'uppercase',
          }}>
            Market Cap · 시가총액
          </div>

          {/* 카운터 */}
          <div style={{
            fontFamily: '"Courier New", monospace',
            fontSize: 34, fontWeight: 900, color: NV_GREEN,
            letterSpacing: -1,
            textShadow: `0 0 20px ${NV_GREEN5}`,
          }}>
            ${counterStr}
          </div>

          <div style={{
            fontFamily: '"Courier New", monospace', fontSize: 10,
            color: WHITE4, letterSpacing: 1.5, marginTop: 8,
            opacity: ci(f, 174, 188),
          }}>
            USD · 2022년 11월 30일 기준 추산
          </div>
        </div>
      </div>

      {/* ══════════════════════════════
          자막 바
          ══════════════════════════════ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        height: '17%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, transparent 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontSize: 42, fontWeight: 800, color: WHITE,
            textAlign: 'center', paddingInline: 80,
            textShadow: '0 2px 20px rgba(0,0,0,1)',
            opacity:
              ci(f, activeSub.from, activeSub.from + 5)
              * ci(f, activeSub.to - 4, activeSub.to, 1, 0),
          }}>
            {activeSub.text}
          </div>
        )}
      </div>

    </AbsoluteFill>
  );
};
