/**
 * KK_S5_PiP — S5 PiP 레이아웃 (발표자 우측 9:16 + 화면 녹화 좌측)
 *
 * 전환 구조:
 *   f0      : 발표자 영상 풀스크린
 *   f0~40   : spring 축소 → 우측 9:16 PiP 프레임
 *   f20~50  : 화면 녹화 영역 fade-in (좌측)
 *
 * 화면 녹화 파일 교체:
 *   SCREEN_SRC 상수에 staticFile('kakao/s5_screen.mp4') 로 교체
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

export const KK_S5_PIP_FRAMES = 942; // 31.4s × 30fps

// ── 화면 녹화 파일 경로 (파일 생기면 여기만 교체) ──
const SCREEN_SRC: string | null = null; // 파일 생기면: staticFile('kakao/ep1/s05_screen.mp4')

// ── PiP 크기 ──
const PIP_W      = 316;
const PIP_H      = Math.round(PIP_W * 16 / 9); // 562px
const PIP_RIGHT  = 52;
const PIP_TOP    = Math.round((1080 - PIP_H) / 2); // 259px
const PIP_RADIUS = 22;

const LIME   = '#AAFF00';
const LIME50 = 'rgba(170,255,0,0.5)';
const LIME15 = 'rgba(170,255,0,0.15)';
const CARD   = 'rgba(0,0,0,0.84)';
const BORDER = 'rgba(170,255,0,0.55)';

const ci = (f: number, a: number, b: number, va = 0, vb = 1) =>
  interpolate(f, [a, b], [va, vb], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

const sp = (f: number, from = 0, damping = 14, stiffness = 180, mass = 0.9) =>
  spring({ frame: Math.max(0, f - from), fps: 30, config: { damping, stiffness, mass } });

// ── 자막 세그먼트 ──
const SUBS = [
  { from: 0,   to: 87,  text: '클로드 데스크탑 앱을 설치하는 것이\n첫 번째 단계입니다.',                  accent: '첫 번째 단계' },
  { from: 97,  to: 180, text: '구글에서 클로드 AI를 검색하면 바로 나타납니다.',                            accent: '클로드 AI' },
  { from: 188, to: 230, text: '다운로드해서 설치해야 합니다.',                                              accent: '설치' },
  { from: 239, to: 344, text: '자동화를 하려면 유료 플랜이 필요합니다.',                                    accent: '유료 플랜' },
  { from: 356, to: 392, text: '월 3만 원 정도예요.',                                                        accent: '3만 원' },
  { from: 405, to: 469, text: '꼭 돈을 써야 해 하실 수 있을 텐데요.',                                      accent: '돈을 써야' },
  { from: 478, to: 556, text: '주식할 때 손절하고 수십만 원 나가는 건 쉽죠.',                              accent: '수십만 원' },
  { from: 574, to: 696, text: '매일 나를 위해 일하는 비서한테\n월 3만 원 주는 거 아까워하시면 안 됩니다.', accent: '3만 원' },
  { from: 709, to: 778, text: '무료 버전엔 이 자동화 기능을 아예 없어요.',                                  accent: '자동화 기능' },
  { from: 796, to: 888, text: '설치하고 실행하면 왼쪽에\nComputer Use 탭이 보일 텐데',                     accent: 'Computer Use' },
  { from: 888, to: 925, text: '이제 클릭하시면 됩니다.',                                                    accent: '클릭' },
];

export const KK_S5_PiP: React.FC = () => {
  const f = useCurrentFrame();

  // ── 전환 progress (0→1, 약 1.3초) ──
  const trans = sp(f, 0, 14, 180, 0.9);

  // ── 발표자 컨테이너 애니메이션 ──
  const presW      = interpolate(trans, [0, 1], [1920, PIP_W]);
  const presH      = interpolate(trans, [0, 1], [1080, PIP_H]);
  const presX      = interpolate(trans, [0, 1], [0,    1920 - PIP_W - PIP_RIGHT]);
  const presY      = interpolate(trans, [0, 1], [0,    PIP_TOP]);
  const presRadius = interpolate(trans, [0, 1], [0,    PIP_RADIUS]);

  // ── 좌측 화면 영역 ──
  const screenOp  = ci(f, 20, 50);
  const screenX   = interpolate(trans, [0, 1], [-60, 0]);

  // ── LIVE 배지 ──
  const badgeOp   = ci(f, 35, 55);

  // ── 그림자 glow ──
  const glowAmt   = interpolate(trans, [0, 1], [0, 1]);

  const activeSub = SUBS.find(s => f >= s.from && f < s.to);

  return (
    <AbsoluteFill style={{ fontFamily: "'Inter', sans-serif", overflow: 'hidden', background: '#0a0a0a' }}>

      {/* ── 좌측: 화면 녹화 영역 ── */}
      <div style={{
        position: 'absolute',
        left: 0,
        top: 0,
        right: PIP_W + PIP_RIGHT + 20,
        bottom: 0,
        opacity: screenOp,
        transform: `translateX(${screenX}px)`,
        overflow: 'hidden',
      }}>
        {SCREEN_SRC ? (
          <OffthreadVideo
            src={SCREEN_SRC}
            style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }}
          />
        ) : (
          /* 플레이스홀더 — 화면 녹화 파일 없을 때 */
          <div style={{
            width: '100%', height: '100%',
            background: 'linear-gradient(135deg, #0d1117 0%, #111a1a 100%)',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 18,
          }}>
            {/* 터미널 느낌 프레임 */}
            <div style={{
              border: `1px solid rgba(170,255,0,0.25)`,
              borderRadius: 8,
              padding: '28px 48px',
              textAlign: 'center',
            }}>
              <div style={{ fontFamily: "'Courier New',monospace", fontSize: 11,
                color: LIME50, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 16 }}>
                SCREEN RECORDING
              </div>
              <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 20, fontWeight: 700,
                color: 'rgba(255,255,255,0.35)' }}>
                설치 화면 녹화 영역
              </div>
              <div style={{ fontFamily: "'Courier New',monospace", fontSize: 10,
                color: 'rgba(255,255,255,0.18)', marginTop: 10, letterSpacing: 1 }}>
                s5_screen.mp4 → public/kakao/
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── 발표자 PiP 컨테이너 ── */}
      <div style={{
        position: 'absolute',
        left: presX,
        top: presY,
        width: presW,
        height: presH,
        borderRadius: presRadius,
        overflow: 'hidden',
        boxShadow: glowAmt > 0.05
          ? `0 0 ${Math.round(glowAmt * 32)}px rgba(170,255,0,${glowAmt * 0.45}), 0 8px 40px rgba(0,0,0,0.8)`
          : 'none',
        // 라임 테두리 (전환 후에만)
        outline: glowAmt > 0.1
          ? `${Math.round(glowAmt * 2)}px solid rgba(170,255,0,${glowAmt * 0.6})`
          : 'none',
        outlineOffset: -1,
      }}>
        <OffthreadVideo
          src={staticFile('kakao/ep1/s05_screen.mp4')}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>

      {/* ── LIVE 배지 (PiP 상단 좌측) ── */}
      <div style={{
        position: 'absolute',
        left: presX + 10,
        top: presY + 10,
        opacity: badgeOp * interpolate(trans, [0, 1], [0, 1]),
        display: 'flex', alignItems: 'center', gap: 6,
        background: CARD,
        border: `1px solid ${BORDER}`,
        borderRadius: 5,
        padding: '4px 10px',
        pointerEvents: 'none',
      }}>
        {/* 빨간 라이브 dot */}
        <div style={{
          width: 7, height: 7, borderRadius: '50%',
          background: '#ff4444',
          boxShadow: '0 0 6px rgba(255,60,60,0.8)',
        }} />
        <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
          color: LIME, letterSpacing: 2.5, textTransform: 'uppercase' }}>
          LIVE
        </span>
        <span style={{ fontFamily: "'Courier New',monospace", fontSize: 9,
          color: 'rgba(255,255,255,0.4)', letterSpacing: 1 }}>
          · 09:16
        </span>
      </div>

      {/* ── 수직 구분선 (전환 후) ── */}
      <div style={{
        position: 'absolute',
        top: 60,
        bottom: 60,
        right: PIP_W + PIP_RIGHT + 18,
        width: 1,
        background: `linear-gradient(to bottom, transparent, ${LIME15} 30%, ${LIME15} 70%, transparent)`,
        opacity: interpolate(trans, [0.6, 1], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
      }} />

      {/* ── 하단 그라데이션 ── */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '18%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, transparent 100%)',
        pointerEvents: 'none',
      }} />

      {/* ── 자막 바 ── */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0,
        // 좌측 콘텐츠 영역 기준 (PiP 아래까지 내려오지 않도록)
        right: PIP_W + PIP_RIGHT + 20,
        height: '18%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {activeSub && (
          <div style={{
            fontFamily: "'Inter',sans-serif",
            fontSize: 34, fontWeight: 700, color: '#fff',
            textAlign: 'center', paddingInline: 48,
            textShadow: '0 2px 18px rgba(0,0,0,0.98), 0 0 40px rgba(0,0,0,0.9)',
            lineHeight: 1.5,
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
